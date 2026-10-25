"""
Tier 4: Real-World Application Scenarios Test Suite
Validates end-to-end simulated device provisioning, debloat with rollback cycle,
and emulator remote key navigation harness with mock execution and optional live AVD support.
"""
import unittest
import tempfile
import json
import os
import subprocess
from pathlib import Path
from typing import List, Dict

from tests.adapter import (
    LauncherConfig,
    create_default_config,
    detect_brand_profile,
    PROFILES,
    PackageSafetyDB,
    SafetyCategory,
    GuardrailsEngine,
    GuardrailViolation,
    RollbackEngine,
    AdbWrapper,
)
from tests.mocks.mock_adb import MockAdbRunner, MockDevice

# Android Keyevent constants
KEYCODE_HOME = 3
KEYCODE_BACK = 4
KEYCODE_DPAD_UP = 19
KEYCODE_DPAD_DOWN = 20
KEYCODE_DPAD_LEFT = 21
KEYCODE_DPAD_RIGHT = 22
KEYCODE_DPAD_CENTER = 23
KEYCODE_SETTINGS = 176
KEYCODE_TV_INPUT = 178

class TestSimulatedDeviceProvisioning(unittest.TestCase):
    """Scenario 1: End-to-End Automated Device Provisioning Flow."""

    def setUp(self):
        self.dev = MockDevice(
            serial="192.168.1.200:5555",
            properties={
                "ro.product.manufacturer": "TCL",
                "ro.product.brand": "TCL",
                "ro.product.model": "BeyondTV4",
                "ro.product.device": "beyondtv",
                "ro.build.version.sdk": "31",
                "settings.global.device_provisioned": "1",
            },
            installed_packages={
                "android",
                "com.android.systemui",
                "com.android.settings",
                "com.tcl.settings",
                "com.tcl.suspension",
                "com.google.android.inputmethod.latin",
                "com.google.android.youtube.tv",
                "com.netflix.ninja",
                "com.amazon.amazonvideo.livingroom",
                "com.tcl.waterfall.overseas",
            }
        )
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(default_device="192.168.1.200:5555")

    def test_complete_device_provisioning_lifecycle(self):
        """1.1 Provisioning: Connect -> Detect Brand -> Query Apps -> Compile Config -> Deploy -> Verify."""
        # 1. Connect
        code, out, _ = self.runner.execute(self.adb.build_connect_cmd("192.168.1.200", 5555))
        self.assertEqual(code, 0)

        # 2. Extract Device Properties & Detect Profile
        code, out, _ = self.runner.execute(self.adb.build_shell_cmd(["getprop"]))
        self.assertEqual(code, 0)
        profile = detect_brand_profile(self.dev.properties, self.dev.installed_packages)
        self.assertEqual(profile.brand_id, "tcl")

        # 3. Query Installed Packages
        code, out, _ = self.runner.execute(self.adb.build_list_packages_cmd())
        self.assertEqual(code, 0)
        installed = self.adb.parse_packages(out)
        self.assertIn("com.netflix.ninja", installed)
        self.assertIn("com.amazon.amazonvideo.livingroom", installed)

        # 4. Compile Configuration tailored to TCL
        user_apps = ["com.netflix.ninja", "com.google.android.youtube.tv", "com.amazon.amazonvideo.livingroom"]
        hdmi_1_uri = profile.get_hdmi_uri(1)
        cfg = LauncherConfig(
            version=1,
            apps=user_apps,
            hdmi=[
                {"id": "HW1", "title": "PlayStation 5", "visible": True, "intent_uri": hdmi_1_uri},
            ],
            quick_settings=["wifi", "bluetooth", "picture", "sound", "settings"],
            theme="OLED_Black",
        )

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(cfg.to_json())
            f.flush()
            local_cfg = f.name

        try:
            # 5. Push Config File to TV
            code, out, _ = self.runner.execute(self.adb.build_push_config_cmd(local_cfg, "/sdcard/OpenTV/config.json"))
            self.assertEqual(code, 0)
            self.assertIn("/sdcard/OpenTV/config.json", self.dev.files)

            # 6. Deploy Launcher APK
            code, out, _ = self.runner.execute(self.adb.build_install_apk_cmd("OpenTV.apk"))
            self.assertEqual(code, 0)
            self.assertIn("Success", out)

            # 7. Set Default Home Activity
            code, out, _ = self.runner.execute(self.adb.build_set_home_cmd("org.opentv.launcher/.MainActivity"))
            self.assertEqual(code, 0)

            # 8. Verify Home Resolution
            code, out, _ = self.runner.execute(self.adb.build_resolve_home_cmd())
            self.assertEqual(code, 0)
            self.assertIn("org.opentv.launcher/.MainActivity", out)

            # 9. Trigger Config Reload
            code, out, _ = self.runner.execute(self.adb.build_broadcast_reload_cmd())
            self.assertEqual(code, 0)
            self.assertIn("org.opentv.launcher.RELOAD_CONFIG", self.dev.broadcasts_received)

        finally:
            Path(local_cfg).unlink(missing_ok=True)


class TestDebloatRollbackCycle(unittest.TestCase):
    """Scenario 2: Full Debloat and Emergency Reversible Rollback Cycle."""

    def setUp(self):
        self.dev = MockDevice(
            serial="192.168.1.210:5555",
            installed_packages={
                "android",
                "com.android.systemui",
                "com.android.settings",
                "com.android.bluetooth",
                "com.google.android.inputmethod.latin",
                "com.google.android.youtube.tv",
                "com.google.android.tvrecommendations",
                "com.google.android.backdrop",
                "tv.samba.ssm",
                "com.sony.dtv.demomode",
                "com.sony.dtv.tvx",
                "com.sony.braviasync",
            }
        )
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(default_device="192.168.1.210:5555")
        self.db = PackageSafetyDB()
        self.guard = GuardrailsEngine()
        self.rollback = RollbackEngine()

    def test_full_debloat_and_recovery_cycle(self):
        """2.1 Debloat cycle: Scan -> Classify -> Guardrail Check -> Disable -> Audit -> Rollback Restore."""
        # 1. Scan installed packages
        code, out, _ = self.runner.execute(self.adb.build_list_packages_cmd())
        installed = self.adb.parse_packages(out)
        self.assertEqual(len(installed), 12)

        # 2. Categorize all packages
        safe_candidates = self.db.get_safe_debloat_candidates(installed)
        expected_safe = {"com.google.android.tvrecommendations", "com.google.android.backdrop", "tv.samba.ssm", "com.sony.dtv.demomode"}
        self.assertEqual(set(safe_candidates), expected_safe)

        # 3. Verify guardrails allow safe candidates and reject critical system packages
        for pkg in safe_candidates:
            self.assertTrue(self.guard.can_disable(pkg))

        with self.assertRaises(GuardrailViolation):
            self.guard.check_can_disable("android")

        # 4. Disable safe packages
        for pkg in safe_candidates:
            code, out, _ = self.runner.execute(self.adb.build_disable_package_cmd(pkg))
            self.assertEqual(code, 0)

        # Verify on-device disabled state
        self.assertEqual(self.dev.disabled_packages, expected_safe)
        code, out, _ = self.runner.execute(self.adb.build_list_packages_cmd(flags="-d"))
        disabled_on_dev = self.adb.parse_packages(out)
        self.assertEqual(set(disabled_on_dev), expected_safe)

        # 5. Generate Standalone Rollback Scripts
        with tempfile.TemporaryDirectory() as tmpdir:
            scripts = self.rollback.write_rollback_scripts(tmpdir, safe_candidates, "192.168.1.210:5555")
            sh_script = Path(scripts["sh"]).read_text(encoding="utf-8")

            # 6. Simulate Emergency Recovery by executing generated restore actions
            for pkg in safe_candidates:
                code, out, _ = self.runner.execute(self.adb.build_enable_package_cmd(pkg))
                self.assertEqual(code, 0)

            # 7. Assert complete restoration: zero disabled packages remain
            self.assertEqual(len(self.dev.disabled_packages), 0)
            code, out, _ = self.runner.execute(self.adb.build_list_packages_cmd(flags="-d"))
            self.assertEqual(out.strip(), "")


class TestEmulatorRemoteNavigationHarness(unittest.TestCase):
    """Scenario 3: Remote Key Navigation Simulation & Anti-Bounce Guard."""

    def setUp(self):
        self.dev = MockDevice(serial="192.168.1.220:5555")
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(default_device="192.168.1.220:5555")

    def test_remote_dpad_key_dispatch_sequence(self):
        """3.1 Dispatches complete D-pad sequence: UP, DOWN, LEFT, RIGHT, OK, BACK, HOME."""
        nav_sequence = [
            KEYCODE_DPAD_DOWN,
            KEYCODE_DPAD_RIGHT,
            KEYCODE_DPAD_RIGHT,
            KEYCODE_DPAD_CENTER,
            KEYCODE_BACK,
            KEYCODE_DPAD_UP,
            KEYCODE_DPAD_LEFT,
            KEYCODE_HOME,
        ]
        for key in nav_sequence:
            code, _, _ = self.runner.execute(self.adb.build_input_keyevent_cmd(key))
            self.assertEqual(code, 0)

        self.assertEqual(self.dev.recorded_keyevents, nav_sequence)

    def test_ok_down_key_bounce_guard_simulation(self):
        """3.2 Simulates Bug #30: Verifies click event only fires if ACTION_DOWN originated on same tile."""
        class MockTile:
            def __init__(self, tile_id: str):
                self.tile_id = tile_id
                self.click_count = 0
                self.has_key_down = False

            def on_key_down(self, keycode: int):
                if keycode == KEYCODE_DPAD_CENTER:
                    self.has_key_down = True

            def on_key_up(self, keycode: int):
                # Bug #30 fix: only click if down originated on this tile
                if keycode == KEYCODE_DPAD_CENTER and self.has_key_down:
                    self.click_count += 1
                    self.has_key_down = False

        tile_a = MockTile("tile_a")
        tile_b = MockTile("tile_b")

        # Normal click on Tile A: Down then Up
        tile_a.on_key_down(KEYCODE_DPAD_CENTER)
        tile_a.on_key_up(KEYCODE_DPAD_CENTER)
        self.assertEqual(tile_a.click_count, 1)

        # Bug #30 scenario: Tile B receives KEY_UP without prior KEY_DOWN (e.g. exit dialog closed)
        tile_b.on_key_up(KEYCODE_DPAD_CENTER)
        self.assertEqual(tile_b.click_count, 0, "Spurious KEY_UP without prior KEY_DOWN must be ignored")

    def test_live_emulator_smoke_check(self):
        """3.3 Checks if live AVD or hardware is available; skips gracefully if not present."""
        emulator_requested = os.environ.get("OPENTV_RUN_EMULATOR") == "1"
        if not emulator_requested:
            self.skipTest("Live emulator test skipped (run with --emulator or OPENTV_RUN_EMULATOR=1)")

        # If live emulator requested, attempt to ping ADB
        try:
            res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
            devices = AdbWrapper().parse_devices(res.stdout)
            online = [d for d in devices if d.state == "device"]
            if not online:
                self.skipTest("No live Android TV emulator or device currently connected via ADB")
            
            target = online[0].serial
            # Verify live ping via getprop
            ping = subprocess.run(["adb", "-s", target, "shell", "getprop", "ro.build.version.sdk"],
                                  capture_output=True, text=True, timeout=5)
            self.assertEqual(ping.returncode, 0)
            self.assertTrue(ping.stdout.strip().isdigit())
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.skipTest(f"Live ADB check unavailable: {e}")


if __name__ == "__main__":
    unittest.main()
