"""
Tier 2: Boundary & Corner Cases Test Suite
Tests extreme inputs, empty configs, invalid IPs, malformed package names,
security guardrails, all-IME protection, SetupWraith prevention, non-TTY fallbacks,
and cross-platform Windows path formatting.
"""
import unittest
import io
import sys
from pathlib import Path

from tests.adapter import (
    LauncherConfig,
    AdbWrapper,
    GuardrailsEngine,
    GuardrailViolation,
    TerminalController,
    FallbackLineEngine,
    RollbackEngine,
)

class TestEmptyAndMalformedConfig(unittest.TestCase):
    """Boundary Area 1: Empty and Malformed Configuration Handling."""

    def test_empty_config_json_string(self):
        """1.1 Empty JSON string returns valid default config without crashing."""
        cfg = LauncherConfig.from_json("")
        self.assertEqual(cfg.version, 1)
        self.assertGreater(len(cfg.apps), 0)

    def test_empty_config_dict(self):
        """1.2 Empty dictionary returns valid default config with version 1."""
        cfg = LauncherConfig.from_dict({})
        self.assertEqual(cfg.version, 1)
        self.assertIsInstance(cfg.apps, list)

    def test_corrupt_json_string(self):
        """1.3 Syntax errors in JSON configuration raise ValueError."""
        corrupt_json = "{version: 1, apps: [unquoted]}"
        with self.assertRaises(Exception):
            LauncherConfig.from_json(corrupt_json)

    def test_unsupported_future_version(self):
        """1.4 Unsupported schema versions (e.g. version 99) raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            LauncherConfig.from_dict({"version": 99})
        self.assertIn("Unsupported config schema version", str(ctx.exception))

    def test_invalid_types_in_config(self):
        """1.5 Non-list apps attribute raises ValueError."""
        with self.assertRaises(ValueError):
            LauncherConfig.from_dict({"version": 1, "apps": "not-a-list"})

    def test_negative_screensaver_idle_seconds(self):
        """1.6 Negative idle seconds raises ValueError."""
        with self.assertRaises(ValueError):
            LauncherConfig.from_dict({
                "version": 1,
                "oled_protection": {"screensaver_idle_seconds": -60}
            })


class TestNetworkBoundaryAndInvalidIP(unittest.TestCase):
    """Boundary Area 2: Network Boundaries, Invalid IPs and Port Ranges."""

    def setUp(self):
        self.adb = AdbWrapper()

    def test_invalid_ip_octets(self):
        """2.1 Octets > 255 raise ValueError."""
        invalid_ips = ["999.999.999.999", "256.0.0.1", "192.168.300.1"]
        for ip in invalid_ips:
            with self.assertRaises(ValueError):
                self.adb.validate_ip(ip)

    def test_malformed_ip_strings(self):
        """2.2 Malformed IP strings and partial IPs raise ValueError."""
        malformed = ["not-an-ip", "192.168.1", "192.168.1.1.1", "192.168.1.foo"]
        for ip in malformed:
            with self.assertRaises(ValueError):
                self.adb.validate_ip(ip)

    def test_port_boundary_limits(self):
        """2.3 Port 0 and 65536 raise ValueError; ports 1 and 65535 succeed."""
        self.assertEqual(self.adb.validate_port(1), 1)
        self.assertEqual(self.adb.validate_port(65535), 65535)
        self.assertEqual(self.adb.validate_port(5555), 5555)

        with self.assertRaises(ValueError):
            self.adb.validate_port(0)
        with self.assertRaises(ValueError):
            self.adb.validate_port(65536)
        with self.assertRaises(ValueError):
            self.adb.validate_port(-1)

    def test_non_numeric_port(self):
        """2.4 Non-numeric ports raise ValueError."""
        with self.assertRaises(ValueError):
            self.adb.validate_port("5555_tcp")

    def test_empty_or_whitespace_host(self):
        """2.5 Empty or whitespace host strings raise ValueError."""
        with self.assertRaises(ValueError):
            self.adb.validate_ip("")
        with self.assertRaises(ValueError):
            self.adb.validate_ip("   ")


class TestMalformedPackageNames(unittest.TestCase):
    """Boundary Area 3: Malformed Package Names and Injection Payloads."""

    def setUp(self):
        self.guard = GuardrailsEngine()

    def test_empty_package_name(self):
        """3.1 Empty string or non-string raises ValueError."""
        with self.assertRaises(ValueError):
            self.guard.validate_package_name("")
        with self.assertRaises(ValueError):
            self.guard.validate_package_name(None)  # type: ignore

    def test_shell_command_injection_semicolon(self):
        """3.2 Shell command separators (; rm -rf) raise ValueError."""
        payload = "com.foo.app; rm -rf /"
        with self.assertRaises(ValueError) as ctx:
            self.guard.validate_package_name(payload)
        self.assertIn("illegal shell characters", str(ctx.exception))

    def test_shell_metacharacters(self):
        """3.3 Shell command expansion metacharacters raise ValueError."""
        payloads = [
            "com.foo$(whoami)",
            "com.foo`id`",
            "com.foo|cat",
            "com.foo&&reboot",
            "com.foo>dump.txt",
        ]
        for p in payloads:
            with self.assertRaises(ValueError):
                self.guard.validate_package_name(p)

    def test_spaces_and_quotes(self):
        """3.4 Spaces and quotes in package names raise ValueError."""
        for p in ["com.foo app", "com.foo'app", 'com.foo"app', "com.foo\\app"]:
            with self.assertRaises(ValueError):
                self.guard.validate_package_name(p)

    def test_single_segment_package_name(self):
        """3.5 Single segment non-domain strings raise ValueError."""
        with self.assertRaises(ValueError):
            self.guard.validate_package_name("standalone")


class TestAllImeDisablePrevention(unittest.TestCase):
    """Boundary Area 4: All-IME Disable Prevention (Keyboard Safety)."""

    def setUp(self):
        self.guard = GuardrailsEngine()

    def test_disabling_only_installed_ime_is_blocked(self):
        """4.1 Disabling the only installed keyboard raises GuardrailViolation."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                package_name="com.google.android.inputmethod.latin",
                installed_packages=["com.google.android.inputmethod.latin"],
                disabled_packages=[],
            )
        self.assertIn("last remaining Input Method", str(ctx.exception))

    def test_disabling_last_active_ime_is_blocked(self):
        """4.2 Disabling the last enabled IME when others are already disabled is blocked."""
        installed = ["com.google.android.inputmethod.latin", "com.android.inputmethod.latin"]
        disabled = ["com.android.inputmethod.latin"]
        with self.assertRaises(GuardrailViolation):
            self.guard.check_can_disable(
                package_name="com.google.android.inputmethod.latin",
                installed_packages=installed,
                disabled_packages=disabled,
            )

    def test_disabling_ime_when_another_is_active_succeeds(self):
        """4.3 Disabling one IME when another active IME remains is allowed."""
        installed = ["com.google.android.inputmethod.latin", "com.android.inputmethod.latin"]
        # Disabling AOSP keyboard while Gboard remains enabled should succeed
        self.assertTrue(
            self.guard.can_disable(
                package_name="com.android.inputmethod.latin",
                installed_packages=installed,
                disabled_packages=[],
            )
        )


class TestSetupWraithAndBootloopGuardrails(unittest.TestCase):
    """Boundary Area 5: Google TV SetupWraith & Bootloop Guardrails."""

    def setUp(self):
        self.guard = GuardrailsEngine()

    def test_google_tv_launcherx_blocked_without_force(self):
        """5.1 Disabling launcherx on Google TV without force_google_tv=True raises GuardrailViolation."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                package_name="com.google.android.apps.tv.launcherx",
                is_google_tv=True,
                force_google_tv=False,
            )
        self.assertIn("prevent bootloops", str(ctx.exception))

    def test_google_tv_launcherx_allowed_when_explicitly_forced(self):
        """5.2 Disabling launcherx on Google TV with explicit force flag is allowed."""
        self.assertTrue(
            self.guard.can_disable(
                package_name="com.google.android.apps.tv.launcherx",
                is_google_tv=True,
                force_google_tv=True,
            )
        )

    def test_unprovisioned_device_setupwraith_blocked(self):
        """5.3 Disabling setup wizard when device_provisioned != 1 raises GuardrailViolation."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                package_name="com.google.android.tungsten.setupwraith",
                device_provisioned=0,
            )
        self.assertIn("not fully provisioned", str(ctx.exception))

    def test_provisioned_device_setupwraith_allowed(self):
        """5.4 Disabling setup wizard when device_provisioned == 1 is permitted."""
        self.assertTrue(
            self.guard.can_disable(
                package_name="com.google.android.tungsten.setupwraith",
                device_provisioned=1,
            )
        )

    def test_persistent_flag_package_rejection(self):
        """5.5 Disabling any package marked PERSISTENT raises GuardrailViolation."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                package_name="com.tcl.guard",
                pkg_flags="pkgFlags=[ SYSTEM PERSISTENT ]",
            )
        self.assertIn("marked PERSISTENT", str(ctx.exception))


class TestNonTtyFallback(unittest.TestCase):
    """Boundary Area 6: Non-TTY & Dumb Terminal Fallbacks."""

    def test_terminal_controller_detects_non_tty(self):
        """6.1 Non-TTY streams return is_tty=False and clean unstyled strings."""
        fake_stdin = io.StringIO()
        fake_stdout = io.StringIO()
        ctrl = TerminalController(stdin=fake_stdin, stdout=fake_stdout)
        self.assertFalse(ctrl.is_tty)
        self.assertEqual(ctrl.clear_screen(), "")
        self.assertEqual(ctrl.invert("Text"), "[Text]")
        self.assertEqual(ctrl.bold("Text"), "Text")

    def test_fallback_line_engine_choice_default(self):
        """6.2 Empty input returns the default selection index."""
        fake_input = io.StringIO("\n")
        fake_output = io.StringIO()
        engine = FallbackLineEngine(
            input_fn=lambda prompt="": fake_input.readline(),
            output_fn=lambda msg="": fake_output.write(msg + "\n"),
        )
        choice = engine.prompt_choice("Select Profile", ["Sony", "TCL", "Generic"], default_index=2)
        self.assertEqual(choice, 2)

    def test_fallback_line_engine_choice_explicit(self):
        """6.3 Explicit numeric entry returns zero-indexed selection."""
        fake_input = io.StringIO("2\n")
        engine = FallbackLineEngine(input_fn=lambda prompt="": fake_input.readline(), output_fn=lambda msg="": None)
        choice = engine.prompt_choice("Select Profile", ["Sony", "TCL", "Generic"])
        self.assertEqual(choice, 1)

    def test_fallback_line_engine_multiselect(self):
        """6.4 Comma-separated indices toggle multiselect options."""
        fake_input = io.StringIO("1, 3\n")
        engine = FallbackLineEngine(input_fn=lambda prompt="": fake_input.readline(), output_fn=lambda msg="": None)
        selected = engine.prompt_multiselect("Select Apps", ["App A", "App B", "App C"])
        self.assertEqual(selected, [0, 2])

    def test_fallback_line_engine_prompt_text_with_default(self):
        """6.5 Text prompt returns default string when input is empty."""
        fake_input = io.StringIO("\n")
        engine = FallbackLineEngine(input_fn=lambda prompt="": fake_input.readline(), output_fn=lambda msg="": None)
        text = engine.prompt_text("Enter TV IP", default="192.168.1.50")
        self.assertEqual(text, "192.168.1.50")


class TestWindowsPathFormatting(unittest.TestCase):
    """Boundary Area 7: Windows Path Formatting & Git Bash Protection."""

    def setUp(self):
        self.engine = RollbackEngine()

    def test_windows_batch_carriage_returns(self):
        """7.1 Windows CMD batch scripts strictly use CRLF (\\r\\n) line endings."""
        bat = self.engine.generate_bat(["tv.samba.ssm"])
        self.assertIn("\r\n", bat)
        self.assertTrue(bat.endswith("\r\n"))

    def test_git_bash_device_tmp_path_preservation(self):
        """7.2 Device path /data/local/tmp/... is quoted to prevent Git Bash path expansion."""
        sh_script = self.engine.generate_sh(["tv.samba.ssm"])
        self.assertIn('"rm -f /data/local/tmp/opentv-disabled.txt"', sh_script)

    def test_powershell_target_parameter(self):
        """7.3 PowerShell script supports parameter override for target TV address."""
        ps1 = self.engine.generate_ps1(["tv.samba.ssm"], target_device="10.0.0.5:5555")
        self.assertIn('$Target = "10.0.0.5:5555"', ps1)


if __name__ == "__main__":
    unittest.main()
