"""
Mock ADB runner and simulated Android TV device environment for cross-platform testing.
"""
from __future__ import annotations
import shlex
from typing import List, Dict, Optional, Tuple, Set

class MockDevice:
    def __init__(
        self,
        serial: str = "192.168.1.50:5555",
        state: str = "device",
        product: str = "bravia_4k",
        model: str = "BRAVIA_4K_VH2",
        device: str = "bravia",
        properties: Optional[Dict[str, str]] = None,
        installed_packages: Optional[Set[str]] = None,
    ):
        self.serial = serial
        self.state = state
        self.product = product
        self.model = model
        self.device = device
        self.properties = {
            "ro.product.manufacturer": "Sony",
            "ro.product.brand": "Sony",
            "ro.product.model": model,
            "ro.product.device": device,
            "ro.build.version.release": "12",
            "ro.build.version.sdk": "31",
            "settings.global.device_provisioned": "1",
            "settings.secure.user_setup_complete": "1",
        }
        if properties:
            self.properties.update(properties)
        
        self.installed_packages = set(installed_packages or [
            "android",
            "com.android.systemui",
            "com.android.settings",
            "com.android.bluetooth",
            "com.google.android.inputmethod.latin",
            "com.google.android.youtube.tv",
            "com.netflix.ninja",
            "com.plexapp.android",
            "tv.samba.ssm",
            "com.sony.dtv.demomode",
            "com.google.android.tvrecommendations",
            "com.google.android.backdrop",
        ])
        self.disabled_packages: Set[str] = set()
        self.home_activity = "com.google.android.apps.tv.launcherx/.MainActivity"
        self.files: Dict[str, str] = {}
        self.recorded_keyevents: List[int] = []
        self.broadcasts_received: List[str] = []
        self.notification_listeners: Set[str] = set()

    def disable_package(self, pkg: str) -> bool:
        if pkg in self.installed_packages:
            self.disabled_packages.add(pkg)
            # Maintain /data/local/tmp/opentv-disabled.txt
            current = self.files.get("/data/local/tmp/opentv-disabled.txt", "")
            lines = [l for l in current.splitlines() if l.strip()]
            if pkg not in lines:
                lines.append(pkg)
            self.files["/data/local/tmp/opentv-disabled.txt"] = "\n".join(lines) + "\n"
            return True
        return False

    def enable_package(self, pkg: str) -> bool:
        if pkg in self.disabled_packages:
            self.disabled_packages.remove(pkg)
            current = self.files.get("/data/local/tmp/opentv-disabled.txt", "")
            lines = [l for l in current.splitlines() if l.strip() and l != pkg]
            self.files["/data/local/tmp/opentv-disabled.txt"] = "\n".join(lines) + "\n"
            return True
        return False


class MockAdbRunner:
    """Interceps ADB command lists and simulates device responses without network or daemon."""
    def __init__(self, initial_devices: Optional[List[MockDevice]] = None):
        self.devices: Dict[str, MockDevice] = {}
        for dev in (initial_devices or [MockDevice()]):
            self.devices[dev.serial] = dev
        self.command_log: List[List[str]] = []

    def add_device(self, dev: MockDevice) -> None:
        self.devices[dev.serial] = dev

    def execute(self, cmd: List[str]) -> Tuple[int, str, str]:
        self.command_log.append(list(cmd))
        if not cmd or cmd[0] != "adb":
            return (1, "", f"Unknown command binary: {cmd}")

        # Check for target device flag `-s`
        target_serial: Optional[str] = None
        args = list(cmd[1:])
        if len(args) >= 2 and args[0] == "-s":
            target_serial = args[1]
            args = args[2:]

        if not args:
            return (0, "Android Debug Bridge version 1.0.41", "")

        subcmd = args[0]

        # 1. adb devices
        if subcmd == "devices":
            lines = ["List of devices attached"]
            for s, dev in self.devices.items():
                meta = f"product:{dev.product} model:{dev.model} device:{dev.device} transport_id:1"
                lines.append(f"{s}\t{dev.state} {meta}")
            return (0, "\n".join(lines) + "\n", "")

        # 2. adb connect <host>
        if subcmd == "connect":
            if len(args) < 2:
                return (1, "", "missing host")
            addr = args[1]
            if addr not in self.devices:
                # Dynamically create connected device
                self.devices[addr] = MockDevice(serial=addr)
            return (0, f"connected to {addr}\n", "")

        # 3. adb disconnect <host>
        if subcmd == "disconnect":
            addr = args[1] if len(args) > 1 else ""
            if addr in self.devices:
                del self.devices[addr]
                return (0, f"disconnected {addr}\n", "")
            return (0, f"error: no such device '{addr}'\n", "")

        # 4. adb pair <host> <code>
        if subcmd == "pair":
            if len(args) < 3:
                return (1, "", "Usage: adb pair <host>[:port] [pairing code]")
            addr = args[1]
            code = args[2]
            if len(code) == 6 and code.isdigit():
                return (0, f"Successfully paired to {addr} [guid=adb-1234]\n", "")
            return (1, "", f"Failed: Unable to pair to {addr}\n")

        # Select target device for device-directed commands
        dev = self.devices.get(target_serial) if target_serial else (next(iter(self.devices.values())) if self.devices else None)
        if not dev:
            return (1, "", "error: no devices/emulators found\n")

        # 5. adb push <src> <dest>
        if subcmd == "push":
            if len(args) < 3:
                return (1, "", "Usage: adb push <local> <remote>")
            dest = args[2]
            dev.files[dest] = "pushed_content"
            return (0, f"{args[1]}: 1 file pushed, 0 skipped. 10.0 MB/s (1024 bytes in 0.000s)\n", "")

        # 6. adb install
        if subcmd == "install":
            return (0, "Performing Streamed Install\nSuccess\n", "")

        # 7. adb shell
        if subcmd == "shell":
            shell_args = args[1:]
            if not shell_args:
                return (0, "", "")
            
            # If wrapped in quotes or a single string
            if len(shell_args) == 1 and " " in shell_args[0]:
                shell_args = shlex.split(shell_args[0])

            shell_cmd = shell_args[0]

            # getprop
            if shell_cmd == "getprop":
                if len(shell_args) > 1:
                    prop_name = shell_args[1]
                    val = dev.properties.get(prop_name, "")
                    return (0, f"{val}\n", "")
                else:
                    lines = [f"[{k}]: [{v}]" for k, v in dev.properties.items()]
                    return (0, "\n".join(lines) + "\n", "")

            # settings get
            if shell_cmd == "settings" and len(shell_args) >= 3 and shell_args[1] == "get":
                namespace = shell_args[2]
                key = shell_args[3] if len(shell_args) > 3 else ""
                prop_key = f"settings.{namespace}.{key}"
                val = dev.properties.get(prop_key, "0")
                return (0, f"{val}\n", "")

            # pm
            if shell_cmd == "pm":
                pm_sub = shell_args[1] if len(shell_args) > 1 else ""
                if pm_sub == "list" and len(shell_args) > 2 and shell_args[2] == "packages":
                    flags = shell_args[3:]
                    if "-d" in flags:
                        out = [f"package:{p}" for p in sorted(dev.disabled_packages)]
                    elif "-e" in flags:
                        out = [f"package:{p}" for p in sorted(dev.installed_packages - dev.disabled_packages)]
                    else:
                        out = [f"package:{p}" for p in sorted(dev.installed_packages)]
                    return (0, "\n".join(out) + "\n" if out else "", "")

                if pm_sub == "disable-user":
                    # pm disable-user --user 0 <pkg>
                    pkg = shell_args[-1]
                    if dev.disable_package(pkg):
                        return (0, f"Package {pkg} new state: disabled-user\n", "")
                    return (1, f"Error: package {pkg} not found\n", "")

                if pm_sub == "enable":
                    pkg = shell_args[-1]
                    dev.enable_package(pkg)
                    return (0, f"Package {pkg} new state: enabled\n", "")

            # cmd package
            if shell_cmd == "cmd" and len(shell_args) >= 2 and shell_args[1] == "package":
                cmd_sub = shell_args[2]
                if cmd_sub == "set-home-activity":
                    component = shell_args[3]
                    dev.home_activity = component
                    return (0, f"Success\n", "")
                if cmd_sub == "resolve-activity":
                    lines = [
                        "priority=0 preferredOrder=0 match=0x108000 specific=false",
                        f"{dev.home_activity}",
                    ]
                    return (0, "\n".join(lines) + "\n", "")

            # cmd notification
            if shell_cmd == "cmd" and len(shell_args) >= 2 and shell_args[1] == "notification":
                if len(shell_args) >= 4 and shell_args[2] == "allow_listener":
                    listener = shell_args[3]
                    dev.notification_listeners.add(listener)
                    return (0, "Success\n", "")

            # am broadcast
            if shell_cmd == "am" and len(shell_args) >= 2 and shell_args[1] == "broadcast":
                # am broadcast -a org.opentv.launcher.RELOAD_CONFIG
                action = shell_args[-1]
                dev.broadcasts_received.append(action)
                return (0, f"Broadcasting: Intent {{ act={action} }}\nBroadcast completed: result=0\n", "")

            # input keyevent
            if shell_cmd == "input" and len(shell_args) >= 3 and shell_args[1] == "keyevent":
                try:
                    keycode = int(shell_args[2])
                    dev.recorded_keyevents.append(keycode)
                    return (0, "", "")
                except ValueError:
                    return (1, "", "invalid keycode")

            # cat / rm
            if shell_cmd == "cat":
                target_file = shell_args[1]
                if target_file in dev.files:
                    return (0, dev.files[target_file], "")
                return (1, "", f"cat: {target_file}: No such file or directory\n")

            if shell_cmd == "rm":
                target_file = shell_args[-1]
                if target_file in dev.files:
                    del dev.files[target_file]
                return (0, "", "")

        return (0, "", "")
