"""
OpenTV Companion CLI Subcommand Parser & Dispatcher.
PROJECT.md Feature F2.7:
Non-interactive, scriptable command-line interface for OpenTV Android TV launcher management,
device pairing, configuration generation, APK deployment, and safe debloating with guardrails.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from opentv import __version__
from opentv.core.adb import AdbClient, AdbDevice
from opentv.core.app_names import (
    format_app_display,
    get_app_category,
    get_app_metadata,
    get_app_name,
)
from opentv.core.config import (
    DEFAULT_THEME,
    HdmiInputConfig,
    LauncherConfig,
    OledProtectionConfig,
    create_default_config,
)
from opentv.core.deployer import LauncherDeployer
from opentv.core.device import AmbiguousDeviceError, DeviceManager, NoDeviceConnectedError
from opentv.debloat.audit import AuditLogger
from opentv.debloat.database import PackageSafetyDB, SafetyCategory
from opentv.debloat.guardrails import GuardrailViolation, GuardrailsEngine
from opentv.debloat.rollback import RollbackEngine
from opentv.profiles.detector import detect_brand_profile

# Standard Exit Codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_DEVICE_NOT_FOUND = 3
EXIT_GUARDRAIL_VIOLATION = 4


def default_subprocess_runner(
    cmd: List[str], timeout: Optional[float] = None
) -> Tuple[int, str, str]:
    """Default production runner using standard subprocess without shell=True."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 1, "", f"Executable not found: '{cmd[0]}'. Ensure ADB is installed and in PATH."
    except Exception as exc:
        return 1, "", f"Subprocess error: {exc}"


def parse_target_address(
    target_str: str, default_port: int = 5555, adb: Optional[AdbClient] = None
) -> Tuple[str, int]:
    """Splits target string into host and port, using default_port if unspecified."""
    target_str = target_str.strip()
    if ":" in target_str:
        host, port_s = target_str.rsplit(":", 1)
        try:
            port = int(port_s)
        except ValueError:
            raise ValueError(f"Invalid port in target: '{port_s}'")
    else:
        host = target_str
        port = default_port

    if adb is not None:
        adb.validate_ip(host)
        adb.validate_port(port)

    return host.strip(), port


def resolve_target_device(
    target_arg: Optional[str],
    adb: AdbClient,
    runner: Callable[[List[str]], Tuple[int, str, str]],
) -> Optional[str]:
    """
    Resolves the target ADB device serial or address.
    Priority:
    1. Explicit `--target` argument
    2. `OPENTV_TARGET` environment variable
    3. Auto-detected single connected device via DeviceManager
    """
    if target_arg and target_arg.strip():
        return target_arg.strip()

    env_target = os.environ.get("OPENTV_TARGET", "").strip()
    if env_target:
        return env_target

    dm = DeviceManager(adb_wrapper=adb, runner=runner)
    try:
        return dm.select_target_device()
    except (NoDeviceConnectedError, AmbiguousDeviceError):
        return None
    except Exception:
        return None


# -------------------------------------------------------------------------
# Subcommand Handlers
# -------------------------------------------------------------------------

def format_device_table(devices: List[Any]) -> str:
    """Renders a clean, formatted ASCII table of discovered Android TV devices."""
    if not devices:
        return "No devices discovered."

    headers = ("#", "IP Address", "Port", "Device Name / Model", "Type", "Source")
    rows: List[Tuple[str, str, str, str, str, str]] = []
    for idx, dev in enumerate(devices, 1):
        name = getattr(dev, "model", "") or getattr(dev, "hostname", "") or "Android TV"
        dtype = getattr(dev, "device_type", "android_tv")
        src = getattr(dev, "source", "mDNS")
        rows.append((str(idx), str(getattr(dev, "ip", "")), str(getattr(dev, "port", 5555)), name, dtype, src))

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_line = "| " + " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"

    lines = [sep, header_line, sep]
    for row in rows:
        lines.append("| " + " | ".join(f"{val:<{col_widths[i]}}" for i, val in enumerate(row)) + " |")
    lines.append(sep)
    return "\n".join(lines)


def run_cli_discovery(
    args: argparse.Namespace,
    adb: AdbClient,
    runner: Callable,
    timeout: float = 3.0,
    auto_prompt: bool = True,
) -> int:
    """Executes network auto-discovery, table formatting, and interactive connection."""
    try:
        from opentv.core.discovery import discover_devices
    except ImportError as exc:
        print(f"Error: Discovery module unavailable: {exc}", file=sys.stderr)
        return EXIT_ERROR

    is_json = getattr(args, "json", False)
    if not is_json:
        print(f"Scanning local network for Android TV devices (mDNS & SSDP, timeout={timeout:.1f}s)...")

    try:
        devices = discover_devices(timeout=timeout)
    except Exception as exc:
        print(f"Discovery error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if is_json:
        serialized = [d.to_dict() if hasattr(d, "to_dict") else vars(d) for d in devices]
        print(json.dumps(serialized, indent=2))
        return EXIT_SUCCESS

    if not devices:
        print(f"\nNo Android TV devices discovered within {timeout:.1f}s.")
        print("Ensure TV is powered on, connected to the same subnet, and has Network Debugging enabled.")
        print("You can connect directly via: opentv connect <IP>:5555")
        return EXIT_DEVICE_NOT_FOUND

    print(f"\nDiscovered {len(devices)} Android TV device(s):")
    print(format_device_table(devices))

    if not auto_prompt:
        print("\nTo connect to a device, run: opentv connect <IP>:5555")
        return EXIT_SUCCESS

    is_atty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
    if not is_atty:
        print(f"\nNon-interactive shell: connect with: opentv connect {devices[0].ip}:{devices[0].port}")
        return EXIT_SUCCESS

    # Interactive selection loop
    while True:
        try:
            choice = input(f"\nSelect a TV to connect [1-{len(devices)}] (or [q] to quit, default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            return EXIT_SUCCESS

        if not choice:
            choice = "1"

        if choice.lower() in ("q", "quit", "exit"):
            print("Cancelled.")
            return EXIT_SUCCESS

        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                selected = devices[idx]
                break

        print(f"Invalid selection: '{choice}'. Enter a number from 1 to {len(devices)}.")

    dm = DeviceManager(adb_wrapper=adb, runner=runner)
    print(f"Connecting to {selected.ip}:{selected.port}...")
    success, message = dm.connect(selected.ip, port=selected.port, timeout=getattr(args, "timeout", 10.0))
    if success:
        print(f"Successfully connected to {selected.ip}:{selected.port}")
        return EXIT_SUCCESS
    else:
        print(f"Connection failed: {message}", file=sys.stderr)
        return EXIT_ERROR


def handle_connect(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Connect to wireless TV target, supporting local network discovery."""
    if getattr(args, "discover", None) is not None or not getattr(args, "target", None):
        if getattr(args, "discover_timeout", None) is not None:
            timeout = float(args.discover_timeout)
        elif getattr(args, "discover", None) is not None and args.discover is not True:
            try:
                timeout = float(args.discover)
            except (ValueError, TypeError):
                timeout = 3.0
        else:
            timeout = 3.0
        return run_cli_discovery(args, adb, runner, timeout=timeout, auto_prompt=True)

    dm = DeviceManager(adb_wrapper=adb, runner=runner)
    try:
        host, port = parse_target_address(args.target, default_port=args.port, adb=adb)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.verbose:
        cmd = adb.build_connect_cmd(host, port)
        print(f"[ADB] {' '.join(cmd)}")

    success, message = dm.connect(host, port=port, timeout=args.timeout)
    if success:
        print(f"Successfully connected to {host}:{port}")
        return EXIT_SUCCESS
    else:
        print(f"Connection failed: {message}", file=sys.stderr)
        return EXIT_ERROR


def handle_discover(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Standalone discovery subcommand handler."""
    timeout = getattr(args, "timeout", 3.0)
    auto_prompt = getattr(args, "connect", False)
    return run_cli_discovery(args, adb, runner, timeout=timeout, auto_prompt=auto_prompt)



def handle_pair(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Android 11+ Wi-Fi pairing wizard."""
    dm = DeviceManager(adb_wrapper=adb, runner=runner)
    if ":" not in args.target:
        print(
            "Error: Target for Wi-Fi pairing must include the port (e.g. 192.168.1.50:38450)",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        host, port = parse_target_address(args.target, adb=adb)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not args.code.isdigit():
        print(f"Error: Pairing code must be numeric digits, got: '{args.code}'", file=sys.stderr)
        return EXIT_USAGE

    if args.verbose:
        cmd = adb.build_pair_cmd(host, port, args.code)
        print(f"[ADB] {' '.join(cmd)}")

    success, message = dm.pair(host, args.code, port=port, timeout=args.timeout)
    if success:
        print(f"Successfully paired to {host}:{port}")
        print(f"You can now connect via: opentv connect {host}:5555")
        return EXIT_SUCCESS
    else:
        print(f"Pairing failed: {message}", file=sys.stderr)
        return EXIT_ERROR


def handle_list_apps(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Lists installed packages with optional filtering and JSON output."""
    target = resolve_target_device(args.target, adb, runner)
    if not target:
        print(
            "Error: No target device specified and no single connected device detected.",
            file=sys.stderr,
        )
        return EXIT_DEVICE_NOT_FOUND

    dm = DeviceManager(adb_wrapper=adb, default_serial=target, runner=runner)

    filter_type = "all"
    if args.system and not args.user:
        filter_type = "system"
    elif args.user and not args.system:
        filter_type = "user"

    try:
        packages = dm.get_installed_packages(serial=target, filter_type=filter_type)
    except Exception as exc:
        print(f"Failed to query packages: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.launchable:
        # Filter to launchable Leanback activities
        try:
            launchable_apps = dm.get_launchable_apps(serial=target)
            if launchable_apps:
                launchable_set = {app.package_name for app in launchable_apps}
                packages = [p for p in packages if p in launchable_set]
        except Exception:
            pass

    if args.json or args.categories:
        safety_db = PackageSafetyDB()
        annotated: List[Dict[str, Any]] = []
        for pkg in packages:
            entry = safety_db.classify(pkg)
            meta = get_app_metadata(pkg)
            friendly_name = meta.name if entry.human_name in (pkg, "") else entry.human_name
            annotated.append({
                "package": pkg,
                "category": entry.category.value,
                "name": friendly_name,
                "genre": meta.category,
                "functional_genre": meta.category,
                "brand": entry.brand,
                "is_known": meta.is_known,
            })

        if args.json:
            if args.categories:
                print(json.dumps(annotated, indent=2))
            else:
                print(json.dumps(packages, indent=2))
            return EXIT_SUCCESS

        # Formatted category table
        for item in annotated:
            cat_tag = f"[{item['category'].upper():<6}]"
            genre_tag = f"[{item['genre']}]"
            print(f"{cat_tag} {genre_tag} [{item['name']}] ({item['package']})")
        return EXIT_SUCCESS

    # Standard listing: raw or friendly formatted
    if getattr(args, "raw", False):
        for pkg in packages:
            print(pkg)
    else:
        for pkg in packages:
            print(format_app_display(pkg))
    return EXIT_SUCCESS


def handle_configure(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Builds, updates, or pushes config.json."""
    if args.base_config:
        base_path = Path(args.base_config)
        if not base_path.is_file():
            print(f"Error: Base config file not found: {args.base_config}", file=sys.stderr)
            return EXIT_ERROR
        try:
            config = LauncherConfig.from_json(base_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Error parsing base config: {exc}", file=sys.stderr)
            return EXIT_ERROR
    else:
        config = create_default_config()

    if args.apps:
        clean_apps: List[str] = []
        for item in args.apps:
            for sub in item.split(","):
                s = sub.strip()
                if s and s not in clean_apps:
                    clean_apps.append(s)
        config.apps = clean_apps

    if args.theme:
        config.theme = args.theme

    if args.screensaver_idle is not None:
        if args.screensaver_idle < 0:
            print("Error: --screensaver-idle must be a positive integer", file=sys.stderr)
            return EXIT_USAGE
        config.oled_protection.screensaver_idle_seconds = args.screensaver_idle

    if args.pixel_shift is not None:
        config.oled_protection.pixel_shift_enabled = bool(args.pixel_shift)

    if args.hdmi:
        hdmi_list: List[HdmiInputConfig] = []
        for item in args.hdmi:
            parts = item.split(":")
            h_id = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else h_id
            vis = True if len(parts) <= 2 or parts[2].lower() in ("true", "1", "yes") else False
            hdmi_list.append(HdmiInputConfig(id=h_id, title=title, visible=vis))
        config.hdmi = hdmi_list

    config_json = config.to_json(indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(config_json + "\n", encoding="utf-8")
        print(f"Configuration written to {out_path}")

    if args.push:
        target = resolve_target_device(args.target, adb, runner)
        if not target:
            print("Error: Cannot push config without a connected target device.", file=sys.stderr)
            return EXIT_DEVICE_NOT_FOUND

        deployer = LauncherDeployer(adb_wrapper=adb, default_serial=target, runner=runner)
        remote_dest = args.remote_path or LauncherDeployer.SECONDARY_CONFIG_PATH
        res = deployer.push_config(target, config, remote_path=remote_dest)
        if not res.success:
            print(f"Failed to push config: {res.message}", file=sys.stderr)
            return EXIT_ERROR
        print(f"Configuration pushed successfully to {target}:{remote_dest}")

        if args.reload:
            rel_res = deployer.reload_config(target)
            if rel_res.success:
                print("Broadcast reload trigger sent (org.opentv.launcher.RELOAD_CONFIG)")
            else:
                print(f"Warning: reload broadcast failed: {rel_res.message}", file=sys.stderr)

    if not args.output and not args.push:
        print(config_json)

    return EXIT_SUCCESS


def handle_deploy(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Deploys APK, pushes config, and sets Home activity."""
    target = resolve_target_device(args.target, adb, runner)
    if not target:
        print("Error: Target device required for deployment.", file=sys.stderr)
        return EXIT_DEVICE_NOT_FOUND

    deployer = LauncherDeployer(adb_wrapper=adb, default_serial=target, runner=runner)

    # 1. Install APK
    if not args.skip_install:
        apk_path = args.apk
        if not apk_path:
            candidates = [
                Path("app/build/outputs/apk/release/app-release.apk"),
                Path("app/build/outputs/apk/debug/app-debug.apk"),
                Path("OpenTV.apk"),
            ]
            for c in candidates:
                if c.is_file():
                    apk_path = str(c)
                    break

        if not apk_path:
            apk_path = "OpenTV.apk"

        # Check file existence if runner is None
        if runner is None and not Path(apk_path).is_file():
            print(f"Error: Launcher APK not found: '{apk_path}'. Specify with --apk <path>", file=sys.stderr)
            return EXIT_ERROR

        print(f"Installing {apk_path} on {target}...")
        res_inst = deployer.install_apk(target, apk_path)
        if not res_inst.success:
            print(f"APK installation failed: {res_inst.message}", file=sys.stderr)
            return EXIT_ERROR
        print("APK installed successfully.")

    # 2. Push Config if specified
    if args.config:
        cfg_path = Path(args.config)
        if runner is None and not cfg_path.is_file():
            print(f"Error: Config file not found: {args.config}", file=sys.stderr)
            return EXIT_ERROR
        try:
            cfg_content = cfg_path.read_text(encoding="utf-8") if cfg_path.is_file() else "{}"
            res_push = deployer.push_config(target, cfg_content)
            if not res_push.success:
                print(f"Failed to push config: {res_push.message}", file=sys.stderr)
                return EXIT_ERROR
            print("Config pushed successfully.")
        except Exception as exc:
            print(f"Error reading/pushing config: {exc}", file=sys.stderr)
            return EXIT_ERROR

    # 3. Set Home Activity
    if args.set_home:
        comp = args.component or LauncherDeployer.DEFAULT_HOME_COMPONENT
        print(f"Configuring default Home activity to {comp}...")
        res_home = deployer.set_home_activity(target, component=comp)
        if not res_home.success:
            print(f"Failed to set Home activity: {res_home.message}", file=sys.stderr)
            return EXIT_ERROR

        is_matched, current_home = deployer.verify_home(target, expected_component=comp)
        if is_matched:
            print("Home activity verified: OpenTV Launcher is active.")
        else:
            print(f"Warning: Home activity did not resolve to {comp}. Current: {current_home}", file=sys.stderr)

    # 4. Reload Broadcast
    if args.reload:
        res_rel = deployer.reload_config(target)
        if res_rel.success:
            print("Configuration reload broadcast sent.")
        else:
            print(f"Warning: Reload broadcast failed: {res_rel.message}", file=sys.stderr)

    return EXIT_SUCCESS


def handle_debloat(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Disables safe or selected packages with guardrails and rollback script generation."""
    if getattr(args, "update_definitions", False):
        from opentv.debloat.database import update_definitions
        success, message, count = update_definitions(source=getattr(args, "source", None))
        if success:
            print(f"Definitions update successful: {message} ({count} packages)")
            return EXIT_SUCCESS
        else:
            print(f"Definitions update failed: {message}", file=sys.stderr)
            return EXIT_ERROR

    target = resolve_target_device(args.target, adb, runner)
    if not target:
        print("Error: Target device required for debloat operations.", file=sys.stderr)
        return EXIT_DEVICE_NOT_FOUND

    dm = DeviceManager(adb_wrapper=adb, default_serial=target, runner=runner)
    try:
        props = dm.get_properties(target)
    except Exception:
        props = {}

    try:
        installed_pkgs = dm.get_installed_packages(target, "all")
    except Exception:
        installed_pkgs = []

    try:
        disabled_pkgs = dm.get_installed_packages(target, "disabled")
    except Exception:
        disabled_pkgs = []

    brand_profile = detect_brand_profile(props, set(installed_pkgs))
    is_gtv = brand_profile.brand_id == "ccwgtv" or "google" in props.get("ro.product.manufacturer", "").lower()
    is_oled = brand_profile.has_oled_protection

    safety_db = PackageSafetyDB()
    candidates: List[str] = []

    if args.safe_only:
        candidates = safety_db.get_safe_candidates(installed_pkgs, brand_id=brand_profile.brand_id)
        if args.packages:
            candidates = sorted(list(set(candidates + args.packages)))
    elif args.packages:
        candidates = list(args.packages)
    else:
        print(
            "Error: Specify either --safe-only to disable confirmed vendor bloat or --packages <names>",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if not candidates:
        print("No debloat candidate packages found.")
        return EXIT_SUCCESS

    # Guardrails filtering
    guardrails = GuardrailsEngine(safety_db=safety_db)
    provisioned = int(props.get("settings.global.device_provisioned", "1")) if props.get("settings.global.device_provisioned", "1").isdigit() else 1
    permitted, violations = guardrails.filter_safe_to_disable(
        candidates,
        brand_id=brand_profile.brand_id,
        installed_packages=installed_pkgs,
        disabled_packages=disabled_pkgs,
        is_google_tv=is_gtv,
        force_google_tv=args.force_google_tv,
        device_provisioned=provisioned,
        is_oled=is_oled,
    )

    if violations:
        print("\n--- Guardrails Shield Warnings ---")
        for pkg, reason in violations:
            print(f"[BLOCKED] {format_app_display(pkg, include_category=False)}: {reason}")
        print("----------------------------------\n")

    if not permitted:
        print("All specified packages were blocked by safety guardrails.", file=sys.stderr)
        return EXIT_GUARDRAIL_VIOLATION if not args.dry_run else EXIT_SUCCESS

    if args.dry_run:
        print(f"Debloat Plan for {target} ({brand_profile.display_name}):")
        print(f"Permitted packages to disable ({len(permitted)}):")
        for p in permitted:
            entry = safety_db.classify(p, brand_id=brand_profile.brand_id)
            print(f"  - {format_app_display(p, safety_label=entry.category.value.upper())}")
        print("\nDry run mode active. No changes were made to the device.")
        return EXIT_SUCCESS

    if not args.yes and sys.stdin.isatty():
        resp = input(f"Proceed with disabling {len(permitted)} packages on {target}? [y/N]: ").strip().lower()
        if resp not in ("y", "yes"):
            print("Operation aborted by user.")
            return EXIT_SUCCESS

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_logger = AuditLogger(log_dir=out_dir)
    rollback_engine = RollbackEngine()

    success_count = 0
    failed_count = 0

    print(f"Disabling {len(permitted)} packages on {target}...")
    for pkg in permitted:
        cmd = adb.build_disable_package_cmd(pkg, target_device=target)
        code, stdout, stderr = runner(cmd)
        success = (code == 0)

        if success:
            success_count += 1
            # Update on-device registry: /data/local/tmp/opentv-disabled.txt
            append_cmd = adb.build_shell_cmd(
                ["sh", "-c", f"echo '{pkg}' >> /data/local/tmp/opentv-disabled.txt"],
                target_device=target,
            )
            runner(append_cmd)
            print(f"  [DISABLED] {format_app_display(pkg, include_category=False)}")
        else:
            failed_count += 1
            print(f"  [FAILED]   {format_app_display(pkg, include_category=False)}: {stderr.strip() or stdout.strip()}", file=sys.stderr)

        audit_logger.record_disable(
            device_id=target,
            package_name=pkg,
            brand_profile=brand_profile.brand_id,
            category=safety_db.categorize(pkg, brand=brand_profile.brand_id).value,
            exit_code=code,
            verified=success,
            details=stdout.strip() if success else stderr.strip(),
        )

    rollback_paths = rollback_engine.write_rollback_scripts(out_dir, permitted, target_device=target)
    print("\nStandalone rollback recovery scripts generated:")
    print(f"  Linux/macOS: {rollback_paths['sh']}")
    print(f"  Windows CMD: {rollback_paths['bat']}")
    print(f"  PowerShell:  {rollback_paths['ps1']}")
    print(f"Audit log saved to: {out_dir / 'audit_log.json'}")

    return EXIT_SUCCESS if failed_count == 0 else EXIT_ERROR


def handle_rollback(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Restores disabled packages or generates recovery scripts."""
    target = resolve_target_device(args.target, adb, runner)

    packages_to_restore: List[str] = []
    if args.packages:
        packages_to_restore = list(args.packages)
    elif target:
        cat_cmd = adb.build_shell_cmd(["cat", "/data/local/tmp/opentv-disabled.txt"], target_device=target)
        code, stdout, _ = runner(cat_cmd)
        if code == 0 and stdout.strip():
            for line in stdout.splitlines():
                pkg = line.strip()
                if pkg and pkg not in packages_to_restore:
                    packages_to_restore.append(pkg)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rollback_engine = RollbackEngine()

    if args.execute:
        if not target:
            print("Error: Target device required to execute rollback.", file=sys.stderr)
            return EXIT_DEVICE_NOT_FOUND

        if not packages_to_restore:
            dm = DeviceManager(adb_wrapper=adb, default_serial=target, runner=runner)
            try:
                packages_to_restore = dm.get_installed_packages(target, "disabled")
            except Exception:
                packages_to_restore = []

        if not packages_to_restore:
            print(f"No disabled packages found to restore on {target}.")
            return EXIT_SUCCESS

        print(f"Restoring {len(packages_to_restore)} packages on {target}...")
        for pkg in packages_to_restore:
            en_cmd = adb.build_enable_package_cmd(pkg, target_device=target)
            code, _, stderr = runner(en_cmd)
            if code == 0:
                print(f"  [RESTORED] {pkg}")
            else:
                print(f"  [ERROR]    Failed to re-enable {pkg}: {stderr}", file=sys.stderr)

        if "com.google.android.apps.tv.launcherx" in packages_to_restore:
            svc = "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
            runner(adb.build_shell_cmd(["cmd", "notification", "allow_listener", svc], target_device=target))

        runner(adb.build_shell_cmd(["rm", "-f", "/data/local/tmp/opentv-disabled.txt"], target_device=target))
        print("Rollback execution complete.")
        return EXIT_SUCCESS

    if not packages_to_restore:
        packages_to_restore = ["<PACKAGE_NAME>"]

    paths = rollback_engine.write_rollback_scripts(out_dir, packages_to_restore, target_device=target or "")
    print(f"Generated standalone rollback scripts in {out_dir}:")
    print(f"  POSIX:      {paths['sh']}")
    print(f"  Batch:      {paths['bat']}")
    print(f"  PowerShell: {paths['ps1']}")
    return EXIT_SUCCESS


def handle_tui(args: argparse.Namespace, adb: AdbClient, runner: Callable) -> int:
    """Launches interactive Terminal UI."""
    try:
        from opentv.tui.app import OpenTVApp
        target = resolve_target_device(args.target, adb, runner)
        app = OpenTVApp(
            target=target,
            adb_path=args.adb_path,
            mode="line" if getattr(args, "fallback", False) else "auto",
            cmd_runner=runner,
            force_fallback=getattr(args, "fallback", False),
        )
        return app.run()
    except ImportError:
        from opentv.tui.terminal import TerminalController
        term = TerminalController()
        print("OpenTV Companion Manager (Terminal Mode)")
        print(f"TTY Active: {term.is_tty}")
        print("Interactive TUI initialized.")
        return EXIT_SUCCESS


# -------------------------------------------------------------------------
# Parser Construction & Main Dispatch
# -------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    """Builds the top-level ArgumentParser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="opentv",
        description="OpenTV Companion: Android TV Launcher Management, Configuration & Debloating Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  opentv tui                                   # Launch interactive Terminal UI
  opentv connect 192.168.1.50                  # Connect to wireless TV
  opentv pair 192.168.1.50:38450 123456        # Android 11+ Wi-Fi pairing
  opentv list-apps --launchable                # List TV launchable apps
  opentv configure --apps com.netflix.ninja    # Build or push config.json
  opentv deploy --apk app-release.apk --set-home # Deploy launcher & set default Home
  opentv debloat --safe-only --dry-run         # Preview safe debloat candidates
  opentv rollback --execute                    # Emergency restore of disabled packages
""",
    )

    # Global Arguments
    parser.add_argument(
        "-t",
        "--target",
        type=str,
        default=None,
        help="Target device serial or IP:port (e.g. 192.168.1.50:5555)",
    )
    parser.add_argument(
        "--adb-path",
        type=str,
        default=os.environ.get("ADB", "adb"),
        help="Path to adb binary (default: 'adb')",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with executed ADB commands",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"OpenTV companion v{__version__}",
    )

    # Common options available to all subparsers as well
    common_sub = argparse.ArgumentParser(add_help=False)
    common_sub.add_argument(
        "-t",
        "--target",
        type=str,
        default=argparse.SUPPRESS,
        help="Target device serial or IP:port (e.g. 192.168.1.50:5555)",
    )
    common_sub.add_argument(
        "--adb-path",
        type=str,
        default=argparse.SUPPRESS,
        help="Path to adb binary (default: 'adb')",
    )
    common_sub.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Enable verbose output with executed ADB commands",
    )

    subparsers = parser.add_subparsers(
        dest="subcommand",
        title="subcommands",
        metavar="<command>",
    )

    # 1. connect
    p_connect = subparsers.add_parser("connect", parents=[common_sub], help="Connect to a wireless Android TV device")
    p_connect.add_argument(
        "target",
        type=str,
        nargs="?",
        default=None,
        help="Device IP or IP:port (e.g. 192.168.1.50 or 192.168.1.50:5555). Optional if --discover is specified.",
    )
    p_connect.add_argument("-p", "--port", type=int, default=5555, help="Port if omitted from target (default: 5555)")
    p_connect.add_argument("--timeout", type=float, default=10.0, help="Connection timeout in seconds (default: 10.0)")
    p_connect.add_argument(
        "-d",
        "--discover",
        nargs="?",
        const=3.0,
        type=float,
        default=None,
        metavar="TIMEOUT",
        help="Discover Android TV devices on local network via mDNS & SSDP (default timeout: 3.0s)",
    )
    p_connect.add_argument(
        "--discover-timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Timeout for device discovery scan in seconds (default: 3.0)",
    )
    p_connect.add_argument(
        "--json",
        action="store_true",
        help="Output discovered devices as JSON (when used with --discover)",
    )

    # 2. pair
    p_pair = subparsers.add_parser("pair", parents=[common_sub], help="Pair with Android 11+ Wi-Fi debugging target")
    p_pair.add_argument("target", type=str, help="Device pairing address IP:port (e.g. 192.168.1.50:38450)")
    p_pair.add_argument("code", type=str, help="6-digit pairing code displayed on TV")
    p_pair.add_argument("--timeout", type=float, default=15.0, help="Pairing timeout in seconds (default: 15.0)")

    # 3. list-apps
    p_list = subparsers.add_parser("list-apps", parents=[common_sub], help="List installed packages on connected TV")
    p_list.add_argument("-s", "--system", action="store_true", help="List only system packages")
    p_list.add_argument("-u", "--user", action="store_true", help="List only 3rd-party user packages")
    p_list.add_argument("-l", "--launchable", action="store_true", help="Filter to only apps with TV Leanback launcher activities")
    p_list.add_argument("--raw", action="store_true", help="Output unformatted package IDs only (for shell piping)")
    p_list.add_argument("--json", action="store_true", help="Output results formatted as JSON")
    p_list.add_argument("--categories", action="store_true", help="Annotate packages with safety categories (never, keep, safe, review)")

    # 4. configure
    p_config = subparsers.add_parser("configure", parents=[common_sub], help="Build, update, or push config.json")
    p_config.add_argument("-a", "--apps", nargs="+", help="Package names to show on launcher home screen")
    p_config.add_argument("--hdmi", action="append", help="HDMI input in format ID:Title[:visible] (e.g. HW5:'PS5')")
    p_config.add_argument("--theme", type=str, default=None, help="Visual theme name (default: OLED_Black)")
    p_config.add_argument("--screensaver-idle", type=int, default=None, help="OLED screensaver idle timeout in seconds")
    p_config.add_argument("--pixel-shift", action="store_true", default=None, help="Enable OLED pixel shift protection")
    p_config.add_argument("--no-pixel-shift", action="store_false", dest="pixel_shift", help="Disable OLED pixel shift")
    p_config.add_argument("-o", "--output", type=str, default=None, help="Output file path to save config.json")
    p_config.add_argument("--push", action="store_true", help="Push config directly to connected TV device")
    p_config.add_argument("--remote-path", type=str, default="/sdcard/OpenTV/config.json", help="Remote destination path on TV")
    p_config.add_argument("--reload", action="store_true", help="Broadcast reload intent after pushing")
    p_config.add_argument("--base-config", type=str, default=None, help="Path to base config.json to load and modify")

    # 5. deploy
    p_deploy = subparsers.add_parser("deploy", parents=[common_sub], help="Deploy launcher APK, push config, and set default Home")
    p_deploy.add_argument("--apk", type=str, default=None, help="Path to OpenTV release APK")
    p_deploy.add_argument("--config", type=str, default=None, help="Path to config.json to push")
    p_deploy.add_argument("--set-home", action="store_true", help="Configure OpenTV as the default Home activity")
    p_deploy.add_argument("--reload", action="store_true", help="Broadcast config reload intent")
    p_deploy.add_argument("--component", type=str, default="org.opentv.launcher/.MainActivity", help="Home activity component")
    p_deploy.add_argument("--skip-install", action="store_true", help="Skip APK installation and only configure/set Home")

    # 6. debloat
    p_debloat = subparsers.add_parser("debloat", parents=[common_sub], help="Safely disable bloatware packages with guardrails")
    p_debloat.add_argument("-p", "--packages", nargs="+", help="Package names to disable")
    p_debloat.add_argument("--safe-only", action="store_true", help="Automatically disable all confirmed SAFE packages for the detected brand")
    p_debloat.add_argument("-n", "--dry-run", action="store_true", help="Preview debloat candidates and guardrails without modifying TV")
    p_debloat.add_argument("--force-google-tv", action="store_true", help="Force disabling launcherx on Google TV (bypassing bootloop shield)")
    p_debloat.add_argument("--output-dir", type=str, default=".", help="Directory to save rollback scripts and audit log")
    p_debloat.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")
    p_debloat.add_argument("--update-definitions", action="store_true", help="Update debloat safety definitions from remote repository or local file")
    p_debloat.add_argument("--source", type=str, default=None, help="Custom URL or local file path for updating definitions")

    # 7. rollback
    p_rollback = subparsers.add_parser("rollback", parents=[common_sub], help="Generate rollback recovery scripts or restore packages")
    p_rollback.add_argument("--output-dir", type=str, default=".", help="Directory to write rollback scripts")
    p_rollback.add_argument("-e", "--execute", action="store_true", help="Directly re-enable packages on connected TV")
    p_rollback.add_argument("-p", "--packages", nargs="*", help="Specific package names to re-enable")
    p_rollback.add_argument("--from-registry", action="store_true", help="Read disabled packages from on-device registry")

    # 8. tui
    p_tui = subparsers.add_parser("tui", parents=[common_sub], help="Launch interactive Terminal UI")
    p_tui.add_argument("--fallback", action="store_true", help="Force line-oriented fallback mode")

    # 9. discover
    p_discover = subparsers.add_parser("discover", parents=[common_sub], help="Scan local network for Android TV devices")
    p_discover.add_argument("--timeout", type=float, default=3.0, help="Discovery timeout in seconds (default: 3.0)")
    p_discover.add_argument("--json", action="store_true", help="Output discovered devices as JSON")
    p_discover.add_argument("-c", "--connect", action="store_true", help="Prompt to immediately connect to a discovered device")

    return parser


def _main_dispatch(
    argv: Optional[List[str]] = None,
    runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
) -> int:
    """Internal CLI argument parser and command dispatcher."""
    parser = create_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    # Default to TUI if no subcommand provided and interactive, else show help
    if not args.subcommand:
        if sys.stdin.isatty():
            args.subcommand = "tui"
        else:
            parser.print_help()
            return EXIT_SUCCESS

    active_runner = runner or default_subprocess_runner
    adb = AdbClient(adb_path=args.adb_path, default_device=getattr(args, "target", None))

    dispatch_table: Dict[str, Callable[[argparse.Namespace, AdbClient, Callable], int]] = {
        "connect": handle_connect,
        "discover": handle_discover,
        "pair": handle_pair,
        "list-apps": handle_list_apps,
        "configure": handle_configure,
        "deploy": handle_deploy,
        "debloat": handle_debloat,
        "rollback": handle_rollback,
        "tui": handle_tui,
    }

    handler = dispatch_table.get(args.subcommand)
    if not handler:
        parser.print_help()
        return EXIT_USAGE

    try:
        return handler(args, adb, active_runner)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130
    except GuardrailViolation as gv:
        print(f"Safety Guardrail Violation: {gv}", file=sys.stderr)
        return EXIT_GUARDRAIL_VIOLATION
    except Exception as exc:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR


def main(
    argv: Optional[List[str]] = None,
    runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
    stdout: Optional[Any] = None,
) -> int:
    """Primary CLI entry point. Parses args and dispatches to subcommand handlers."""
    if stdout is not None:
        with contextlib.redirect_stdout(stdout):
            return _main_dispatch(argv, runner)
    return _main_dispatch(argv, runner)

