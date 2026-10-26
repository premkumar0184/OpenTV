"""
OpenTV Adversarial Security, Injection Defense, & Parser Hardening Tests.
Phase 1 & Phase 4:
- ADB shell command injection prevention (package names, components, system properties)
- Non-UTF-8 byte stream resilience
- Binary mDNS packet parser cycle/pointer loop elimination and RFC 1035 limits
- Terminal dimension bounds clamping
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "companion"))

from opentv.core.adb import AdbWrapper
from opentv.core.device import DeviceManager
from opentv.core.deployer import LauncherDeployer
from opentv.core.discovery import parse_dns_name, fetch_ssdp_descriptor
from opentv.tui.terminal import TerminalController


class TestAdversarialSecurity(unittest.TestCase):

    def setUp(self):
        self.adb = AdbWrapper()

    # -------------------------------------------------------------------------
    # 1. Package Name Injection Defense
    # -------------------------------------------------------------------------

    def test_package_name_valid_inputs(self):
        valid = [
            "android",
            "com.android.tv",
            "org.opentv.launcher",
            "tv.samba.ssm",
            "com.example_123.app",
            "a.b.c.d",
        ]
        for pkg in valid:
            self.assertEqual(self.adb.validate_package_name(pkg), pkg)

    def test_package_name_injection_attempts(self):
        injections = [
            "com.app; reboot",
            "com.app && reboot",
            "com.app || reboot",
            "com.app | rm -rf /",
            "com.app $(reboot)",
            "com.app `reboot`",
            "com.app\nreboot",
            "com.app > /dev/null",
            "com.app < /dev/null",
            "com.app&",
            "com.app 123",
            " com.app",
            "com.app ",
            "",
            "   ",
            "com..app",
            ".com.app",
            "com.app.",
            "com/app",
            "com\\app",
            "a" * 257,  # Exceeds max length
        ]
        for attack in injections:
            with self.subTest(attack=attack):
                with self.assertRaises(ValueError):
                    self.adb.validate_package_name(attack)

    def test_adb_commands_reject_malicious_packages(self):
        malicious = "com.evil.app; reboot"
        with self.assertRaises(ValueError):
            self.adb.build_disable_package_cmd(malicious)
        with self.assertRaises(ValueError):
            self.adb.build_enable_package_cmd(malicious)
        with self.assertRaises(ValueError):
            self.adb.build_dumpsys_package_cmd(malicious)

    # -------------------------------------------------------------------------
    # 2. Component Injection Defense
    # -------------------------------------------------------------------------

    def test_component_valid_inputs(self):
        valid = [
            "org.opentv.launcher/.MainActivity",
            "com.android.tv/com.android.tv.MainActivity",
            "tv.danmaku.bili/.ui.splash.SplashActivity",
        ]
        for comp in valid:
            self.assertEqual(self.adb.validate_component(comp), comp)

    def test_component_injection_attempts(self):
        injections = [
            "org.opentv.launcher/.MainActivity; reboot",
            "org.opentv.launcher/.MainActivity && rm -rf /",
            "org.opentv.launcher/.MainActivity $(whoami)",
            "org.opentv.launcher/.MainActivity `id`",
            "org.opentv.launcher/.MainActivity\nreboot",
            "org.opentv.launcher",
            "/MainActivity",
            "org.opentv.launcher/",
            "org.opentv.launcher//MainActivity",
            "",
            "a" * 513,
        ]
        for attack in injections:
            with self.subTest(attack=attack):
                with self.assertRaises(ValueError):
                    self.adb.validate_component(attack)

    def test_set_home_rejects_malicious_component(self):
        with self.assertRaises(ValueError):
            self.adb.build_set_home_cmd("org.opentv.launcher/.MainActivity; reboot")

    # -------------------------------------------------------------------------
    # 3. System Property Name Injection Defense
    # -------------------------------------------------------------------------

    def test_getprop_valid_inputs(self):
        valid = [
            "ro.product.model",
            "ro.build.version.release",
            "ro.oem.brand-name",
            "vendor.display.oled_mode",
        ]
        for prop in valid:
            cmd = self.adb.build_getprop_cmd(prop)
            self.assertIn(prop, cmd)

    def test_getprop_injection_rejection(self):
        injections = [
            "ro.product.model; reboot",
            "ro.model && ls",
            "ro.model | rm -rf /",
            "ro.model $(reboot)",
            "ro.model `reboot`",
            "ro.model\nreboot",
            "ro model",
        ]
        for attack in injections:
            with self.subTest(attack=attack):
                with self.assertRaises(ValueError):
                    self.adb.build_getprop_cmd(attack)

    # -------------------------------------------------------------------------
    # 4. Binary mDNS Packet Parser Hardening (Cycles, Bounds, RFC 1035)
    # -------------------------------------------------------------------------

    def test_parse_dns_name_pointer_self_cycle(self):
        # 0xC000 points to offset 0 (direct infinite cycle)
        data = b"\xc0\x00"
        name, next_off = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(next_off, 2)

    def test_parse_dns_name_mutual_pointer_cycle(self):
        # Offset 0: pointer to offset 2 (\xc0\x02)
        # Offset 2: pointer to offset 0 (\xc0\x00)
        data = b"\xc0\x02\xc0\x00"
        name, next_off = parse_dns_name(data, 0)
        self.assertEqual(name, "")
        self.assertEqual(next_off, 2)

    def test_parse_dns_name_invalid_reserved_label_bits(self):
        # 0x40 (binary 01000000) or 0x80 (binary 10000000) are reserved by RFC 1035
        data = b"\x45invalid"
        name, next_off = parse_dns_name(data, 0)
        self.assertEqual(name, "")

    def test_parse_dns_name_label_exceeding_63_bytes(self):
        # RFC 1035 section 2.3.4: individual label length <= 63 octets
        oversized = bytes([64]) + b"a" * 64 + b"\x00"
        name, next_off = parse_dns_name(oversized, 0)
        self.assertEqual(name, "")

    def test_parse_dns_name_valid_hybrid(self):
        # Label "test", followed by null byte
        data = b"\x04test\x00"
        name, next_off = parse_dns_name(data, 0)
        self.assertEqual(name, "test")
        self.assertEqual(next_off, 6)

    def test_fetch_ssdp_descriptor_url_scheme_validation(self):
        # Non-http/https locations must be rejected immediately without network requests
        self.assertEqual(fetch_ssdp_descriptor("file:///etc/passwd"), {})
        self.assertEqual(fetch_ssdp_descriptor("ftp://evil.com/desc.xml"), {})
        self.assertEqual(fetch_ssdp_descriptor("javascript:alert(1)"), {})
        self.assertEqual(fetch_ssdp_descriptor(""), {})

    # -------------------------------------------------------------------------
    # 5. Non-UTF-8 Subprocess Decoding Resilience
    # -------------------------------------------------------------------------

    def test_device_manager_non_utf8_output_resilience(self):
        # Mock runner returning non-UTF-8 bytes or error replacement
        mock_runner = MagicMock(return_value=(0, "Model: \ufffd\ufffd Sony", ""))
        dm = DeviceManager(runner=mock_runner)
        info = dm.get_device_info("192.168.1.50:5555")
        self.assertIsNotNone(info)

    def test_deployer_callable_runner_dispatch(self):
        called_cmd = []
        def dummy_runner(cmd):
            called_cmd.append(cmd)
            return (0, "Success", "")

        deployer = LauncherDeployer(runner=dummy_runner)
        code, out, err = deployer._run_cmd(["adb", "version"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "Success")
        self.assertEqual(called_cmd, [["adb", "version"]])

    # -------------------------------------------------------------------------
    # 6. Terminal Controller Dimension Clamping
    # -------------------------------------------------------------------------

    def test_terminal_dimensions_clamped_to_minimum_bounds(self):
        tc = TerminalController()
        cols, lines = tc.get_size()
        self.assertGreaterEqual(cols, 80)
        self.assertGreaterEqual(lines, 24)


if __name__ == "__main__":
    unittest.main()
