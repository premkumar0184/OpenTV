"""
OpenTV Interactive Terminal UI Application.
PROJECT.md Features F2.4, F2.5, F2.6:
- ANSI VT100 interactive dashboard with raw terminal key loop when in TTY.
- FallbackLineEngine integration for CI, non-TTY, and redirected stdin.
- 6 Screen Workflows:
  1. Main Menu (Status header, model, brand profile badge, OLED status, menu 1-6).
  2. Connection Wizard (Auto-detects USB devices, guides Wi-Fi connect & pairing).
  3. Home Screen Layout Manager (app checkbox picker, tile ordering, live 6-column TV grid preview).
  4. HDMI Input Manager (custom labels for HDMI 1-4, hardware passthrough URI confirmation).
  5. Debloat Assistant (4-tier categorized package view, 'S' safe bloat select, guardrails check summary, atomic rollback generation, audit logging).
  6. Deploy Launcher (pushes config JSON, installs APK, sets home activity, broadcasts reload).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from opentv.core.app_names import format_app_display, get_app_name

from opentv.core.adb import AdbClient, AdbDevice, AdbWrapper
from opentv.core.config import (
    DEFAULT_THEME,
    HdmiInputConfig,
    LauncherConfig,
    OledProtectionConfig,
    create_default_config,
)
from opentv.core.deployer import LauncherDeployer
from opentv.core.device import DeviceInfo, DeviceManager
from opentv.debloat.audit import AuditEvent, AuditLogger
from opentv.debloat.database import PackageSafetyDB, SafetyCategory
from opentv.debloat.guardrails import GuardrailViolation, GuardrailsEngine
from opentv.debloat.rollback import RollbackEngine
from opentv.profiles.detector import BrandProfile, detect_brand_profile
from opentv.tui.fallback import FallbackLineEngine
from opentv.tui.terminal import TerminalController


class AppState(str, Enum):
    MAIN_MENU = "main_menu"
    CONNECT_WIZARD = "connect_wizard"
    LAYOUT_MANAGER = "layout_manager"
    HDMI_MANAGER = "hdmi_manager"
    SETTINGS_TOGGLES = "settings_toggles"
    DEBLOAT_ASSISTANT = "debloat_assistant"
    DEPLOY_LAUNCHER = "deploy_launcher"
    EXIT = "exit"


class KeyCode(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    HOME = auto()
    END = auto()
    ENTER = auto()
    SPACE = auto()
    BACKSPACE = auto()
    TAB = auto()
    ESC = auto()
    CHAR = auto()


class KeyEvent:
    def __init__(self, code: KeyCode, char: str = "") -> None:
        self.code = code
        self.char = char


class RawTerminalEngine:
    """Manages raw terminal mode cross-platform and decodes keystrokes."""

    def __init__(self, stdin: Optional[Any] = None) -> None:
        self.stdin = stdin or sys.stdin
        self._orig_termios = None

    def __enter__(self) -> RawTerminalEngine:
        if sys.platform != "win32" and hasattr(self.stdin, "fileno"):
            try:
                import termios
                import tty

                fd = self.stdin.fileno()
                self._orig_termios = termios.tcgetattr(fd)
                tty.setcbreak(fd)
            except Exception:
                self._orig_termios = None
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if sys.platform != "win32" and self._orig_termios is not None:
            try:
                import termios

                termios.tcsetattr(
                    self.stdin.fileno(), termios.TCSADRAIN, self._orig_termios
                )
            except Exception:
                pass

    def read_key(self) -> KeyEvent:
        """Reads and decodes a single keystroke cross-platform."""
        if sys.platform == "win32":
            try:
                import msvcrt

                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    ch2 = msvcrt.getwch()
                    mapping = {
                        "H": KeyCode.UP,
                        "P": KeyCode.DOWN,
                        "K": KeyCode.LEFT,
                        "M": KeyCode.RIGHT,
                        "I": KeyCode.PAGE_UP,
                        "Q": KeyCode.PAGE_DOWN,
                        "G": KeyCode.HOME,
                        "O": KeyCode.END,
                    }
                    return KeyEvent(mapping.get(ch2, KeyCode.CHAR), ch2)
                if ch in ("\r", "\n"):
                    return KeyEvent(KeyCode.ENTER)
                if ch == " ":
                    return KeyEvent(KeyCode.SPACE)
                if ch == "\x08":
                    return KeyEvent(KeyCode.BACKSPACE)
                if ch == "\t":
                    return KeyEvent(KeyCode.TAB)
                if ch == "\x1b":
                    return KeyEvent(KeyCode.ESC)
                return KeyEvent(KeyCode.CHAR, ch)
            except Exception:
                return KeyEvent(KeyCode.ESC)
        else:
            try:
                ch = self.stdin.read(1)
                if not ch:
                    return KeyEvent(KeyCode.ESC)
                if ch == "\x1b":
                    import select

                    r, _, _ = select.select([self.stdin], [], [], 0.05)
                    if not r:
                        return KeyEvent(KeyCode.ESC)
                    seq = self.stdin.read(1)
                    if seq == "[":
                        code = self.stdin.read(1)
                        if code == "A":
                            return KeyEvent(KeyCode.UP)
                        if code == "B":
                            return KeyEvent(KeyCode.DOWN)
                        if code == "C":
                            return KeyEvent(KeyCode.RIGHT)
                        if code == "D":
                            return KeyEvent(KeyCode.LEFT)
                        if code == "H":
                            return KeyEvent(KeyCode.HOME)
                        if code == "F":
                            return KeyEvent(KeyCode.END)
                        if code in ("1", "5", "6"):
                            trailer = self.stdin.read(1)
                            if code == "5" and trailer == "~":
                                return KeyEvent(KeyCode.PAGE_UP)
                            if code == "6" and trailer == "~":
                                return KeyEvent(KeyCode.PAGE_DOWN)
                    return KeyEvent(KeyCode.ESC)
                if ch in ("\r", "\n"):
                    return KeyEvent(KeyCode.ENTER)
                if ch == " ":
                    return KeyEvent(KeyCode.SPACE)
                if ch in ("\x7f", "\x08"):
                    return KeyEvent(KeyCode.BACKSPACE)
                if ch == "\t":
                    return KeyEvent(KeyCode.TAB)
                return KeyEvent(KeyCode.CHAR, ch)
            except Exception:
                return KeyEvent(KeyCode.ESC)


class OpenTVApp:
    """
    Main TUI Application Controller.
    Seamlessly executes in ANSI VT100 interactive mode or FallbackLineEngine non-TTY mode.
    """

    def __init__(
        self,
        target: Optional[str] = None,
        adb_path: str = "adb",
        mode: str = "auto",  # "auto", "interactive", "line"
        stdin: Optional[Any] = None,
        stdout: Optional[Any] = None,
        cmd_runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
        apk_path: Optional[str] = None,
        output_dir: str = ".",
        force_fallback: bool = False,
    ) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.terminal = TerminalController(stdin=self.stdin, stdout=self.stdout)
        self.fallback = FallbackLineEngine(
            input_fn=lambda prompt="": (
                self.stdout.write(prompt),
                self.stdout.flush(),
                self.stdin.readline(),
            )[2].strip(),
            output_fn=lambda msg="": (
                self.stdout.write(str(msg) + "\n"),
                self.stdout.flush(),
            ),
        )
        self.adb = AdbClient(adb_path=adb_path, default_device=target)
        self.cmd_runner = cmd_runner or self._default_cmd_runner
        self.output_dir = Path(output_dir)
        self.apk_path = apk_path

        # Core Engines
        self.safety_db = PackageSafetyDB()
        self.guardrails = GuardrailsEngine(safety_db=self.safety_db)
        self.rollback = RollbackEngine()
        self.audit_logger = AuditLogger(log_dir=self.output_dir)
        self.device_mgr = DeviceManager(
            adb_wrapper=self.adb, default_serial=target, runner=self.cmd_runner
        )
        self.deployer = LauncherDeployer(
            adb_wrapper=self.adb, default_serial=target, runner=self.cmd_runner
        )

        # Device & Config State
        self.target_device: Optional[str] = target
        self.device_info: Optional[DeviceInfo] = None
        self.device_properties: Dict[str, str] = {}
        self.installed_packages: List[str] = []
        self.disabled_packages: Set[str] = set()
        self.brand_profile: Optional[BrandProfile] = None
        self.current_config: LauncherConfig = create_default_config()

        # Navigation State
        self.state: AppState = AppState.MAIN_MENU
        self.status_message: str = ""

        # Determine interactive vs line mode
        if force_fallback or mode == "line":
            self.interactive = False
        elif mode == "interactive":
            self.interactive = True
        else:  # "auto"
            self.interactive = bool(self.terminal.is_tty)

        # If initial target provided, auto-interrogate
        if self.target_device:
            self.interrogate_device()

    def _default_cmd_runner(self, cmd: List[str]) -> Tuple[int, str, str]:
        """Executes a command list via subprocess without shell=True."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except Exception as e:
            return 1, "", str(e)

    def run(self) -> int:
        """Application main entry loop."""
        if not self.interactive:
            return self._run_fallback_loop()
        try:
            return self._run_interactive_loop()
        except Exception:
            # If raw mode failed unexpectedly, fall back to line engine
            return self._run_fallback_loop()

    # -------------------------------------------------------------------------
    # Device Connection & Interrogation Methods
    # -------------------------------------------------------------------------

    def scan_devices(self) -> List[AdbDevice]:
        """Lists connected devices via DeviceManager."""
        try:
            return self.device_mgr.list_connected_devices()
        except Exception:
            return []

    def connect_target(self, host: str, port: int = 5555) -> bool:
        """Connects to a network device via DeviceManager."""
        success, msg = self.device_mgr.connect(host, port=port)
        if success:
            self.target_device = f"{host}:{port}"
            self.adb.default_device = self.target_device
            self.device_mgr.default_serial = self.target_device
            self.deployer.default_serial = self.target_device
            self.interrogate_device()
            self.status_message = f"Connected to {self.target_device}"
            return True
        self.status_message = f"Connection failed: {msg}"
        return False

    def pair_target(self, host: str, port: int, code: str) -> bool:
        """Pairs with Android 11+ Wi-Fi debugging via DeviceManager."""
        success, msg = self.device_mgr.pair(host, code, port=port)
        if success:
            self.status_message = f"Successfully paired to {host}:{port}"
            return True
        self.status_message = f"Pairing failed: {msg}"
        return False

    def interrogate_device(self) -> None:
        """Queries properties and installed packages to detect BrandProfile."""
        if not self.target_device:
            return
        try:
            self.device_properties = self.device_mgr.get_properties(self.target_device)
        except Exception:
            self.device_properties = {}

        try:
            self.installed_packages = self.device_mgr.get_installed_packages(
                self.target_device, "all"
            )
        except Exception:
            self.installed_packages = []

        try:
            dis = self.device_mgr.get_installed_packages(self.target_device, "disabled")
            self.disabled_packages = set(dis)
        except Exception:
            self.disabled_packages = set()

        try:
            self.device_info = self.device_mgr.get_device_info(
                self.target_device, installed_packages=set(self.installed_packages)
            )
            self.brand_profile = self.device_info.profile
        except Exception:
            self.brand_profile = detect_brand_profile(
                self.device_properties, set(self.installed_packages)
            )

    # -------------------------------------------------------------------------
    # Debloat Pipeline Methods
    # -------------------------------------------------------------------------

    def get_categorized_packages(self) -> Dict[SafetyCategory, List[str]]:
        """Groups installed packages by SafetyCategory."""
        brand = self.brand_profile.brand_id if self.brand_profile else "generic"
        res: Dict[SafetyCategory, List[str]] = {cat: [] for cat in SafetyCategory}
        for pkg in self.installed_packages:
            cat = self.safety_db.categorize(pkg, brand)
            res[cat].append(pkg)
        return res

    def execute_debloat(
        self, packages: List[str]
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Validates guardrails, disables safe packages, generates rollback scripts,
        and logs audit trail.
        Returns (successful_disables, guardrail_violations).
        """
        if not self.target_device:
            return [], [("", "No target device connected")]

        brand = self.brand_profile.brand_id if self.brand_profile else "generic"
        is_gtv = (
            brand == "ccwgtv"
            or "com.google.android.apps.tv.launcherx" in self.installed_packages
        )
        provisioned = int(
            self.device_properties.get("settings.global.device_provisioned", "1")
        ) if self.device_properties.get("settings.global.device_provisioned", "1").isdigit() else 1
        is_oled = self.brand_profile.has_oled_protection if self.brand_profile else False

        permitted, violations = self.guardrails.filter_safe_to_disable(
            packages,
            brand_id=brand,
            installed_packages=self.installed_packages,
            disabled_packages=self.disabled_packages,
            is_google_tv=is_gtv,
            device_provisioned=provisioned,
            is_oled=is_oled,
        )

        if violations and not permitted:
            return [], violations

        successful: List[str] = []
        for pkg in permitted:
            cmd = self.adb.build_disable_package_cmd(
                pkg, target_device=self.target_device
            )
            code, out, err = self.cmd_runner(cmd)
            verified = code == 0
            if verified:
                successful.append(pkg)
                self.disabled_packages.add(pkg)
                # Update on-device registry
                self.cmd_runner(
                    self.adb.build_shell_cmd(
                        [
                            "sh",
                            "-c",
                            f"echo '{pkg}' >> /data/local/tmp/opentv-disabled.txt",
                        ],
                        target_device=self.target_device,
                    )
                )

            self.audit_logger.record_disable(
                device_id=self.target_device,
                package_name=pkg,
                brand_profile=brand,
                category=self.safety_db.categorize(pkg, brand).value,
                exit_code=code,
                verified=verified,
                details=out.strip() if verified else err.strip(),
            )

        if successful:
            self.rollback.write_rollback_scripts(
                self.output_dir,
                list(self.disabled_packages),
                target_device=self.target_device,
            )

        return successful, violations

    # -------------------------------------------------------------------------
    # Deployment Pipeline Methods
    # -------------------------------------------------------------------------

    def deploy_launcher(
        self, apk_file: Optional[str] = None
    ) -> List[Tuple[str, bool, str]]:
        """
        Executes the 5-step launcher deployment workflow:
        1. Push config to /sdcard/OpenTV/config.json
        2. Install APK
        3. Set default Home activity
        4. Verify Home activity resolution
        5. Broadcast RELOAD_CONFIG
        """
        results: List[Tuple[str, bool, str]] = []
        target = self.target_device
        if not target:
            return [("Pre-check", False, "No target device connected")]

        apk = apk_file or self.apk_path or "OpenTV.apk"

        # 1. Push Config
        res_push = self.deployer.push_config(target, self.current_config)
        results.append(
            (
                "Push Configuration",
                res_push.success,
                res_push.message if res_push.success else res_push.output,
            )
        )

        # 2. Install APK
        res_inst = self.deployer.install_apk(target, apk)
        results.append(
            (
                "Install Launcher APK",
                res_inst.success,
                res_inst.message if res_inst.success else res_inst.output,
            )
        )

        # 3. Set Home Activity
        res_home = self.deployer.set_home_activity(target)
        results.append(
            (
                "Set Default Home Activity",
                res_home.success,
                res_home.message if res_home.success else res_home.output,
            )
        )

        # 4. Verify Home Activity
        is_home, current_home = self.deployer.verify_home(target)
        results.append(
            (
                "Verify Home Activity Resolution",
                is_home,
                f"Active Home: {current_home}",
            )
        )

        # 5. Broadcast Reload
        res_rel = self.deployer.reload_config(target)
        results.append(
            (
                "Broadcast Config Reload",
                res_rel.success,
                res_rel.message if res_rel.success else res_rel.output,
            )
        )

        return results

    # -------------------------------------------------------------------------
    # 6-Column Grid ASCII Preview Generator
    # -------------------------------------------------------------------------

    def generate_grid_preview(self, apps: List[str], columns: int = 6) -> str:
        """Renders an ASCII visualization of the TV 6-column grid."""
        if not apps:
            return "[No visible apps configured for home screen]"

        col_width = 16
        lines: List[str] = []
        divider = "+" + "+".join(["-" * (col_width + 2)] * columns) + "+"
        lines.append(divider)

        for i in range(0, len(apps), columns):
            row_items = apps[i : i + columns]
            row_cells = []
            for j in range(columns):
                if j < len(row_items):
                    pkg = row_items[j]
                    label = get_app_name(pkg)[:col_width]
                    row_cells.append(f" {i + j + 1}. {label}".ljust(col_width + 2))
                else:
                    row_cells.append(" [Empty]".ljust(col_width + 2))
            lines.append("|" + "|".join(row_cells) + "|")
            lines.append(divider)

        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Fallback Line Engine Loop (Non-TTY / CI)
    # -------------------------------------------------------------------------

    def _run_fallback_loop(self) -> int:
        """Runs prompt-based line workflow using FallbackLineEngine."""
        self.fallback.output_fn("====================================================")
        self.fallback.output_fn("         OpenTV Companion Manager (Line Mode)       ")
        self.fallback.output_fn("====================================================")

        while True:
            # Main Menu
            status_target = self.target_device or "Disconnected"
            status_brand = (
                self.brand_profile.display_name if self.brand_profile else "Generic"
            )
            title = (
                f"OpenTV Menu [Target: {status_target} | Profile: {status_brand}]"
            )
            options = [
                "Connection Wizard (USB & Wi-Fi)",
                "Home Screen Layout Manager",
                "Debloat Assistant",
                "HDMI Input Manager",
                "Deploy Launcher",
                "Exit",
            ]
            choice = self.fallback.prompt_choice(title, options, default_index=0)

            if choice == 0:  # Connection Wizard
                self._fallback_connect_wizard()
            elif choice == 1:  # Layout Manager
                self._fallback_layout_manager()
            elif choice == 2:  # Debloat Assistant
                self._fallback_debloat_assistant()
            elif choice == 3:  # HDMI Input Manager
                self._fallback_hdmi_manager()
            elif choice == 4:  # Deploy Launcher
                self._fallback_deploy_launcher()
            elif choice == 5:  # Exit
                self.fallback.output_fn("Exiting OpenTV Companion.")
                return 0

    def _fallback_connect_wizard(self) -> None:
        self.fallback.output_fn("\n--- Connection Wizard ---")
        devices = self.scan_devices()
        online = [d for d in devices if d.state == "device"]
        options = []
        if online:
            self.fallback.output_fn(f"Discovered {len(online)} online device(s):")
            for i, d in enumerate(online):
                self.fallback.output_fn(f"  [{i + 1}] {d.serial} ({d.model})")
            options.extend([f"Use {d.serial}" for d in online])

        options.extend([
            "Scan Local Network (mDNS/SSDP)",
            "Manual Wi-Fi Connect",
            "Wi-Fi Pair (Android 11+)",
            "Cancel / Back to Menu",
        ])

        opt = self.fallback.prompt_choice(
            "Select Connection Method:",
            options,
            default_index=0,
        )
        num_attached = len(online)
        if opt < num_attached:
            self.target_device = online[opt].serial
            self.interrogate_device()
            self.fallback.output_fn(f"Target selected: {self.target_device}")
            return

        method_idx = opt - num_attached
        if method_idx == 0:  # Scan Local Network (mDNS/SSDP)
            self.fallback.output_fn("\nScanning local network for Android TVs (timeout 3.0s)...")
            try:
                from opentv.core.discovery import discover_devices
                discovered = discover_devices(timeout=3.0)
            except Exception as exc:
                discovered = []
                self.fallback.output_fn(f"Scan failed: {exc}")

            if not discovered:
                self.fallback.output_fn("No Android TV devices discovered on the network.")
                return

            dev_opts = [
                f"{d.ip}:{d.port} - {d.model or d.hostname or 'Android TV'} ({d.source})"
                for d in discovered
            ] + ["Cancel"]
            sel = self.fallback.prompt_choice("Select Discovered TV to Connect:", dev_opts, default_index=0)
            if sel < len(discovered):
                picked = discovered[sel]
                self.connect_target(picked.ip, picked.port)
                self.fallback.output_fn(self.status_message)
            return

        elif method_idx == 1:  # Manual Wi-Fi Connect
            ip = self.fallback.prompt_text("Enter TV IP Address", default="192.168.1.50")
            port_s = self.fallback.prompt_text("Enter ADB Port", default="5555")
            try:
                port = int(port_s)
            except ValueError:
                port = 5555
            self.connect_target(ip, port)
            self.fallback.output_fn(self.status_message)

        elif method_idx == 2:  # Wi-Fi Pair
            self._fallback_pair()
            return

    def _fallback_pair(self) -> None:
        addr = self.fallback.prompt_text("Enter TV Pairing Address (IP:port)", default="192.168.1.50:38450")
        code = self.fallback.prompt_text("Enter 6-digit Pairing Code", default="123456")
        if ":" in addr:
            h, p = addr.split(":", 1)
            port = int(p) if p.isdigit() else 5555
            self.pair_target(h, port, code)
            self.fallback.output_fn(self.status_message)
            # Then connect
            self.connect_target(h, 5555)
            self.fallback.output_fn(self.status_message)

    def _fallback_layout_manager(self) -> None:
        self.fallback.output_fn("\n--- Home Screen Layout Manager ---")
        if not self.target_device:
            self.fallback.output_fn("Please connect a target device first.")
            return

        available_apps = self.installed_packages or self.current_config.apps
        # Filter to likely launchables
        options = [p for p in available_apps if not p.startswith("android")]
        if not options:
            options = self.current_config.apps

        preselected = [i for i, p in enumerate(options) if p in self.current_config.apps]
        display_options = [format_app_display(p) for p in options]
        chosen_indices = self.fallback.prompt_multiselect(
            "Select apps visible on home screen (comma-separated numbers)",
            display_options,
            preselected=preselected,
        )
        self.current_config.apps = [options[i] for i in chosen_indices]
        self.fallback.output_fn(f"Updated visible apps: {len(self.current_config.apps)}")
        self.fallback.output_fn("Live 6-column TV grid preview:")
        self.fallback.output_fn(self.generate_grid_preview(self.current_config.apps))

    def _fallback_debloat_assistant(self) -> None:
        self.fallback.output_fn("\n--- Debloat Assistant ---")
        if not self.target_device:
            self.fallback.output_fn("Please connect a target device first.")
            return

        categorized = self.get_categorized_packages()
        safe_pkgs = categorized.get(SafetyCategory.SAFE, [])
        self.fallback.output_fn(
            f"Package Summary: SAFE={len(safe_pkgs)}, KEEP={len(categorized.get(SafetyCategory.KEEP, []))}, "
            f"NEVER={len(categorized.get(SafetyCategory.NEVER, []))}, REVIEW={len(categorized.get(SafetyCategory.REVIEW, []))}"
        )

        action = self.fallback.prompt_choice(
            "Select debloat action:",
            ["Disable All SAFE Packages (Recommended)", "Specify Package List", "Cancel"],
            default_index=0,
        )

        candidates: List[str] = []
        if action == 0:
            candidates = safe_pkgs
        elif action == 1:
            raw = self.fallback.prompt_text("Enter package names separated by comma", default="")
            candidates = [p.strip() for p in raw.split(",") if p.strip()]
        else:
            return

        if not candidates:
            self.fallback.output_fn("No candidate packages selected.")
            return

        self.fallback.output_fn(f"Evaluating {len(candidates)} package(s) against safety guardrails...")
        successful, violations = self.execute_debloat(candidates)
        if violations:
            self.fallback.output_fn(f"Guardrail Violations ({len(violations)}):")
            for pkg, reason in violations:
                self.fallback.output_fn(f"  [BLOCKED] {pkg}: {reason}")
        if successful:
            self.fallback.output_fn(f"Successfully disabled {len(successful)} package(s).")
            self.fallback.output_fn(f"Rollback scripts written to: {self.output_dir}")

    def _fallback_hdmi_manager(self) -> None:
        self.fallback.output_fn("\n--- HDMI Input Manager ---")
        for i, hdmi in enumerate(self.current_config.hdmi):
            vis = "Visible" if hdmi.visible else "Hidden"
            self.fallback.output_fn(f"  [{i + 1}] {hdmi.id}: '{hdmi.title}' ({vis})")

        choice = self.fallback.prompt_choice(
            "Select an action:",
            ["Edit HDMI input label", "Toggle HDMI input visibility", "Back"],
            default_index=2,
        )
        if choice in (0, 1):
            idx = self.fallback.prompt_choice(
                "Select port to modify:",
                [f"{h.id} ({h.title})" for h in self.current_config.hdmi],
                default_index=0,
            )
            if choice == 0:
                new_title = self.fallback.prompt_text(
                    f"Enter new label for {self.current_config.hdmi[idx].id}",
                    default=self.current_config.hdmi[idx].title,
                )
                self.current_config.hdmi[idx].title = new_title
                self.fallback.output_fn(f"Updated label: {new_title}")
            elif choice == 1:
                self.current_config.hdmi[idx].visible = not self.current_config.hdmi[idx].visible
                vis_str = "Visible" if self.current_config.hdmi[idx].visible else "Hidden"
                self.fallback.output_fn(f"Set {self.current_config.hdmi[idx].id} to {vis_str}")

    def _fallback_deploy_launcher(self) -> None:
        self.fallback.output_fn("\n--- Deploy Launcher ---")
        if not self.target_device:
            self.fallback.output_fn("Please connect a target device first.")
            return

        apk = self.fallback.prompt_text(
            "Enter path to launcher APK",
            default=self.apk_path or "OpenTV.apk",
        )
        results = self.deploy_launcher(apk_file=apk)
        for step, success, msg in results:
            tag = "[OK]  " if success else "[FAIL]"
            self.fallback.output_fn(f"  {tag} {step}: {msg}")

    # -------------------------------------------------------------------------
    # Interactive ANSI VT100 Loop
    # -------------------------------------------------------------------------

    def _run_interactive_loop(self) -> int:
        """Runs the interactive ANSI VT100 dashboard with raw key events."""
        with RawTerminalEngine(stdin=self.stdin) as raw_engine:
            self.state = AppState.MAIN_MENU
            while self.state != AppState.EXIT:
                if self.state == AppState.MAIN_MENU:
                    self._draw_main_menu()
                    key = raw_engine.read_key()
                    if key.char in ("1", "c"):
                        self.state = AppState.CONNECT_WIZARD
                    elif key.char in ("2", "l"):
                        self.state = AppState.LAYOUT_MANAGER
                    elif key.char in ("3", "d"):
                        self.state = AppState.DEBLOAT_ASSISTANT
                    elif key.char in ("4", "h"):
                        self.state = AppState.HDMI_MANAGER
                    elif key.char in ("5", "p"):
                        self.state = AppState.DEPLOY_LAUNCHER
                    elif key.char in ("6", "q") or key.code == KeyCode.ESC:
                        self.state = AppState.EXIT

                elif self.state == AppState.CONNECT_WIZARD:
                    self._run_interactive_connect(raw_engine)
                    self.state = AppState.MAIN_MENU

                elif self.state == AppState.LAYOUT_MANAGER:
                    self._run_interactive_layout(raw_engine)
                    self.state = AppState.MAIN_MENU

                elif self.state == AppState.HDMI_MANAGER:
                    self._run_interactive_hdmi(raw_engine)
                    self.state = AppState.MAIN_MENU

                elif self.state == AppState.DEBLOAT_ASSISTANT:
                    self._run_interactive_debloat(raw_engine)
                    self.state = AppState.MAIN_MENU

                elif self.state == AppState.DEPLOY_LAUNCHER:
                    self._run_interactive_deploy(raw_engine)
                    self.state = AppState.MAIN_MENU

        self.stdout.write(self.terminal.clear_screen())
        self.stdout.write("Thank you for using OpenTV Companion.\n")
        self.stdout.flush()
        return 0

    def _draw_main_menu(self) -> None:
        """Renders the main menu dashboard header and navigation options."""
        out: List[str] = [self.terminal.clear_screen()]
        out.append(self.terminal.bold("================================================================================"))
        out.append(self.terminal.bold("                        OpenTV Companion Manager v1.0.0                         "))
        out.append(self.terminal.bold("================================================================================"))

        # Status Header
        tgt = self.target_device or "Disconnected"
        brand_name = self.brand_profile.display_name if self.brand_profile else "Generic"
        oled_str = "Enabled" if (self.brand_profile and self.brand_profile.has_oled_protection) else "Disabled"
        dis_count = len(self.disabled_packages)

        out.append(f"  Target Device:  {self.terminal.bold(tgt)}")
        out.append(f"  Brand Profile:  {self.terminal.bold(brand_name)} (OLED Protection: {oled_str})")
        out.append(f"  Visible Apps:   {len(self.current_config.apps)} apps | HDMI Ports: {len(self.current_config.hdmi)} ports")
        out.append(f"  Debloat Status: {dis_count} package(s) disabled on device")
        if self.status_message:
            out.append(f"  Notice:         {self.status_message}")
        out.append("--------------------------------------------------------------------------------")
        out.append("  Main Menu Options:")
        out.append("    [1] Connect Device       - USB auto-detect & Wi-Fi connect / pairing")
        out.append("    [2] Layout Manager       - Select home apps, reorder tiles, 6-col live preview")
        out.append("    [3] Debloat Assistant    - 4-tier package view, safe debloat, rollback scripts")
        out.append("    [4] HDMI Input Manager   - Custom labels and hardware passthrough URIs")
        out.append("    [5] Deploy Launcher      - Push config, install APK, set default Home")
        out.append("    [6] Exit                 - Quit application")
        out.append("--------------------------------------------------------------------------------")
        out.append("  Press [1-6] or corresponding hotkey to enter a workflow, or [Q] to quit: ")
        self.stdout.write("\n".join(out))
        self.stdout.flush()

    def _run_interactive_connect(self, raw_engine: RawTerminalEngine) -> None:
        """Interactive Connection Wizard screen."""
        devices = self.scan_devices()
        online = [d for d in devices if d.state == "device"]
        if online and not self.target_device:
            self.target_device = online[0].serial
            self.interrogate_device()
            self.status_message = f"Auto-selected device {self.target_device}"
            return

        out: List[str] = [self.terminal.clear_screen()]
        out.append(self.terminal.bold("--- Connection Wizard ---"))
        if online:
            out.append(f"Discovered {len(online)} attached device(s):")
            for i, d in enumerate(online):
                out.append(f"  [{i + 1}] {d.serial} ({d.model})")
        else:
            out.append("No USB devices detected.")
        out.append("\nOptions: [S] Scan Local Network, [C] Connect to IP:5555, [P] Pair Wi-Fi (Android 11+), [B] Back to Menu")
        out.append("Choice: ")
        self.stdout.write("\n".join(out))
        self.stdout.flush()

        k = raw_engine.read_key()
        if k.char in ("1", "2", "3") and int(k.char) <= len(online):
            self.target_device = online[int(k.char) - 1].serial
            self.interrogate_device()
            self.status_message = f"Selected {self.target_device}"
        elif k.char in ("s", "S"):
            self._run_interactive_network_scan(raw_engine)
        elif k.char in ("c", "C"):
            # Simple prompt
            self.stdout.write("\nEnter IP address [192.168.1.50]: ")
            self.stdout.flush()
            ip = self.stdin.readline().strip() or "192.168.1.50"
            self.connect_target(ip, 5555)

    def _run_interactive_network_scan(self, raw_engine: RawTerminalEngine) -> None:
        """Executes mDNS/SSDP scan and displays interactive device selection list."""
        self.stdout.write(self.terminal.clear_screen())
        self.stdout.write(self.terminal.bold("--- Scanning Local Network for Android TVs ---\n\n"))
        self.stdout.write("Broadcasting mDNS & SSDP queries across local subnet...\n")
        self.stdout.write("Please wait up to 3 seconds...\n")
        self.stdout.flush()

        try:
            from opentv.core.discovery import discover_devices
            discovered = discover_devices(timeout=3.0)
        except Exception as exc:
            discovered = []
            self.status_message = f"Discovery error: {exc}"

        if not discovered:
            self.stdout.write("\nNo Android TV devices found on local network.\n")
            self.stdout.write("Ensure your TV is powered on and Network Debugging is active.\n")
            self.stdout.write("Press any key to return...")
            self.stdout.flush()
            raw_engine.read_key()
            return

        self.stdout.write(self.terminal.clear_screen())
        out = [
            self.terminal.bold("--- Discovered Local Android TVs ---"),
            f"Found {len(discovered)} device(s) on local subnet:\n",
        ]
        for idx, dev in enumerate(discovered, 1):
            name = dev.model or dev.hostname or "Android TV"
            out.append(f"  [{idx}] {dev.ip}:{dev.port} - {name} ({dev.source})")

        out.append("\nPress [1-9] to connect, or [B/Esc] to cancel: ")
        self.stdout.write("\n".join(out))
        self.stdout.flush()

        k = raw_engine.read_key()
        if k.char.isdigit():
            idx = int(k.char) - 1
            if 0 <= idx < len(discovered):
                picked = discovered[idx]
                self.connect_target(picked.ip, picked.port)

    def _run_interactive_layout(self, raw_engine: RawTerminalEngine) -> None:
        """Interactive Home Screen Layout Manager with live 6-column grid."""
        available = self.installed_packages or self.current_config.apps
        apps = [p for p in available if not p.startswith("android")]
        if not apps:
            apps = self.current_config.apps

        cursor = 0
        while True:
            out: List[str] = [self.terminal.clear_screen()]
            out.append(self.terminal.bold("--- Home Screen Layout Manager ---"))
            out.append("Live 6-Column TV Grid Preview:")
            out.append(self.generate_grid_preview(self.current_config.apps))
            out.append("\nApp List ([Space] Toggle, [U/+] Move Up, [D/-] Move Down, [B/Esc] Back):")

            start = max(0, cursor - 5)
            end = min(len(apps), start + 12)
            term_cols = shutil.get_terminal_size(fallback=(80, 24)).columns
            max_label_len = max(20, term_cols - 12)
            for idx in range(start, end):
                pkg = apps[idx]
                is_vis = pkg in self.current_config.apps
                chk = "[X]" if is_vis else "[ ]"
                prefix = "> " if idx == cursor else "  "
                formatted_label = format_app_display(pkg, max_width=max_label_len)
                line = f"{prefix}{chk} {idx + 1}. {formatted_label}"
                if idx == cursor:
                    out.append(self.terminal.bold(self.terminal.invert(line)))
                else:
                    out.append(line)

            self.stdout.write("\n".join(out))
            self.stdout.flush()

            k = raw_engine.read_key()
            if k.code == KeyCode.UP:
                cursor = max(0, cursor - 1)
            elif k.code == KeyCode.DOWN:
                cursor = min(len(apps) - 1, cursor + 1)
            elif k.code == KeyCode.SPACE:
                pkg = apps[cursor]
                if pkg in self.current_config.apps:
                    self.current_config.apps.remove(pkg)
                else:
                    self.current_config.apps.append(pkg)
            elif k.char in ("u", "U", "+"):
                pkg = apps[cursor]
                if pkg in self.current_config.apps:
                    i = self.current_config.apps.index(pkg)
                    if i > 0:
                        self.current_config.apps[i], self.current_config.apps[i - 1] = (
                            self.current_config.apps[i - 1],
                            self.current_config.apps[i],
                        )
            elif k.char in ("d", "D", "-"):
                pkg = apps[cursor]
                if pkg in self.current_config.apps:
                    i = self.current_config.apps.index(pkg)
                    if i < len(self.current_config.apps) - 1:
                        self.current_config.apps[i], self.current_config.apps[i + 1] = (
                            self.current_config.apps[i + 1],
                            self.current_config.apps[i],
                        )
            elif k.char in ("b", "B", "q") or k.code == KeyCode.ESC:
                break

    def _run_interactive_hdmi(self, raw_engine: RawTerminalEngine) -> None:
        """Interactive HDMI Input Manager."""
        cursor = 0
        while True:
            out: List[str] = [self.terminal.clear_screen()]
            out.append(self.terminal.bold("--- HDMI Input Manager ---"))
            out.append("Configure input titles and visibility on launcher:")
            for i, h in enumerate(self.current_config.hdmi):
                chk = "[X]" if h.visible else "[ ]"
                prefix = "> " if i == cursor else "  "
                uri_desc = f"(URI: {h.intent_uri})" if h.intent_uri else ""
                line = f"{prefix}{chk} {h.id}: '{h.title}' {uri_desc}"
                if i == cursor:
                    out.append(self.terminal.bold(self.terminal.invert(line)))
                else:
                    out.append(line)
            out.append("\nControls: [Space] Toggle Visibility, [E] Edit Title, [B/Esc] Back")
            self.stdout.write("\n".join(out))
            self.stdout.flush()

            k = raw_engine.read_key()
            if k.code == KeyCode.UP:
                cursor = max(0, cursor - 1)
            elif k.code == KeyCode.DOWN:
                cursor = min(len(self.current_config.hdmi) - 1, cursor + 1)
            elif k.code == KeyCode.SPACE:
                self.current_config.hdmi[cursor].visible = not self.current_config.hdmi[cursor].visible
            elif k.char in ("e", "E"):
                self.stdout.write(f"\nEnter new title for {self.current_config.hdmi[cursor].id}: ")
                self.stdout.flush()
                nt = self.stdin.readline().strip()
                if nt:
                    self.current_config.hdmi[cursor].title = nt
            elif k.char in ("b", "B") or k.code == KeyCode.ESC:
                break

    def _run_interactive_debloat(self, raw_engine: RawTerminalEngine) -> None:
        """Interactive Debloat Assistant."""
        categorized = self.get_categorized_packages()
        safe_pkgs = categorized.get(SafetyCategory.SAFE, [])

        out: List[str] = [self.terminal.clear_screen()]
        out.append(self.terminal.bold("--- Debloat Assistant ---"))
        out.append(
            f"Package Catalog Breakdown for {self.brand_profile.display_name if self.brand_profile else 'Generic'}:"
        )
        out.append(f"  [SAFE]   {len(safe_pkgs)} known safe bloat packages")
        out.append(f"  [KEEP]   {len(categorized.get(SafetyCategory.KEEP, []))} optional user packages")
        out.append(f"  [NEVER]  {len(categorized.get(SafetyCategory.NEVER, []))} critical system packages (protected)")
        out.append(f"  [REVIEW] {len(categorized.get(SafetyCategory.REVIEW, []))} third-party / user packages")
        out.append("\nActions:")
        out.append("  [S] One-Key Safe Debloat (Disable all confirmed SAFE packages)")
        out.append("  [B] Back to Main Menu")
        out.append("Choice: ")
        self.stdout.write("\n".join(out))
        self.stdout.flush()

        k = raw_engine.read_key()
        if k.char in ("s", "S"):
            if safe_pkgs:
                self.stdout.write(f"\nDisabling {len(safe_pkgs)} SAFE packages...\n")
                self.stdout.flush()
                succ, viol = self.execute_debloat(safe_pkgs)
                self.status_message = f"Disabled {len(succ)} safe packages. Rollback generated."
            else:
                self.status_message = "No safe bloat packages detected on device."

    def _run_interactive_deploy(self, raw_engine: RawTerminalEngine) -> None:
        """Interactive Deploy Launcher Screen."""
        out: List[str] = [self.terminal.clear_screen()]
        out.append(self.terminal.bold("--- Deploy Launcher ---"))
        out.append(f"Target: {self.target_device or 'None'}")
        out.append("Actions to perform:")
        out.append("  1. Push configuration JSON (/sdcard/OpenTV/config.json)")
        out.append("  2. Install OpenTV Release APK")
        out.append("  3. Set OpenTV as default Home activity")
        out.append("  4. Verify Home activity resolution")
        out.append("  5. Broadcast configuration reload")
        out.append("\nPress [Enter] to proceed, [B/Esc] to cancel: ")
        self.stdout.write("\n".join(out))
        self.stdout.flush()

        k = raw_engine.read_key()
        if k.code == KeyCode.ENTER:
            results = self.deploy_launcher()
            res_lines = ["\nDeployment Results:"]
            for step, ok, msg in results:
                tag = "[OK]  " if ok else "[FAIL]"
                res_lines.append(f"  {tag} {step}: {msg}")
            res_lines.append("\nPress any key to return to menu...")
            self.stdout.write("\n".join(res_lines))
            self.stdout.flush()
            raw_engine.read_key()
            self.status_message = "Deployment completed."
