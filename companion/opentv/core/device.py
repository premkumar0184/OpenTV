"""
OpenTV Device Models & Device Manager.
PROJECT.md Feature F2.2 & F2.3:
Provides discovery, connection, pairing, interrogation, and package querying for Android TV devices.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from opentv.core.adb import AdbClient, AdbDevice, AdbWrapper
from opentv.core.app_names import get_app_name
from opentv.profiles.detector import BrandProfile, detect_brand_profile


@dataclass
class ActivityComponent:
    """Represents an Android package and launchable activity component."""

    package_name: str
    activity_name: str
    category: str = "android.intent.category.LEANBACK_LAUNCHER"
    label: str = ""

    @property
    def component_name(self) -> str:
        """Formatted as 'package/activity' (e.g. 'com.netflix.ninja/.MainActivity')."""
        if self.activity_name.startswith("."):
            return f"{self.package_name}/{self.activity_name}"
        elif "/" in self.activity_name:
            return self.activity_name
        return f"{self.package_name}/{self.activity_name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "activity_name": self.activity_name,
            "component_name": self.component_name,
            "category": self.category,
            "label": self.label,
        }


@dataclass
class PackageInfo:
    """Represents an installed application package and its capabilities."""

    package_name: str
    is_system: bool = False
    is_enabled: bool = True
    app_label: str = ""
    launchable_activity: Optional[str] = None
    is_tv_app: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_name": self.package_name,
            "is_system": self.is_system,
            "is_enabled": self.is_enabled,
            "app_label": self.app_label,
            "launchable_activity": self.launchable_activity,
            "is_tv_app": self.is_tv_app,
        }


@dataclass
class DeviceInfo:
    """Structured Android TV device metadata and resolved brand profile."""

    serial: str
    model: str
    brand: str
    manufacturer: str
    android_version: str
    sdk_level: int
    is_tv: bool
    profile: BrandProfile
    device: str = ""
    product: str = ""
    state: str = "device"
    is_provisioned: bool = True
    properties: Dict[str, str] = field(default_factory=dict)

    @property
    def is_wireless(self) -> bool:
        """Returns True if the serial is a network address (contains ':')."""
        return ":" in self.serial

    def display_summary(self) -> str:
        """Human-readable one-line device description."""
        tv_tag = "TV" if self.is_tv else "Device"
        return (
            f"{self.manufacturer} {self.model} ({tv_tag}, Android {self.android_version}, "
            f"SDK {self.sdk_level}) [{self.profile.display_name}]"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "serial": self.serial,
            "model": self.model,
            "brand": self.brand,
            "manufacturer": self.manufacturer,
            "android_version": self.android_version,
            "sdk_level": self.sdk_level,
            "is_tv": self.is_tv,
            "brand_id": self.profile.brand_id,
            "brand_display_name": self.profile.display_name,
            "has_oled_protection": self.profile.has_oled_protection,
            "device": self.device,
            "product": self.product,
            "state": self.state,
            "is_wireless": self.is_wireless,
            "is_provisioned": self.is_provisioned,
        }


class DeviceError(Exception):
    """Base exception for device discovery and connection errors."""

    pass


class NoDeviceConnectedError(DeviceError):
    """Raised when no ADB devices are found online."""

    pass


class AmbiguousDeviceError(DeviceError):
    """Raised when multiple devices are found and no target was specified."""

    def __init__(self, message: str, devices: Optional[List[AdbDevice]] = None) -> None:
        super().__init__(message)
        self.devices = devices or []


class DeviceConnectionError(DeviceError):
    """Raised when adb connect or pair fails."""

    pass


class DeviceInterrogationError(DeviceError):
    """Raised when retrieving getprop or device features fails."""

    pass


class DeviceManager:
    """
    Manages ADB device discovery, wireless connection/pairing, property extraction,
    and Leanback TV application discovery.
    """

    def __init__(
        self,
        adb_wrapper: Optional[AdbWrapper] = None,
        default_serial: Optional[str] = None,
        runner: Optional[Any] = None,
    ) -> None:
        self.adb = adb_wrapper or AdbWrapper(default_device=default_serial)
        self.default_serial = default_serial
        self.runner = runner  # Optional MockAdbRunner or custom executor

    def _run_cmd(
        self, cmd: List[str], timeout: Optional[float] = 30.0
    ) -> Tuple[int, str, str]:
        """Executes an ADB command via injected runner or standard subprocess."""
        if self.runner is not None:
            if callable(self.runner):
                return self.runner(cmd)
            elif hasattr(self.runner, "execute"):
                return self.runner.execute(cmd)
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return (res.returncode, res.stdout, res.stderr)
        except FileNotFoundError:
            return (127, "", f"ADB binary not found: '{cmd[0]}'")
        except subprocess.TimeoutExpired:
            return (124, "", f"Command timed out after {timeout}s: {' '.join(cmd)}")
        except Exception as e:
            return (1, "", str(e))

    # Device Discovery & Selection
    def list_connected_devices(self) -> List[AdbDevice]:
        """Lists all attached devices using `adb devices -l`."""
        cmd = self.adb.build_devices_cmd()
        code, out, err = self._run_cmd(cmd)
        if code != 0:
            raise DeviceError(f"Failed to list devices: {err.strip() or out.strip()}")
        return self.adb.parse_devices(out)

    def select_target_device(self, target: Optional[str] = None) -> str:
        """
        Resolves the target device serial.
        If target is provided, validates and returns it.
        If target is None, queries connected devices:
          - If exactly one online device: auto-selects it.
          - If multiple devices: auto-selects single USB device if present, else raises AmbiguousDeviceError.
          - If zero devices: raises NoDeviceConnectedError.
        """
        if target and target.strip():
            return target.strip()
        if self.default_serial and self.default_serial.strip():
            return self.default_serial.strip()

        devices = self.list_connected_devices()
        online = [d for d in devices if d.state == "device"]

        if not online:
            raise NoDeviceConnectedError("No online Android TV devices found via ADB.")

        if len(online) == 1:
            return online[0].serial

        # Check for single USB device among network devices
        usb_devices = [d for d in online if not self.is_wireless_serial(d.serial)]
        if len(usb_devices) == 1:
            return usb_devices[0].serial

        device_list = ", ".join(d.serial for d in online)
        raise AmbiguousDeviceError(
            f"Multiple devices found: [{device_list}]. Specify target with -t / --target.",
            devices=online,
        )

    @staticmethod
    def is_wireless_serial(serial: str) -> bool:
        """Returns True if the serial string is an IP:port address."""
        return ":" in serial

    # Device Connection & Pairing
    def connect(
        self, target: str, port: int = 5555, timeout: float = 10.0
    ) -> Tuple[bool, str]:
        """
        Connects to a wireless Android TV device via `adb connect <host>[:port]`.
        Returns (success: bool, message: str).
        """
        host = target.strip()
        if ":" in host:
            host_part, port_str = host.split(":", 1)
            host = host_part
            try:
                port = int(port_str)
            except ValueError:
                return (False, f"Invalid port in target: '{port_str}'")

        try:
            cmd = self.adb.build_connect_cmd(host, port)
        except ValueError as exc:
            return (False, str(exc))

        code, out, err = self._run_cmd(cmd, timeout=timeout)
        combined = f"{out}\n{err}".strip()

        if code == 0 and ("connected to" in combined.lower() or "already connected" in combined.lower()):
            return (True, combined)
        return (False, combined or "Failed to connect to device")

    def disconnect(
        self, target: str, port: int = 5555, timeout: float = 10.0
    ) -> Tuple[bool, str]:
        """Disconnects a wireless device via `adb disconnect <host>[:port]`."""
        host = target.strip()
        if ":" in host:
            host_part, port_str = host.split(":", 1)
            host = host_part
            try:
                port = int(port_str)
            except ValueError:
                return (False, f"Invalid port in target: '{port_str}'")

        try:
            cmd = self.adb.build_disconnect_cmd(host, port)
        except ValueError as exc:
            return (False, str(exc))

        code, out, err = self._run_cmd(cmd, timeout=timeout)
        combined = f"{out}\n{err}".strip()
        return (code == 0, combined)

    def pair(
        self,
        target: str,
        code: str,
        port: Optional[int] = None,
        timeout: float = 15.0,
    ) -> Tuple[bool, str]:
        """
        Pairs with an Android 11+ wireless debugging host:port and 6-digit pairing code.
        Returns (success: bool, message: str).
        """
        host = target.strip()
        if ":" in host:
            host_part, port_str = host.split(":", 1)
            host = host_part
            try:
                port = int(port_str)
            except ValueError:
                return (False, f"Invalid port in target: '{port_str}'")
        elif port is None:
            return (False, "Pairing requires target host:port or port parameter")

        try:
            cmd = self.adb.build_pair_cmd(host, port, code)
        except ValueError as exc:
            return (False, str(exc))

        ret, out, err = self._run_cmd(cmd, timeout=timeout)
        combined = f"{out}\n{err}".strip()

        if ret == 0 and ("successfully paired" in combined.lower() or "paired to" in combined.lower()):
            return (True, combined)
        return (False, combined or "Pairing failed")

    # Device Interrogation
    def get_properties(self, serial: Optional[str] = None) -> Dict[str, str]:
        """Queries `getprop` from the target device and returns a dictionary of properties."""
        target = self.select_target_device(serial)
        cmd = self.adb.build_getprop_cmd(target_device=target)
        code, out, err = self._run_cmd(cmd)
        if code != 0:
            raise DeviceInterrogationError(
                f"Failed to run getprop: {err.strip() or out.strip()}"
            )

        props: Dict[str, str] = {}
        for line in out.splitlines():
            line = line.strip()
            # Match standard getprop format: [key]: [value]
            if line.startswith("[") and "]: [" in line:
                k = line[1:].split("]: [")[0]
                v = line.split("]: [", 1)[1].rstrip("]")
                props[k] = v
            elif ":" in line:
                parts = line.split(":", 1)
                k = parts[0].strip().strip("[]")
                v = parts[1].strip().strip("[]")
                props[k] = v
        return props

    def get_device_info(
        self,
        serial: Optional[str] = None,
        installed_packages: Optional[Set[str]] = None,
    ) -> DeviceInfo:
        """
        Interrogates the connected device, extracts model/manufacturer/SDK,
        evaluates Android TV features, and resolves the BrandProfile.
        """
        target = self.select_target_device(serial)
        props = self.get_properties(target)

        # Extract primary identity properties
        mfg = props.get("ro.product.manufacturer", "Unknown")
        brand = props.get("ro.product.brand", "Generic")
        model = props.get("ro.product.model", "Android TV")
        device_name = props.get("ro.product.device", "")
        product_name = props.get("ro.product.name", "")
        version_rel = props.get("ro.build.version.release", "Unknown")
        sdk_str = props.get("ro.build.version.sdk", "0")
        try:
            sdk_level = int(sdk_str)
        except ValueError:
            sdk_level = 0

        # Query packages if not provided (needed for brand signature detection)
        if installed_packages is None:
            try:
                installed_packages = set(self.get_installed_packages(target))
            except Exception:
                installed_packages = set()

        # Check for Android TV features
        is_tv = self._check_is_tv(target, props, installed_packages)

        # Resolve BrandProfile
        profile = detect_brand_profile(props, installed_packages)

        # Provisioning status
        provisioned = (
            props.get("settings.global.device_provisioned", "1") != "0"
            and props.get("ro.setupwizard.mode", "") != "REQUIRED"
        )

        return DeviceInfo(
            serial=target,
            model=model,
            brand=brand,
            manufacturer=mfg,
            android_version=version_rel,
            sdk_level=sdk_level,
            is_tv=is_tv,
            profile=profile,
            device=device_name,
            product=product_name,
            state="device",
            is_provisioned=provisioned,
            properties=props,
        )

    def _check_is_tv(
        self, serial: str, props: Dict[str, str], pkgs: Set[str]
    ) -> bool:
        """Determines if the target device is an Android TV / Google TV platform."""
        # Check characteristic properties
        chars = props.get("ro.build.characteristics", "").lower()
        if "tv" in chars or "leanback" in chars:
            return True

        # Check model / device names
        model_str = (
            props.get("ro.product.model", "")
            + " "
            + props.get("ro.product.device", "")
            + " "
            + props.get("ro.product.name", "")
        ).lower()
        if any(term in model_str for term in ("bravia", "shield", "beyondtv", "chromecast", "mibox")):
            return True

        # Check TV packages
        tv_indicators = {
            "com.google.android.apps.tv.launcherx",
            "com.google.android.tvlauncher",
            "com.google.android.tvrecommendations",
            "org.droidtv.homeintentresolver",
            "com.mitv.tvhome",
        }
        if any(p in pkgs for p in tv_indicators):
            return True

        # Check features via pm list features
        cmd = self.adb.build_shell_cmd(["pm", "list", "features"], target_device=serial)
        code, out, _ = self._run_cmd(cmd)
        if code == 0:
            if "android.software.leanback" in out or "android.hardware.type.television" in out:
                return True

        return False

    # App Discovery
    def get_installed_packages(
        self, serial: Optional[str] = None, filter_type: str = "all"
    ) -> List[str]:
        """
        Lists installed package names on the target device.
        Supported filter_type: 'all', 'user' / '-3', 'system' / '-s', 'enabled' / '-e', 'disabled' / '-d'.
        """
        target = self.select_target_device(serial)
        flag_map = {
            "all": "",
            "user": "-3",
            "third-party": "-3",
            "-3": "-3",
            "system": "-s",
            "-s": "-s",
            "enabled": "-e",
            "-e": "-e",
            "disabled": "-d",
            "-d": "-d",
        }
        flag = flag_map.get(filter_type.lower().strip(), "")
        cmd = self.adb.build_list_packages_cmd(flags=flag, target_device=target)
        code, out, err = self._run_cmd(cmd)
        if code != 0:
            raise DeviceError(f"Failed to query packages: {err.strip() or out.strip()}")
        return self.adb.parse_packages(out)

    def resolve_leanback_activity(
        self, serial: Optional[str] = None
    ) -> Optional[ActivityComponent]:
        """
        Queries the default/resolving Leanback launcher activity via:
        `cmd package resolve-activity -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER`.
        """
        target = self.select_target_device(serial)
        cmd = self.adb.build_shell_cmd(
            [
                "cmd",
                "package",
                "resolve-activity",
                "--brief",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LEANBACK_LAUNCHER",
            ],
            target_device=target,
        )
        code, out, _ = self._run_cmd(cmd)
        if code != 0 or not out.strip() or "No activity found" in out:
            return None

        # Parse component from brief output (last line contains pkg/activity)
        for line in reversed(out.strip().splitlines()):
            line = line.strip()
            if "/" in line and not line.startswith("priority="):
                parts = line.split("/", 1)
                return ActivityComponent(
                    package_name=parts[0].strip(),
                    activity_name=parts[1].strip(),
                    category="android.intent.category.LEANBACK_LAUNCHER",
                )
        return None

    def get_launchable_apps(
        self, serial: Optional[str] = None
    ) -> List[ActivityComponent]:
        """
        Queries all installed apps that declare a LEANBACK_LAUNCHER activity.
        Falls back to regular LAUNCHER if no leanback activities are returned.
        """
        target = self.select_target_device(serial)
        apps = self._query_activities(target, "android.intent.category.LEANBACK_LAUNCHER")
        if not apps:
            apps = self._query_activities(target, "android.intent.category.LAUNCHER")
        return apps

    def _query_activities(
        self, target: str, category: str
    ) -> List[ActivityComponent]:
        """Helper to run pm query-intent-activities."""
        cmd = self.adb.build_shell_cmd(
            [
                "pm",
                "query-intent-activities",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                category,
            ],
            target_device=target,
        )
        code, out, _ = self._run_cmd(cmd)
        if code != 0 or not out.strip():
            return []

        results: List[ActivityComponent] = []
        seen: Set[str] = set()

        for line in out.splitlines():
            line = line.strip()
            # Handle formats like: "com.netflix.ninja/.MainActivity" or "activity name=com.pkg/.Act"
            match = re.search(r"([a-zA-Z0-9_\.]+)/([a-zA-Z0-9_\.]+)", line)
            if match:
                pkg = match.group(1)
                act = match.group(2)
                comp = f"{pkg}/{act}"
                if comp not in seen:
                    seen.add(comp)
                    results.append(
                        ActivityComponent(
                            package_name=pkg,
                            activity_name=act,
                            category=category,
                        )
                    )
        return results

    def get_all_packages_info(
        self, serial: Optional[str] = None
    ) -> List[PackageInfo]:
        """Returns comprehensive PackageInfo records for all installed packages."""
        target = self.select_target_device(serial)
        all_pkgs = set(self.get_installed_packages(target, "all"))
        sys_pkgs = set(self.get_installed_packages(target, "system"))
        dis_pkgs = set(self.get_installed_packages(target, "disabled"))
        launchables = {
            app.package_name: app.component_name
            for app in self.get_launchable_apps(target)
        }

        info_list: List[PackageInfo] = []
        for pkg in sorted(all_pkgs):
            is_sys = pkg in sys_pkgs
            is_en = pkg not in dis_pkgs
            launch_act = launchables.get(pkg)
            is_tv = pkg in launchables

            info_list.append(
                PackageInfo(
                    package_name=pkg,
                    is_system=is_sys,
                    is_enabled=is_en,
                    app_label=get_app_name(pkg),
                    launchable_activity=launch_act,
                    is_tv_app=is_tv,
                )
            )
        return info_list
