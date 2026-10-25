"""
Tier 1: Feature Coverage Test Suite
Validates core functionality for config parsing, profile resolution,
safety DB categorization, rollback generation, adb wrapper, and launcher intent resolution.
Requires >= 5 test cases per feature.
"""
import unittest
import tempfile
import json
from pathlib import Path

from tests.adapter import (
    LauncherConfig,
    create_default_config,
    BrandProfile,
    detect_brand_profile,
    PROFILES,
    PackageSafetyDB,
    SafetyCategory,
    GuardrailsEngine,
    RollbackEngine,
    AdbWrapper,
)

class TestConfigParsing(unittest.TestCase):
    """Core Feature 1: Configuration Schema, Parsing & Serialization."""

    def test_default_config_generation(self):
        """1.1 Verify default configuration contains all required sections and defaults."""
        config = create_default_config() if create_default_config else LauncherConfig()
        self.assertEqual(config.version, 1)
        self.assertIsInstance(config.apps, list)
        self.assertGreater(len(config.apps), 0)
        self.assertIn("com.google.android.youtube.tv", config.apps)
        self.assertIsInstance(config.quick_settings, list)
        self.assertIn("wifi", config.quick_settings)
        self.assertIn("settings", config.quick_settings)
        self.assertEqual(config.theme, "OLED_Black")
        self.assertTrue(config.oled_protection.pixel_shift_enabled)
        self.assertEqual(config.oled_protection.screensaver_idle_seconds, 180)

    def test_parse_valid_json_config(self):
        """1.2 Verify parsing and deserialization from valid JSON string."""
        sample_json = json.dumps({
            "version": 1,
            "apps": ["com.netflix.ninja", "com.spotify.tv.android"],
            "hdmi": [{"id": "HW1", "title": "Xbox Series X", "visible": True}],
            "quick_settings": ["wifi", "bluetooth", "sound"],
            "theme": "Pure_Black",
            "oled_protection": {
                "screensaver_idle_seconds": 300,
                "pixel_shift_enabled": True
            }
        })
        cfg = LauncherConfig.from_json(sample_json)
        self.assertEqual(cfg.version, 1)
        self.assertEqual(len(cfg.apps), 2)
        self.assertEqual(cfg.apps[0], "com.netflix.ninja")
        self.assertEqual(len(cfg.hdmi), 1)
        self.assertEqual(cfg.hdmi[0].title, "Xbox Series X")
        self.assertEqual(cfg.oled_protection.screensaver_idle_seconds, 300)

    def test_schema_version_enforcement(self):
        """1.3 Verify schema version enforcement and serialization."""
        cfg = LauncherConfig(version=1, apps=["com.example.app"])
        data = cfg.to_dict()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["apps"], ["com.example.app"])
        json_output = cfg.to_json()
        self.assertIn('"version": 1', json_output)

    def test_apps_ordering_and_filtering(self):
        """1.4 Verify app ordering is strictly preserved and dict items are resolved."""
        raw_dict = {
            "version": 1,
            "apps": [
                {"package_name": "app.first", "visible": True, "order": 1},
                {"package_name": "app.hidden", "visible": False, "order": 2},
                {"package_name": "app.second", "visible": True, "order": 3},
            ]
        }
        cfg = LauncherConfig.from_dict(raw_dict)
        self.assertEqual(cfg.apps, ["app.first", "app.second"])

    def test_hdmi_and_quick_settings_parsing(self):
        """1.5 Verify HDMI inputs and quick settings array deserialization."""
        raw_dict = {
            "version": 1,
            "hdmi": [
                {"id": "HW5", "title": "PS5", "visible": True},
                {"id": "HW6", "title": "Switch", "visible": False},
            ],
            "quick_settings": ["wifi", "bluetooth", "picture", "sound"]
        }
        cfg = LauncherConfig.from_dict(raw_dict)
        self.assertEqual(len(cfg.hdmi), 2)
        self.assertEqual(cfg.hdmi[0].id, "HW5")
        self.assertTrue(cfg.hdmi[0].visible)
        self.assertFalse(cfg.hdmi[1].visible)
        self.assertEqual(cfg.quick_settings, ["wifi", "bluetooth", "picture", "sound"])

    def test_oled_protection_config_deserialization(self):
        """1.6 Verify OLED burn-in protection preferences are parsed correctly."""
        raw_dict = {
            "version": 1,
            "oled_protection": {
                "screensaver_idle_seconds": 120,
                "pixel_shift_enabled": False
            }
        }
        cfg = LauncherConfig.from_dict(raw_dict)
        self.assertEqual(cfg.oled_protection.screensaver_idle_seconds, 120)
        self.assertFalse(cfg.oled_protection.pixel_shift_enabled)


class TestProfileResolution(unittest.TestCase):
    """Core Feature 2: Manufacturer & Model-Specific Profile Resolution."""

    def test_detect_sony_bravia_profile(self):
        """2.1 Verify Sony Bravia detection via getprop manufacturer and model regex."""
        props = {
            "ro.product.manufacturer": "Sony",
            "ro.product.brand": "Sony",
            "ro.product.model": "KD-55X85J",
            "ro.product.device": "bravia_atv3",
        }
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "sony")
        self.assertIn("Sony", profile.display_name)
        self.assertIn("launcherx_shield", profile.get_guardrails())

    def test_detect_tcl_profile(self):
        """2.2 Verify TCL profile detection via manufacturer and package signature."""
        props = {"ro.product.manufacturer": "TCL", "ro.product.model": "BeyondTV4"}
        profile = detect_brand_profile(props, installed_packages=["com.tcl.settings"])
        self.assertEqual(profile.brand_id, "tcl")
        self.assertIn("TCL", profile.display_name)

    def test_detect_philips_profile(self):
        """2.3 Verify Philips (TPV) detection via manufacturer and Home router package."""
        props = {"ro.product.manufacturer": "TP Vision", "ro.product.brand": "Philips"}
        profile = detect_brand_profile(props, installed_packages=["org.droidtv.homeintentresolver"])
        self.assertEqual(profile.brand_id, "philips")
        self.assertTrue(profile.requires_home_focus_test)
        self.assertEqual(profile.home_router_package, "org.droidtv.homeintentresolver")

    def test_detect_hisense_profile(self):
        """2.4 Verify Hisense Android TV detection via manufacturer and Jamdeo subsystem."""
        props = {"ro.product.manufacturer": "Hisense", "ro.product.model": "55U7G"}
        profile = detect_brand_profile(props, installed_packages=["com.jamdeo.tv.common"])
        self.assertEqual(profile.brand_id, "hisense")
        self.assertIn("Hisense", profile.display_name)

    def test_detect_xiaomi_profile(self):
        """2.5 Verify Xiaomi Mi TV / PatchWall detection via brand and PatchWall package."""
        props = {"ro.product.manufacturer": "Xiaomi", "ro.product.brand": "Redmi"}
        profile = detect_brand_profile(props, installed_packages=["com.mitv.tvhome"])
        self.assertEqual(profile.brand_id, "xiaomi")

    def test_detect_ccwgtv_and_nvidia(self):
        """2.6 Verify Chromecast with Google TV and Nvidia Shield detection."""
        ccwgtv_props = {
            "ro.product.manufacturer": "Google",
            "ro.product.device": "sabrina",
            "ro.product.model": "Chromecast",
        }
        self.assertEqual(detect_brand_profile(ccwgtv_props).brand_id, "ccwgtv")

        nvidia_props = {
            "ro.product.manufacturer": "NVIDIA",
            "ro.product.model": "SHIELD Android TV",
            "ro.product.device": "mdarcy",
        }
        self.assertEqual(detect_brand_profile(nvidia_props).brand_id, "nvidia")

    def test_detect_generic_fallback(self):
        """2.7 Verify fallback to generic profile when properties are unrecognized."""
        props = {"ro.product.manufacturer": "UnknownOEM", "ro.product.model": "CustomBox"}
        profile = detect_brand_profile(props)
        self.assertEqual(profile.brand_id, "generic")


class TestSafetyDBCategorization(unittest.TestCase):
    """Core Feature 3: Curated Package Safety Database & Categorization."""

    def setUp(self):
        self.db = PackageSafetyDB()

    def test_categorize_core_aosp_as_never(self):
        """3.1 Verify critical core system packages are strictly categorized as NEVER."""
        critical_pkgs = [
            "android",
            "com.android.systemui",
            "com.android.settings",
            "com.android.shell",
            "com.android.packageinstaller",
            "com.android.bluetooth",
            "com.google.android.gms",
        ]
        for pkg in critical_pkgs:
            category = self.db.categorize(pkg)
            self.assertEqual(category, SafetyCategory.NEVER, f"Package {pkg} must be categorized as NEVER")
            self.assertFalse(self.db.is_safe_to_disable(pkg))

    def test_categorize_input_methods_as_never(self):
        """3.2 Verify on-screen keyboards (IMEs) are protected with NEVER category."""
        ime_pkgs = [
            "com.google.android.inputmethod.latin",
            "com.android.inputmethod.latin",
            "com.tcl.inputmethod.international",
        ]
        for ime in ime_pkgs:
            self.assertEqual(self.db.categorize(ime), SafetyCategory.NEVER)

    def test_categorize_optional_services_as_keep(self):
        """3.3 Verify user features like Chromecast built-in and Assistant are KEEP."""
        keep_pkgs = [
            "com.google.android.apps.mediashell",
            "com.google.android.katniss",
            "com.google.android.marvin.talkback",
            "com.google.android.webview",
        ]
        for pkg in keep_pkgs:
            self.assertEqual(self.db.categorize(pkg), SafetyCategory.KEEP)

    def test_categorize_vendor_bloat_as_safe(self):
        """3.4 Verify confirmed vendor bloat, ads, and telemetry are categorized as SAFE."""
        safe_pkgs = [
            "com.google.android.tvrecommendations",
            "tv.samba.ssm",
            "com.tcl.waterfall.overseas",
            "org.droidtv.nettv",
            "com.mitv.tvhome.michannel",
        ]
        for pkg in safe_pkgs:
            category = self.db.categorize(pkg)
            self.assertEqual(category, SafetyCategory.SAFE, f"Package {pkg} must be SAFE")
            self.assertTrue(self.db.is_safe_to_disable(pkg))

    def test_categorize_unknown_package_as_review(self):
        """3.5 Verify any unrecognized third-party package defaults to REVIEW (enabled)."""
        unknown_pkg = "com.thirdparty.custom.streaming.app"
        self.assertEqual(self.db.categorize(unknown_pkg), SafetyCategory.REVIEW)
        self.assertFalse(self.db.is_safe_to_disable(unknown_pkg))

    def test_get_safe_debloat_candidates_filtering(self):
        """3.6 Verify filtering an installed package list produces only SAFE items."""
        installed = [
            "android",
            "com.google.android.youtube.tv",
            "tv.samba.ssm",
            "com.google.android.tvrecommendations",
            "com.android.settings",
            "com.tcl.waterfall.overseas",
        ]
        candidates = self.db.get_safe_debloat_candidates(installed)
        self.assertIn("tv.samba.ssm", candidates)
        self.assertIn("com.google.android.tvrecommendations", candidates)
        self.assertIn("com.tcl.waterfall.overseas", candidates)
        self.assertNotIn("android", candidates)
        self.assertNotIn("com.android.settings", candidates)


class TestRollbackGeneration(unittest.TestCase):
    """Core Feature 4: Standalone Reversible Rollback Engine."""

    def setUp(self):
        self.engine = RollbackEngine()
        self.sample_packages = [
            "tv.samba.ssm",
            "com.google.android.tvrecommendations",
            "com.sony.dtv.demomode",
        ]

    def test_generate_posix_shell_script(self):
        """4.1 Verify POSIX shell rollback script (.sh) generation."""
        sh_content = self.engine.generate_sh(self.sample_packages, target_device="192.168.1.50:5555")
        self.assertTrue(sh_content.startswith("#!/bin/sh"))
        self.assertIn("set -e", sh_content)
        for pkg in self.sample_packages:
            self.assertIn(f'shell pm enable "{pkg}"', sh_content)
        self.assertIn("rm -f /data/local/tmp/opentv-disabled.txt", sh_content)

    def test_generate_windows_cmd_batch_script(self):
        """4.2 Verify Windows CMD batch rollback script (.bat) generation."""
        bat_content = self.engine.generate_bat(self.sample_packages, target_device="192.168.1.50:5555")
        self.assertTrue(bat_content.startswith("@echo off"))
        for pkg in self.sample_packages:
            self.assertIn(f"shell pm enable {pkg}", bat_content)
        self.assertIn("%ERRORLEVEL%", bat_content)

    def test_generate_windows_powershell_script(self):
        """4.3 Verify Windows PowerShell rollback script (.ps1) generation."""
        ps1_content = self.engine.generate_ps1(self.sample_packages, target_device="192.168.1.50:5555")
        self.assertIn("param(", ps1_content)
        self.assertIn("$packages =", ps1_content)
        for pkg in self.sample_packages:
            self.assertIn(pkg, ps1_content)
        self.assertIn("shell pm enable $pkg", ps1_content)

    def test_rollback_launcherx_notification_listener_privilege(self):
        """4.4 Verify Google TV notification listener command is included when launcherx is modified."""
        pkgs_with_launcherx = ["com.google.android.apps.tv.launcherx", "com.google.android.tvrecommendations"]
        sh_script = self.engine.generate_sh(pkgs_with_launcherx)
        self.assertIn("cmd notification allow_listener", sh_script)
        self.assertIn("TvNotificationListenerService", sh_script)

    def test_write_rollback_scripts_to_directory(self):
        """4.5 Verify writing all rollback scripts to output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = self.engine.write_rollback_scripts(tmpdir, self.sample_packages, "192.168.1.100:5555")
            self.assertTrue(Path(paths["sh"]).is_file())
            self.assertTrue(Path(paths["bat"]).is_file())
            self.assertTrue(Path(paths["ps1"]).is_file())
            # Ensure POSIX script is executable
            mode = Path(paths["sh"]).stat().st_mode
            self.assertTrue(bool(mode & 0o111))


class TestAdbWrapper(unittest.TestCase):
    """Core Feature 5: Typed AdbWrapper Client & Command Builder."""

    def setUp(self):
        self.adb = AdbWrapper(adb_path="adb", default_device="192.168.1.50:5555")

    def test_adb_command_list_formatting(self):
        """5.1 Verify commands are returned as structured string lists (never shell=True)."""
        cmd = self.adb.build_shell_cmd(["pm", "list", "packages"])
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], "adb")
        self.assertEqual(cmd[1], "-s")
        self.assertEqual(cmd[2], "192.168.1.50:5555")
        self.assertEqual(cmd[3], "shell")
        self.assertEqual(cmd[4:], ["pm", "list", "packages"])

    def test_adb_devices_parsing(self):
        """5.2 Verify parsing `adb devices -l` output into structured objects."""
        raw_output = """List of devices attached
192.168.1.50:5555      device product:bravia model:BRAVIA_4K device:bravia transport_id:1
emulator-5554          device product:sdk_google_atv_x86 model:Android_TV device:generic transport_id:2
192.168.1.60:5555      unauthorized transport_id:3
"""
        devices = self.adb.parse_devices(raw_output)
        self.assertEqual(len(devices), 3)
        self.assertEqual(devices[0].serial, "192.168.1.50:5555")
        self.assertEqual(devices[0].state, "device")
        self.assertEqual(devices[0].model, "BRAVIA_4K")
        self.assertEqual(devices[2].state, "unauthorized")

    def test_adb_connect_and_disconnect_formatting(self):
        """5.3 Verify connection and disconnection command formatting."""
        conn_cmd = self.adb.build_connect_cmd("192.168.1.80", 5555)
        self.assertEqual(conn_cmd, ["adb", "connect", "192.168.1.80:5555"])

        disc_cmd = self.adb.build_disconnect_cmd("192.168.1.80", 5555)
        self.assertEqual(disc_cmd, ["adb", "disconnect", "192.168.1.80:5555"])

    def test_adb_pair_command_formatting(self):
        """5.4 Verify Android 11+ Wi-Fi pairing wizard command formatting."""
        pair_cmd = self.adb.build_pair_cmd("192.168.1.80", 37845, "123456")
        self.assertEqual(pair_cmd, ["adb", "pair", "192.168.1.80:37845", "123456"])

        # Non-numeric code should raise ValueError
        with self.assertRaises(ValueError):
            self.adb.build_pair_cmd("192.168.1.80", 37845, "abc-xyz")

    def test_adb_package_list_parser(self):
        """5.5 Verify package listing parser strips package: prefix and returns sorted unique list."""
        raw_output = """package:com.google.android.youtube.tv
package:com.netflix.ninja
package:com.google.android.youtube.tv
package:android
"""
        pkgs = self.adb.parse_packages(raw_output)
        self.assertEqual(pkgs, ["android", "com.google.android.youtube.tv", "com.netflix.ninja"])

    def test_adb_shell_command_builder(self):
        """5.6 Verify building keyevent and broadcast reload commands."""
        key_cmd = self.adb.build_input_keyevent_cmd(19)  # DPAD_UP
        self.assertIn("19", key_cmd)
        self.assertIn("keyevent", key_cmd)

        reload_cmd = self.adb.build_broadcast_reload_cmd()
        self.assertIn("org.opentv.launcher.RELOAD_CONFIG", reload_cmd)


class TestLauncherIntentResolution(unittest.TestCase):
    """Core Feature 6: Launcher Intent & Hardware Input Resolution."""

    def test_sony_settings_intents_resolution(self):
        """6.1 Verify Sony Bravia proprietary settings component resolution."""
        profile = PROFILES["sony"]
        settings_intent = profile.get_quick_setting_intent("settings")
        self.assertEqual(settings_intent.component, "com.sony.dtv.settings/.SettingsMainActivity")
        self.assertEqual(settings_intent.fallback_keycode, 176)

    def test_tcl_picture_sound_service_calls(self):
        """6.2 Verify TCL proprietary ShowWindowService resolution for picture and sound."""
        profile = PROFILES["tcl"]
        pic_intent = profile.get_quick_setting_intent("picture")
        self.assertEqual(pic_intent.service_call, "com.tcl.settings.SHOW_WINDOW")
        self.assertEqual(pic_intent.extras.get("Type"), "picture")

        sound_intent = profile.get_quick_setting_intent("sound")
        self.assertEqual(sound_intent.service_call, "com.tcl.settings.SHOW_WINDOW")
        self.assertEqual(sound_intent.extras.get("Type"), "SoundPreset")

    def test_philips_hdmi_passthrough_uris(self):
        """6.3 Verify Philips direct HDMI passthrough URI resolution."""
        profile = PROFILES["philips"]
        hdmi_1_uri = profile.get_hdmi_uri(1)
        self.assertIn("org.droidtv.playtv", hdmi_1_uri)
        self.assertIn("HW5", hdmi_1_uri)

        hdmi_2_uri = profile.get_hdmi_uri(2)
        self.assertIn("HW6", hdmi_2_uri)

    def test_generic_settings_and_input_fallbacks(self):
        """6.4 Verify Generic profile resolves standard AOSP intents and keycodes."""
        profile = PROFILES["generic"]
        settings_intent = profile.get_quick_setting_intent("settings")
        self.assertEqual(settings_intent.action, "android.settings.SETTINGS")
        self.assertEqual(settings_intent.fallback_keycode, 176)

        hdmi_uri = profile.get_hdmi_uri(1)
        self.assertTrue(hdmi_uri.startswith("content://android.media.tv/passthrough/"))

    def test_brand_profile_guardrails_query(self):
        """6.5 Verify brand profiles report their specific guardrails list."""
        self.assertIn("launcherx_shield", PROFILES["sony"].get_guardrails())
        self.assertIn("philips_homeintent_shield", PROFILES["philips"].get_guardrails())
        self.assertIn("tcl_suspension_shield", PROFILES["tcl"].get_guardrails())


if __name__ == "__main__":
    unittest.main()
