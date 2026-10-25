"""
Canonical AdbClient wrapper and command builder according to PROJECT.md Feature F2.2 & F2.3.
Enforces typed list formatting, IP validation, device parsing, and command execution contracts.
"""
from __future__ import annotations
import re
import ipaddress
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

@dataclass
class AdbDevice:
    serial: str
    state: str  # "device", "unauthorized", "offline"
    product: str = ""
    model: str = ""
    device: str = ""
    transport_id: str = ""

IPV4_REGEX = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")

class AdbWrapper:
    def __init__(self, adb_path: str = "adb", default_device: Optional[str] = None):
        self.adb_path = adb_path
        self.default_device = default_device

    def validate_ip(self, ip_str: str) -> None:
        if not ip_str or not isinstance(ip_str, str):
            raise ValueError(f"Invalid IP address: '{ip_str}'")
        try:
            ipaddress.ip_address(ip_str.strip())
        except ValueError as e:
            raise ValueError(f"Invalid IP address format: '{ip_str}'") from e

    def validate_port(self, port: int | str) -> int:
        try:
            p = int(port)
            if not (1 <= p <= 65535):
                raise ValueError()
            return p
        except (ValueError, TypeError):
            raise ValueError(f"Invalid port: '{port}'. Must be between 1 and 65535.")

    def format_device_address(self, host: str, port: int = 5555) -> str:
        self.validate_ip(host)
        valid_port = self.validate_port(port)
        return f"{host.strip()}:{valid_port}"

    def base_cmd(self, target_device: Optional[str] = None) -> List[str]:
        device = target_device or self.default_device
        if device:
            return [self.adb_path, "-s", device]
        return [self.adb_path]

    # Command Builders
    def build_devices_cmd(self) -> List[str]:
        return [self.adb_path, "devices", "-l"]

    def build_connect_cmd(self, host: str, port: int = 5555) -> List[str]:
        addr = self.format_device_address(host, port)
        return [self.adb_path, "connect", addr]

    def build_disconnect_cmd(self, host: str, port: int = 5555) -> List[str]:
        addr = self.format_device_address(host, port)
        return [self.adb_path, "disconnect", addr]

    def build_pair_cmd(self, host: str, port: int, pairing_code: str) -> List[str]:
        addr = self.format_device_address(host, port)
        code = str(pairing_code).strip()
        if not code or not code.isdigit():
            raise ValueError(f"Pairing code must be numeric digits, got: '{pairing_code}'")
        return [self.adb_path, "pair", addr, code]

    def build_shell_cmd(self, shell_args: List[str], target_device: Optional[str] = None) -> List[str]:
        return self.base_cmd(target_device) + ["shell"] + list(shell_args)

    def build_list_packages_cmd(self, flags: str = "", target_device: Optional[str] = None) -> List[str]:
        cmd = ["pm", "list", "packages"]
        if flags:
            cmd.extend(flags.split())
        return self.build_shell_cmd(cmd, target_device)

    def build_disable_package_cmd(self, package_name: str, user: int = 0, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd(["pm", "disable-user", "--user", str(user), package_name], target_device)

    def build_enable_package_cmd(self, package_name: str, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd(["pm", "enable", package_name], target_device)

    def build_set_home_cmd(self, component: str, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd(["cmd", "package", "set-home-activity", component], target_device)

    def build_resolve_home_cmd(self, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd([
            "cmd", "package", "resolve-activity", "--brief",
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.HOME"
        ], target_device)

    def build_broadcast_reload_cmd(self, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd([
            "am", "broadcast", "-a", "org.opentv.launcher.RELOAD_CONFIG"
        ], target_device)

    def build_input_keyevent_cmd(self, keycode: int, target_device: Optional[str] = None) -> List[str]:
        return self.build_shell_cmd(["input", "keyevent", str(keycode)], target_device)

    def build_push_config_cmd(self, local_path: str, remote_path: str = "/sdcard/OpenTV/config.json", target_device: Optional[str] = None) -> List[str]:
        return self.base_cmd(target_device) + ["push", local_path, remote_path]

    def build_install_apk_cmd(self, apk_path: str, target_device: Optional[str] = None) -> List[str]:
        return self.base_cmd(target_device) + ["install", "-r", "-g", apk_path]

    # Parsers
    def parse_devices(self, stdout: str) -> List[AdbDevice]:
        devices: List[AdbDevice] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices") or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                state = parts[1]
                meta: Dict[str, str] = {}
                for token in parts[2:]:
                    if ":" in token:
                        k, v = token.split(":", 1)
                        meta[k] = v
                devices.append(AdbDevice(
                    serial=serial,
                    state=state,
                    product=meta.get("product", ""),
                    model=meta.get("model", ""),
                    device=meta.get("device", ""),
                    transport_id=meta.get("transport_id", ""),
                ))
        return devices

    def parse_packages(self, stdout: str) -> List[str]:
        pkgs: List[str] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkgs.append(line[len("package:"):].strip())
            elif line:
                pkgs.append(line)
        return sorted(list(set(pkgs)))
