"""
Tier 3: Cross-Feature Combinations Test Suite
Validates pairwise interactions: brand profile + debloat presets,
wireless pairing + deployment, config reload + TV input resolution,
and guardrails + audit logging + rollback integration.
"""
import unittest
import tempfile
import json
from pathlib import Path

from tests.adapter import (
    LauncherConfig,
    BrandProfile,
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

class TestBrandProfileWithDebloatPresets(unittest.TestCase):
    """Pairwise 1: Brand Profile Resolution with Safe Debloat Presets."""

    def setUp(self):
        self.db = PackageSafetyDB()
        self.guard = GuardrailsEngine()

    def test_sony_profile_with_safe_preset(self):
        """1.1 Sony Bravia profile debloat removes Samba TV ACR but guards Bravia Sync and TVX."""
        props = {"ro.product.manufacturer": "Sony", "ro.product.model": "Bravia 4K"}
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "sony")

        installed = [
            "android",
            "com.sony.dtv.tvx",
            "com.sony.braviasync",
            "tv.samba.ssm",
            "com.sony.dtv.demomode",
            "com.google.android.youtube.tv",
        ]
        safe_candidates = self.db.get_safe_debloat_candidates(installed)
        self.assertIn("tv.samba.ssm", safe_candidates)
        self.assertIn("com.sony.dtv.demomode", safe_candidates)
        self.assertNotIn("com.sony.dtv.tvx", safe_candidates)
        self.assertNotIn("com.sony.braviasync", safe_candidates)

        # Ensure critical Sony components are guarded
        for critical in ["com.sony.dtv.tvx", "com.sony.braviasync"]:
            self.assertEqual(self.db.categorize(critical), SafetyCategory.NEVER)

    def test_tcl_profile_with_safe_preset(self):
        """1.2 TCL profile debloat removes Waterfall feed but preserves TCL settings & suspension."""
        props = {"ro.product.manufacturer": "TCL", "ro.product.model": "TCL 4K TV"}
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "tcl")

        installed = [
            "com.tcl.settings",
            "com.tcl.suspension",
            "com.tcl.tvinput",
            "com.tcl.waterfall.overseas",
            "com.tcl.esticker",
            "com.tcl.messagebox",
        ]
        safe_candidates = self.db.get_safe_debloat_candidates(installed)
        self.assertIn("com.tcl.waterfall.overseas", safe_candidates)
        self.assertIn("com.tcl.esticker", safe_candidates)
        self.assertIn("com.tcl.messagebox", safe_candidates)
        self.assertNotIn("com.tcl.settings", safe_candidates)
        self.assertNotIn("com.tcl.suspension", safe_candidates)

    def test_philips_profile_with_safe_preset(self):
        """1.3 Philips profile preserves HomeIntentResolver and PlayTV HDMI while removing NetTV."""
        props = {"ro.product.manufacturer": "TP Vision", "ro.product.brand": "Philips"}
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "philips")

        installed = [
            "org.droidtv.homeintentresolver",
            "org.droidtv.playtv",
            "org.droidtv.nettv",
            "org.droidtv.philipstvcollection",
        ]
        safe_candidates = self.db.get_safe_debloat_candidates(installed)
        self.assertIn("org.droidtv.nettv", safe_candidates)
        self.assertIn("org.droidtv.philipstvcollection", safe_candidates)
        self.assertNotIn("org.droidtv.homeintentresolver", safe_candidates)
        self.assertNotIn("org.droidtv.playtv", safe_candidates)

    def test_ccwgtv_profile_blocks_launcherx_in_safe_preset(self):
        """1.4 CCwGTV profile debloat removes recommendation ads but blocks launcherx disablement."""
        props = {"ro.product.manufacturer": "Google", "ro.product.device": "sabrina"}
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "ccwgtv")

        installed = [
            "com.google.android.apps.tv.launcherx",
            "com.google.android.tvrecommendations",
            "com.google.android.backdrop",
        ]
        safe_candidates = self.db.get_safe_debloat_candidates(installed)
        self.assertIn("com.google.android.tvrecommendations", safe_candidates)
        self.assertIn("com.google.android.backdrop", safe_candidates)
        self.assertNotIn("com.google.android.apps.tv.launcherx", safe_candidates)

        # Assert guardrail triggers if launcherx is attempted
        with self.assertRaises(GuardrailViolation):
            self.guard.check_can_disable(
                package_name="com.google.android.apps.tv.launcherx",
                is_google_tv=True,
                force_google_tv=False,
            )


class TestWirelessPairingWithDeployment(unittest.TestCase):
    """Pairwise 2: Wireless Pairing Handshake with Launcher Deployment."""

    def setUp(self):
        self.dev = MockDevice(serial="192.168.1.120:5555")
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(adb_path="adb", default_device="192.168.1.120:5555")

    def test_wireless_pairing_and_deployment_workflow(self):
        """2.1 Full sequence: Wi-Fi pair -> connect -> install APK -> push config -> set Home."""
        # Step 1: Pair
        pair_cmd = self.adb.build_pair_cmd("192.168.1.120", 38450, "987654")
        code, stdout, stderr = self.runner.execute(pair_cmd)
        self.assertEqual(code, 0)
        self.assertIn("Successfully paired", stdout)

        # Step 2: Connect
        conn_cmd = self.adb.build_connect_cmd("192.168.1.120", 5555)
        code, stdout, stderr = self.runner.execute(conn_cmd)
        self.assertEqual(code, 0)
        self.assertIn("connected to", stdout)

        # Step 3: Install Launcher APK
        install_cmd = self.adb.build_install_apk_cmd("/path/to/OpenTV.apk", target_device="192.168.1.120:5555")
        code, stdout, stderr = self.runner.execute(install_cmd)
        self.assertEqual(code, 0)
        self.assertIn("Success", stdout)

        # Step 4: Push Config JSON
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            cfg = LauncherConfig(apps=["com.netflix.ninja", "com.google.android.youtube.tv"])
            f.write(cfg.to_json())
            f.flush()
            temp_path = f.name

        try:
            push_cmd = self.adb.build_push_config_cmd(temp_path, "/sdcard/OpenTV/config.json", target_device="192.168.1.120:5555")
            code, stdout, stderr = self.runner.execute(push_cmd)
            self.assertEqual(code, 0)
            self.assertIn("/sdcard/OpenTV/config.json", self.dev.files)

            # Step 5: Broadcast Reload
            reload_cmd = self.adb.build_broadcast_reload_cmd(target_device="192.168.1.120:5555")
            code, stdout, stderr = self.runner.execute(reload_cmd)
            self.assertEqual(code, 0)
            self.assertIn("org.opentv.launcher.RELOAD_CONFIG", self.dev.broadcasts_received)

            # Step 6: Set Home Activity
            home_cmd = self.adb.build_set_home_cmd("org.opentv.launcher/.MainActivity", target_device="192.168.1.120:5555")
            code, stdout, stderr = self.runner.execute(home_cmd)
            self.assertEqual(code, 0)
            self.assertEqual(self.dev.home_activity, "org.opentv.launcher/.MainActivity")

            # Step 7: Verify Home Resolution
            resolve_cmd = self.adb.build_resolve_home_cmd(target_device="192.168.1.120:5555")
            code, stdout, stderr = self.runner.execute(resolve_cmd)
            self.assertEqual(code, 0)
            self.assertIn("org.opentv.launcher/.MainActivity", stdout)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestConfigReloadWithTvInputResolution(unittest.TestCase):
    """Pairwise 3: Config Reload Broadcast with Dynamic TV Input Resolution."""

    def setUp(self):
        self.dev = MockDevice(serial="192.168.1.150:5555")
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(default_device="192.168.1.150:5555")

    def test_config_reload_updates_hdmi_passthrough_uris(self):
        """3.1 Updating config with brand profile HDMI URIs and broadcasting RELOAD_CONFIG."""
        profile = PROFILES["sony"]
        hdmi_1_uri = profile.get_hdmi_uri(1)
        hdmi_2_uri = profile.get_hdmi_uri(2)

        cfg_dict = {
            "version": 1,
            "apps": ["com.netflix.ninja"],
            "hdmi": [
                {"id": "HW0", "title": "PlayStation 5", "visible": True, "intent_uri": hdmi_1_uri},
                {"id": "HW1", "title": "Nintendo Switch", "visible": True, "intent_uri": hdmi_2_uri},
            ],
            "quick_settings": ["wifi", "sound", "picture"]
        }
        cfg = LauncherConfig.from_dict(cfg_dict)
        self.assertEqual(cfg.hdmi[0].intent_uri, hdmi_1_uri)
        self.assertEqual(cfg.hdmi[1].intent_uri, hdmi_2_uri)

        # Push to simulated TV
        push_cmd = self.adb.build_push_config_cmd("local_config.json", "/sdcard/OpenTV/config.json")
        code, stdout, stderr = self.runner.execute(push_cmd)
        self.assertEqual(code, 0)

        # Trigger reload broadcast
        reload_cmd = self.adb.build_broadcast_reload_cmd()
        code, stdout, stderr = self.runner.execute(reload_cmd)
        self.assertEqual(code, 0)
        self.assertIn("org.opentv.launcher.RELOAD_CONFIG", self.dev.broadcasts_received)


class TestGuardrailsAuditRollbackIntegration(unittest.TestCase):
    """Pairwise 4: Guardrails + Audit Logging + Standalone Rollback Cycle."""

    def setUp(self):
        self.dev = MockDevice(serial="192.168.1.180:5555")
        self.runner = MockAdbRunner([self.dev])
        self.adb = AdbWrapper(default_device="192.168.1.180:5555")
        self.guard = GuardrailsEngine()
        self.rollback = RollbackEngine()

    def test_debloat_audit_and_rollback_flow(self):
        """4.1 Debloating packages records on-device registry, generates rollback scripts, and restores."""
        packages_to_disable = ["tv.samba.ssm", "com.sony.dtv.demomode"]

        # Validate through guardrails
        for pkg in packages_to_disable:
            self.guard.check_can_disable(pkg)

        # Disable via ADB
        disabled_log = []
        for pkg in packages_to_disable:
            disable_cmd = self.adb.build_disable_package_cmd(pkg)
            code, stdout, stderr = self.runner.execute(disable_cmd)
            self.assertEqual(code, 0)
            disabled_log.append({
                "package": pkg,
                "timestamp": "2026-10-25T14:30:00Z",
                "status": "disabled-user"
            })

        # Verify on-device registry was updated
        cat_cmd = self.adb.build_shell_cmd(["cat", "/data/local/tmp/opentv-disabled.txt"])
        code, stdout, stderr = self.runner.execute(cat_cmd)
        self.assertEqual(code, 0)
        for pkg in packages_to_disable:
            self.assertIn(pkg, stdout)

        # Write audit log to temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "audit_log.json"
            audit_path.write_text(json.dumps(disabled_log, indent=2))
            self.assertTrue(audit_path.is_file())

            # Generate rollback scripts
            scripts = self.rollback.write_rollback_scripts(tmpdir, packages_to_disable, "192.168.1.180:5555")
            self.assertTrue(Path(scripts["sh"]).exists())

            # Simulate executing rollback: re-enable packages
            for pkg in packages_to_disable:
                enable_cmd = self.adb.build_enable_package_cmd(pkg)
                code, stdout, stderr = self.runner.execute(enable_cmd)
                self.assertEqual(code, 0)

            # Clear on-device registry
            rm_cmd = self.adb.build_shell_cmd(["rm", "-f", "/data/local/tmp/opentv-disabled.txt"])
            self.runner.execute(rm_cmd)

            # Assert device state is fully restored
            self.assertEqual(len(self.dev.disabled_packages), 0)
            self.assertNotIn("/data/local/tmp/opentv-disabled.txt", self.dev.files)


if __name__ == "__main__":
    unittest.main()
