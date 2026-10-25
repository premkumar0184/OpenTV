"""
Milestone 5 Phase 2: Tier 5 Adversarial Coverage Hardening — Core & TUI.
Author: Challenger 1 (Milestone 5 Phase 2)
Audited targets:
- companion/opentv/core/device.py
- companion/opentv/core/deployer.py
- companion/opentv/core/adb.py
- companion/opentv/core/config.py
- companion/opentv/tui/app.py
- companion/opentv/tui/fallback.py
- companion/opentv/tui/terminal.py
- companion/opentv/cli.py

Tests uncovered branches, boundary inputs, failure recovery, auto-selection precedence,
scoped storage pushes, retry paths, guardrail filtering, and non-TTY TUI workflows.
Uses 100% Python standard library (unittest) with zero pip dependencies.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANION_DIR = REPO_ROOT / "companion"
if str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from opentv.core.adb import AdbClient, AdbDevice, AdbWrapper
from opentv.core.config import (
    DEFAULT_THEME,
    HdmiInputConfig,
    LauncherConfig,
    OledProtectionConfig,
    create_default_config,
)
from opentv.core.deployer import (
    ApkInstallError,
    ConfigPushError,
    DeployResult,
    DeploySummary,
    DeployerError,
    HomeActivityError,
    HomeVerificationError,
    LauncherDeployer,
)
from opentv.core.device import (
    ActivityComponent,
    AmbiguousDeviceError,
    DeviceConnectionError,
    DeviceError,
    DeviceInfo,
    DeviceInterrogationError,
    DeviceManager,
    NoDeviceConnectedError,
    PackageInfo,
)
from opentv.debloat.database import PackageSafetyDB, SafetyCategory
from opentv.debloat.guardrails import GuardrailViolation, GuardrailsEngine
from opentv.debloat.rollback import RollbackEngine
from opentv.profiles.detector import BrandProfile, detect_brand_profile
from opentv.tui.app import AppState, KeyCode, KeyEvent, OpenTVApp, RawTerminalEngine
from opentv.tui.fallback import FallbackLineEngine
from opentv.tui.terminal import TerminalController
import opentv.cli as cli

from tests.mocks.mock_adb import MockAdbRunner, MockDevice


# ==============================================================================
# Suite 1: DeviceManager & Device Models Adversarial Hardening
# ==============================================================================

class TestDeviceManagerAdversarial(unittest.TestCase):
    """Probes uncovered branches, boundary conditions, and error recovery in core/device.py."""

    def test_activity_component_variants(self):
        """Verifies component_name formatting with leading dot, fully-qualified name, and existing slash."""
        # Leading dot
        comp1 = ActivityComponent(package_name="org.opentv.launcher", activity_name=".MainActivity")
        self.assertEqual(comp1.component_name, "org.opentv.launcher/.MainActivity")

        # Existing slash
        comp2 = ActivityComponent(package_name="pkg", activity_name="other.pkg/other.Act")
        self.assertEqual(comp2.component_name, "other.pkg/other.Act")

        # Without leading dot or slash
        comp3 = ActivityComponent(package_name="com.netflix.ninja", activity_name="MainActivity")
        self.assertEqual(comp3.component_name, "com.netflix.ninja/MainActivity")

        # to_dict check
        d = comp1.to_dict()
        self.assertEqual(d["package_name"], "org.opentv.launcher")
        self.assertEqual(d["component_name"], "org.opentv.launcher/.MainActivity")

    def test_package_info_to_dict(self):
        """Validates PackageInfo default properties and dictionary serialization."""
        pkg = PackageInfo(
            package_name="com.test.app",
            is_system=True,
            is_enabled=False,
            app_label="Test App",
            launchable_activity="com.test.app/.Main",
            is_tv_app=True,
        )
        d = pkg.to_dict()
        self.assertEqual(d["package_name"], "com.test.app")
        self.assertTrue(d["is_system"])
        self.assertFalse(d["is_enabled"])
        self.assertEqual(d["app_label"], "Test App")
        self.assertEqual(d["launchable_activity"], "com.test.app/.Main")
        self.assertTrue(d["is_tv_app"])

    def test_device_info_display_summary_and_serialization(self):
        """Tests TV vs non-TV summary strings, wireless detection, and serialization."""
        prof = detect_brand_profile({"ro.product.manufacturer": "Sony"})
        dev_tv = DeviceInfo(
            serial="192.168.1.100:5555",
            model="BRAVIA 4K",
            brand="Sony",
            manufacturer="Sony",
            android_version="12",
            sdk_level=31,
            is_tv=True,
            profile=prof,
        )
        self.assertTrue(dev_tv.is_wireless)
        self.assertIn("(TV, Android 12, SDK 31)", dev_tv.display_summary())

        dev_phone = DeviceInfo(
            serial="USB123456",
            model="Pixel",
            brand="Google",
            manufacturer="Google",
            android_version="14",
            sdk_level=34,
            is_tv=False,
            profile=prof,
        )
        self.assertFalse(dev_phone.is_wireless)
        self.assertIn("(Device, Android 14, SDK 34)", dev_phone.display_summary())

        d = dev_tv.to_dict()
        self.assertEqual(d["serial"], "192.168.1.100:5555")
        self.assertTrue(d["is_wireless"])
        self.assertTrue(d["is_tv"])

    def test_select_target_device_explicit_target(self):
        """Explicit target string is trimmed and returned without device query."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        self.assertEqual(dm.select_target_device("  192.168.1.50:5555  "), "192.168.1.50:5555")

    def test_select_target_device_default_serial(self):
        """Default serial configured on DeviceManager is returned when target is None."""
        runner = MockAdbRunner([])
        dm = DeviceManager(default_serial="DEFAULT_DEVICE", runner=runner)
        self.assertEqual(dm.select_target_device(None), "DEFAULT_DEVICE")

    def test_select_target_device_no_devices_raises(self):
        """Raises NoDeviceConnectedError when no devices are connected."""
        runner = MockAdbRunner([])
        runner.devices.clear()
        dm = DeviceManager(runner=runner)
        with self.assertRaises(NoDeviceConnectedError):
            dm.select_target_device(None)

    def test_select_target_device_all_offline_raises(self):
        """Raises NoDeviceConnectedError when all attached devices are offline or unauthorized."""
        dev = MockDevice(serial="offline_device", state="offline")
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        with self.assertRaises(NoDeviceConnectedError):
            dm.select_target_device(None)

    def test_select_target_device_single_online(self):
        """Auto-selects single online device."""
        dev = MockDevice(serial="single_device:5555", state="device")
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        self.assertEqual(dm.select_target_device(None), "single_device:5555")

    def test_select_target_device_usb_precedence_over_network(self):
        """Crucial heuristic: when exactly 1 USB device and 1+ wireless devices exist, USB device is auto-selected."""
        usb_dev = MockDevice(serial="USB_PHYSICAL_CABLE", state="device")
        net_dev1 = MockDevice(serial="192.168.1.10:5555", state="device")
        net_dev2 = MockDevice(serial="192.168.1.11:5555", state="device")
        runner = MockAdbRunner([usb_dev, net_dev1, net_dev2])
        dm = DeviceManager(runner=runner)
        # Should pick the USB device without raising AmbiguousDeviceError
        self.assertEqual(dm.select_target_device(None), "USB_PHYSICAL_CABLE")

    def test_select_target_device_ambiguous_multiple_usb(self):
        """Raises AmbiguousDeviceError when multiple physical USB devices are attached."""
        usb1 = MockDevice(serial="USB_DEV_1", state="device")
        usb2 = MockDevice(serial="USB_DEV_2", state="device")
        runner = MockAdbRunner([usb1, usb2])
        dm = DeviceManager(runner=runner)
        with self.assertRaises(AmbiguousDeviceError) as ctx:
            dm.select_target_device(None)
        self.assertEqual(len(ctx.exception.devices), 2)

    def test_select_target_device_ambiguous_multiple_wireless(self):
        """Raises AmbiguousDeviceError when multiple wireless devices and no USB device exist."""
        net1 = MockDevice(serial="192.168.1.1:5555", state="device")
        net2 = MockDevice(serial="192.168.1.2:5555", state="device")
        runner = MockAdbRunner([net1, net2])
        dm = DeviceManager(runner=runner)
        with self.assertRaises(AmbiguousDeviceError):
            dm.select_target_device(None)

    def test_list_connected_devices_command_failure(self):
        """Raises DeviceError when adb devices command exits with non-zero code."""
        def failing_runner(cmd):
            return (1, "", "daemon not running; failed to start")
        dm = DeviceManager(runner=failing_runner)
        with self.assertRaises(DeviceError) as ctx:
            dm.list_connected_devices()
        self.assertIn("Failed to list devices", str(ctx.exception))

    def test_connect_invalid_port_in_target_string(self):
        """connect() returns (False, msg) when target contains non-integer port."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.connect("192.168.1.50:invalid_port")
        self.assertFalse(ok)
        self.assertIn("Invalid port in target", msg)

    def test_connect_invalid_ip_format(self):
        """connect() gracefully returns (False, msg) when IP is invalid without crashing."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.connect("999.999.999.999", 5555)
        self.assertFalse(ok)
        self.assertIn("Invalid IP address", msg)

    def test_connect_already_connected(self):
        """connect() returns (True, msg) when ADB reports already connected."""
        def connected_runner(cmd):
            return (0, "already connected to 192.168.1.50:5555\n", "")
        dm = DeviceManager(runner=connected_runner)
        ok, msg = dm.connect("192.168.1.50", 5555)
        self.assertTrue(ok)
        self.assertIn("already connected", msg.lower())

    def test_connect_failure_output(self):
        """connect() returns (False, msg) when ADB fails to connect."""
        def refusing_runner(cmd):
            return (1, "", "Connection refused (111)")
        dm = DeviceManager(runner=refusing_runner)
        ok, msg = dm.connect("192.168.1.50", 5555)
        self.assertFalse(ok)
        self.assertIn("Connection refused", msg)

    def test_disconnect_invalid_port_string(self):
        """disconnect() returns (False, msg) when target contains non-integer port."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.disconnect("192.168.1.50:bad_port")
        self.assertFalse(ok)
        self.assertIn("Invalid port in target", msg)

    def test_disconnect_invalid_ip(self):
        """disconnect() returns (False, msg) when target IP is malformed."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.disconnect("not_an_ip", 5555)
        self.assertFalse(ok)

    def test_pair_missing_port_raises_cleanly(self):
        """pair() returns False when target lacks port and port argument is None."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.pair("192.168.1.50", "123456", port=None)
        self.assertFalse(ok)
        self.assertIn("Pairing requires target host:port or port parameter", msg)

    def test_pair_invalid_port_in_target(self):
        """pair() returns False when target contains invalid port string."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.pair("192.168.1.50:bad", "123456")
        self.assertFalse(ok)
        self.assertIn("Invalid port in target", msg)

    def test_pair_non_numeric_code(self):
        """pair() returns False when pairing code contains non-digits."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)
        ok, msg = dm.pair("192.168.1.50", "abc123", port=38450)
        self.assertFalse(ok)
        self.assertIn("numeric digits", msg)

    def test_pair_success_and_failure(self):
        """pair() handles successful and failed pairing handshakes."""
        runner = MockAdbRunner([])
        dm = DeviceManager(runner=runner)

        # Successful pair (6 digits)
        ok, msg = dm.pair("192.168.1.50", "123456", port=38450)
        self.assertTrue(ok)
        self.assertIn("Successfully paired", msg)

        # Failed pair (wrong code length)
        ok2, msg2 = dm.pair("192.168.1.50", "123", port=38450)
        self.assertFalse(ok2)

    def test_get_properties_failure_raises(self):
        """get_properties() raises DeviceInterrogationError on non-zero return code."""
        def failing_runner(cmd):
            return (1, "", "device offline")
        dm = DeviceManager(default_serial="dev1", runner=failing_runner)
        with self.assertRaises(DeviceInterrogationError):
            dm.get_properties("dev1")

    def test_get_properties_unbracketed_colon_format(self):
        """get_properties() parses both [key]: [val] and unbracketed key: val lines."""
        raw_output = (
            "[ro.product.model]: [TEST_MODEL]\n"
            "ro.product.brand: Sony\n"
            "[ro.build.version.sdk]: [33]\n"
        )
        def prop_runner(cmd):
            return (0, raw_output, "")
        dm = DeviceManager(default_serial="dev1", runner=prop_runner)
        props = dm.get_properties("dev1")
        self.assertEqual(props["ro.product.model"], "TEST_MODEL")
        self.assertEqual(props["ro.product.brand"], "Sony")
        self.assertEqual(props["ro.build.version.sdk"], "33")

    def test_get_device_info_non_int_sdk_defaults_to_zero(self):
        """get_device_info() defaults sdk_level to 0 when sdk property is non-numeric."""
        dev = MockDevice(
            serial="test_dev",
            properties={
                "ro.product.model": "Bravia TV",
                "ro.build.version.sdk": "unreleased_version_sdk",
            }
        )
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        info = dm.get_device_info("test_dev")
        self.assertEqual(info.sdk_level, 0)

    def test_get_device_info_package_query_exception_recovery(self):
        """get_device_info() gracefully handles package query errors during interrogation."""
        call_count = [0]
        def custom_runner(cmd):
            if "getprop" in cmd:
                return (0, "[ro.product.model]: [Bravia 4K]\n[ro.product.manufacturer]: [Sony]\n", "")
            if "pm" in cmd and "list" in cmd:
                call_count[0] += 1
                return (1, "", "pm service died")
            return (0, "", "")

        dm = DeviceManager(default_serial="dev1", runner=custom_runner)
        info = dm.get_device_info("dev1")
        self.assertIsNotNone(info)
        self.assertEqual(info.manufacturer, "Sony")
        self.assertGreater(call_count[0], 0)

    def test_get_device_info_unprovisioned_device(self):
        """get_device_info() detects unprovisioned device when setupwizard is required."""
        dev = MockDevice(
            serial="unprovisioned_dev",
            properties={
                "ro.setupwizard.mode": "REQUIRED",
                "settings.global.device_provisioned": "0",
            }
        )
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        info = dm.get_device_info("unprovisioned_dev")
        self.assertFalse(info.is_provisioned)

    def test_check_is_tv_characteristics_leanback(self):
        """_check_is_tv identifies device with 'leanback' in build characteristics."""
        dev = MockDevice(
            serial="leanback_dev",
            properties={"ro.build.characteristics": "nosdcard,leanback"},
            installed_packages={"com.android.settings"}
        )
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        self.assertTrue(dm._check_is_tv("leanback_dev", dev.properties, dev.installed_packages))

    def test_check_is_tv_model_names(self):
        """_check_is_tv identifies devices with 'beyondtv', 'shield', or 'mibox' in model/device/name."""
        dm = DeviceManager(runner=MockAdbRunner([]))
        for key, val in [("ro.product.model", "MiBox4"), ("ro.product.device", "beyondtv"), ("ro.product.name", "shield")]:
            props = {key: val}
            self.assertTrue(dm._check_is_tv("dev", props, set()))

    def test_check_is_tv_tv_indicator_packages(self):
        """_check_is_tv identifies devices with TV-specific home launcher packages."""
        dm = DeviceManager(runner=MockAdbRunner([]))
        props = {"ro.product.model": "GenericDevice"}
        self.assertTrue(dm._check_is_tv("dev", props, {"com.mitv.tvhome"}))
        self.assertTrue(dm._check_is_tv("dev", props, {"org.droidtv.homeintentresolver"}))

    def test_check_is_tv_pm_features_fallback(self):
        """_check_is_tv identifies television via pm list features fallback."""
        def feature_runner(cmd):
            if "pm" in cmd and "features" in cmd:
                return (0, "feature:android.hardware.type.television\nfeature:android.software.leanback\n", "")
            return (0, "", "")
        dm = DeviceManager(runner=feature_runner)
        self.assertTrue(dm._check_is_tv("dev", {}, set()))

    def test_check_is_tv_non_tv_device_returns_false(self):
        """_check_is_tv returns False for standard phone/tablet without TV characteristics."""
        def non_tv_runner(cmd):
            return (0, "feature:android.hardware.telephony\nfeature:android.hardware.touchscreen\n", "")
        dm = DeviceManager(runner=non_tv_runner)
        props = {
            "ro.build.characteristics": "default",
            "ro.product.model": "Pixel 7",
            "ro.product.device": "panther",
            "ro.product.name": "panther",
        }
        self.assertFalse(dm._check_is_tv("dev", props, {"com.google.android.apps.photos"}))

    def test_get_installed_packages_all_flags(self):
        """get_installed_packages maps all filter_type strings to correct ADB flags."""
        recorded_cmds: List[List[str]] = []
        def cmd_recorder(cmd):
            recorded_cmds.append(list(cmd))
            return (0, "package:com.app.one\npackage:com.app.two\n", "")

        dm = DeviceManager(default_serial="dev1", runner=cmd_recorder)
        # Test flag map: all, user, third-party, -3, system, -s, enabled, -e, disabled, -d
        tests = [
            ("all", None),
            ("user", "-3"),
            ("third-party", "-3"),
            ("-3", "-3"),
            ("system", "-s"),
            ("-s", "-s"),
            ("enabled", "-e"),
            ("-e", "-e"),
            ("disabled", "-d"),
            ("-d", "-d"),
        ]
        for mode, expected_flag in tests:
            pkgs = dm.get_installed_packages("dev1", filter_type=mode)
            self.assertEqual(len(pkgs), 2)
            last_cmd = recorded_cmds[-1]
            if expected_flag:
                self.assertIn(expected_flag, last_cmd)

    def test_get_installed_packages_command_failure_raises(self):
        """get_installed_packages raises DeviceError when pm command fails."""
        def failing_runner(cmd):
            return (1, "", "Failure [Package manager died]")
        dm = DeviceManager(default_serial="dev1", runner=failing_runner)
        with self.assertRaises(DeviceError):
            dm.get_installed_packages("dev1", "all")

    def test_resolve_leanback_activity_success(self):
        """resolve_leanback_activity parses resolving Leanback launcher component."""
        raw_output = (
            "priority=0 preferredOrder=0 match=0x108000 specific=false\n"
            "org.opentv.launcher/.MainActivity\n"
        )
        def resolver_runner(cmd):
            return (0, raw_output, "")
        dm = DeviceManager(default_serial="dev1", runner=resolver_runner)
        comp = dm.resolve_leanback_activity("dev1")
        self.assertIsNotNone(comp)
        self.assertEqual(comp.package_name, "org.opentv.launcher")
        self.assertEqual(comp.activity_name, ".MainActivity")

    def test_resolve_leanback_activity_not_found(self):
        """resolve_leanback_activity returns None when no activity is found."""
        def not_found_runner(cmd):
            return (0, "No activity found\n", "")
        dm = DeviceManager(default_serial="dev1", runner=not_found_runner)
        comp = dm.resolve_leanback_activity("dev1")
        self.assertIsNone(comp)

    def test_get_launchable_apps_fallback_to_launcher(self):
        """get_launchable_apps falls back to regular LAUNCHER when LEANBACK query returns empty."""
        def fallback_runner(cmd):
            if "android.intent.category.LEANBACK_LAUNCHER" in cmd:
                return (0, "", "")
            if "android.intent.category.LAUNCHER" in cmd:
                return (0, "com.generic.app/.MainActivity\n", "")
            return (0, "", "")

        dm = DeviceManager(default_serial="dev1", runner=fallback_runner)
        apps = dm.get_launchable_apps("dev1")
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0].package_name, "com.generic.app")

    def test_get_all_packages_info(self):
        """get_all_packages_info compiles comprehensive package metadata with derived labels."""
        dev = MockDevice(
            serial="meta_dev",
            installed_packages={"com.netflix.ninja", "com.android.settings"}
        )
        dev.disabled_packages.add("com.android.settings")
        runner = MockAdbRunner([dev])
        dm = DeviceManager(runner=runner)
        info_list = dm.get_all_packages_info("meta_dev")
        self.assertEqual(len(info_list), 2)
        pkg_map = {p.package_name: p for p in info_list}

        self.assertTrue(pkg_map["com.netflix.ninja"].is_enabled)
        self.assertFalse(pkg_map["com.android.settings"].is_enabled)
        self.assertTrue(pkg_map["com.netflix.ninja"].app_label.strip() != "")

    def test_run_cmd_subprocess_exceptions(self):
        """_run_cmd catches FileNotFoundError, TimeoutExpired, and generic Exception when runner is None."""
        # Test with non-existent adb binary
        adb = AdbClient(adb_path="non_existent_binary_12345")
        dm = DeviceManager(adb_wrapper=adb, runner=None)
        code, out, err = dm._run_cmd(["non_existent_binary_12345", "devices"])
        self.assertEqual(code, 127)
        self.assertIn("not found", err)


# ==============================================================================
# Suite 2: LauncherDeployer Adversarial Hardening
# ==============================================================================

class TestLauncherDeployerAdversarial(unittest.TestCase):
    """Probes uncovered branches, recovery loops, scoped storage, and deployment pipelines in core/deployer.py."""

    def test_resolve_target_missing_raises_deployer_error(self):
        """Raises DeployerError when no target device serial is provided or defaulted."""
        deployer = LauncherDeployer(default_serial=None)
        deployer.adb.default_device = None
        with self.assertRaises(DeployerError):
            deployer.install_apk(None, "app.apk")

    def test_deploy_summary_and_result_failures(self):
        """DeploySummary aggregates failures and preserves first error message."""
        summary = DeploySummary(serial="dev1")
        self.assertTrue(summary.overall_success)

        res1 = DeployResult(step="step1", success=False, message="first failure", return_code=1)
        res2 = DeployResult(step="step2", success=False, message="second failure", return_code=2)
        summary.add_result(res1)
        summary.add_result(res2)

        self.assertFalse(summary.overall_success)
        self.assertIn("first failure", summary.error_message)

        d = summary.to_dict()
        self.assertFalse(d["overall_success"])
        self.assertEqual(len(d["steps"]), 2)

    def test_install_apk_missing_local_file_no_runner(self):
        """install_apk returns failure DeployResult if local file is missing when runner is None."""
        deployer = LauncherDeployer(default_serial="target_dev", runner=None)
        res = deployer.install_apk("target_dev", "/non_existent/path/OpenTV.apk")
        self.assertFalse(res.success)
        self.assertIn("Local APK file not found", res.message)

    def test_install_apk_success_and_failure(self):
        """install_apk verifies success and handles failure outputs."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        # Mocked install succeeds
        res_ok = deployer.install_apk("dev1", "OpenTV.apk")
        self.assertTrue(res_ok.success)
        self.assertIn("APK installed successfully", res_ok.message)

        # Failing install
        def fail_install_runner(cmd):
            return (1, "INSTALL_FAILED_INSUFFICIENT_STORAGE\n", "")
        deployer_fail = LauncherDeployer(default_serial="dev1", runner=fail_install_runner)
        res_fail = deployer_fail.install_apk("dev1", "OpenTV.apk")
        self.assertFalse(res_fail.success)
        self.assertIn("Installation failed", res_fail.message)

    def test_install_apk_grant_permissions_fallback_retry(self):
        """When install with -g fails due to 'Unknown option: -g' on older Android, retries without -g."""
        attempts = []
        def retry_runner(cmd):
            attempts.append(list(cmd))
            if "-g" in cmd:
                return (1, "", "Error: Unknown option: -g")
            return (0, "Success\n", "")

        deployer = LauncherDeployer(default_serial="dev1", runner=retry_runner)
        res = deployer.install_apk("dev1", "OpenTV.apk", grant_permissions=True)

        self.assertTrue(res.success)
        self.assertEqual(len(attempts), 2)
        self.assertIn("-g", attempts[0])
        self.assertNotIn("-g", attempts[1])

    def test_push_config_from_launcher_config_object(self):
        """push_config accepts LauncherConfig instance and pushes to device."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)
        cfg = LauncherConfig(apps=["com.netflix.ninja", "com.plexapp.android"])

        res = deployer.push_config("dev1", cfg)
        self.assertTrue(res.success)
        self.assertIn(LauncherDeployer.SECONDARY_CONFIG_PATH, dev.files)

    def test_push_config_from_dict(self):
        """push_config accepts Python dictionary and serializes to JSON."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)
        d = {"version": 1, "apps": ["com.youtube.tv"]}

        res = deployer.push_config("dev1", d)
        self.assertTrue(res.success)
        self.assertIn("pushed successfully", res.message)

    def test_push_config_invalid_json_string(self):
        """push_config rejects malformed JSON string without pushing."""
        runner = MockAdbRunner([])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)
        res = deployer.push_config("dev1", "{invalid_json_content}")
        self.assertFalse(res.success)
        self.assertIn("Invalid JSON configuration string", res.message)

    def test_push_config_unsupported_type(self):
        """push_config rejects non-config data types (e.g. list, integer)."""
        runner = MockAdbRunner([])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)
        res = deployer.push_config("dev1", 12345)  # type: ignore
        self.assertFalse(res.success)
        self.assertIn("Unsupported config type: int", res.message)

    def test_push_config_primary_push_failure(self):
        """push_config returns failure DeployResult if ADB push fails."""
        def fail_push_runner(cmd):
            if "push" in cmd:
                return (1, "", "failed to copy: Read-only file system")
            return (0, "", "")

        deployer = LauncherDeployer(default_serial="dev1", runner=fail_push_runner)
        res = deployer.push_config("dev1", "{}")
        self.assertFalse(res.success)
        self.assertIn("Failed to push config", res.message)

    def test_push_config_dual_storage_scoped_copy(self):
        """push_config pushes to secondary path and copies to scoped app storage."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        res = deployer.push_config("dev1", "{}", copy_to_app_storage=True)
        self.assertTrue(res.success)
        self.assertIn(LauncherDeployer.SECONDARY_CONFIG_PATH, dev.files)
        self.assertIn(LauncherDeployer.PRIMARY_CONFIG_PATH, dev.files)
        self.assertEqual(len(res.details["pushed_paths"]), 2)

    def test_push_config_primary_destination_does_not_duplicate(self):
        """When destination is PRIMARY_CONFIG_PATH, copy_to_app_storage does not duplicate push."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        res = deployer.push_config(
            "dev1", "{}",
            remote_path=LauncherDeployer.PRIMARY_CONFIG_PATH,
            copy_to_app_storage=True
        )
        self.assertTrue(res.success)
        self.assertEqual(res.details["pushed_paths"], [LauncherDeployer.PRIMARY_CONFIG_PATH])

    def test_set_home_activity_success_and_failure(self):
        """set_home_activity handles success and error outputs from cmd package set-home-activity."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        # Success
        res_ok = deployer.set_home_activity("dev1", "org.opentv.launcher/.MainActivity")
        self.assertTrue(res_ok.success)
        self.assertEqual(dev.home_activity, "org.opentv.launcher/.MainActivity")

        # Failure
        def fail_home_runner(cmd):
            return (1, "", "Error: Component not found")
        deployer_fail = LauncherDeployer(default_serial="dev1", runner=fail_home_runner)
        res_fail = deployer_fail.set_home_activity("dev1")
        self.assertFalse(res_fail.success)

    def test_reload_config_broadcast_success_and_failure(self):
        """reload_config handles broadcast completion confirmation."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        res_ok = deployer.reload_config("dev1")
        self.assertTrue(res_ok.success)
        self.assertIn("RELOAD_CONFIG", dev.broadcasts_received[-1])

        def fail_broadcast_runner(cmd):
            return (1, "", "Broadcast failed: receiver killed")
        deployer_fail = LauncherDeployer(default_serial="dev1", runner=fail_broadcast_runner)
        res_fail = deployer_fail.reload_config("dev1")
        self.assertFalse(res_fail.success)

    def test_verify_home_matched_and_mismatched(self):
        """verify_home returns (True, comp) when matching, (False, comp) when resolving to other launcher."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        # Default resolves to launcherx
        matched, comp = deployer.verify_home("dev1", expected_component="org.opentv.launcher/.MainActivity")
        self.assertFalse(matched)
        self.assertIn("launcherx", comp)

        # Update home activity to OpenTV
        dev.home_activity = "org.opentv.launcher/.MainActivity"
        matched, comp = deployer.verify_home("dev1", expected_component="org.opentv.launcher/.MainActivity")
        self.assertTrue(matched)
        self.assertEqual(comp, "org.opentv.launcher/.MainActivity")

    def test_verify_home_command_failure(self):
        """verify_home returns (False, 'Unknown') when command fails or returns empty."""
        def fail_runner(cmd):
            return (1, "", "error")
        deployer = LauncherDeployer(default_serial="dev1", runner=fail_runner)
        matched, comp = deployer.verify_home("dev1")
        self.assertFalse(matched)
        self.assertEqual(comp, "Unknown")

    def test_deploy_full_pipeline_success(self):
        """deploy_full completes all 5 deployment steps sequentially."""
        dev = MockDevice(serial="dev1")
        # Pre-set mock to resolve OpenTV when set_home is called
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        summary = deployer.deploy_full(
            "dev1",
            config="{}",
            apk_path="OpenTV.apk",
            set_home=True,
            reload=True,
        )
        self.assertEqual(len(summary.steps), 5)
        # Check all step names
        step_names = [s.step for s in summary.steps]
        self.assertEqual(step_names, ["install_apk", "push_config", "set_home_activity", "verify_home", "reload_config"])

    def test_deploy_full_short_circuit_on_install_failure(self):
        """deploy_full halts immediately when APK installation fails."""
        def fail_install_runner(cmd):
            if "install" in cmd:
                return (1, "", "INSTALL_FAILED_INVALID_APK")
            return (0, "", "")

        deployer = LauncherDeployer(default_serial="dev1", runner=fail_install_runner)
        summary = deployer.deploy_full("dev1", config="{}", apk_path="bad.apk")
        self.assertFalse(summary.overall_success)
        self.assertEqual(len(summary.steps), 1)
        self.assertEqual(summary.steps[0].step, "install_apk")

    def test_deploy_full_short_circuit_on_push_failure(self):
        """deploy_full halts immediately when push config fails."""
        def fail_push_runner(cmd):
            if "install" in cmd:
                return (0, "Success", "")
            if "push" in cmd:
                return (1, "", "disk full")
            return (0, "", "")

        deployer = LauncherDeployer(default_serial="dev1", runner=fail_push_runner)
        summary = deployer.deploy_full("dev1", config="{}", apk_path="OpenTV.apk")
        self.assertFalse(summary.overall_success)
        self.assertEqual(len(summary.steps), 2)
        self.assertEqual(summary.steps[1].step, "push_config")

    def test_deploy_full_skip_set_home_and_reload(self):
        """deploy_full respects set_home=False and reload=False flags."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        deployer = LauncherDeployer(default_serial="dev1", runner=runner)

        summary = deployer.deploy_full(
            "dev1", config="{}", apk_path=None, set_home=False, reload=False
        )
        step_names = [s.step for s in summary.steps]
        self.assertNotIn("install_apk", step_names)
        self.assertIn("push_config", step_names)
        self.assertNotIn("set_home_activity", step_names)
        self.assertIn("verify_home", step_names)
        self.assertNotIn("reload_config", step_names)


# ==============================================================================
# Suite 3: Interactive TUI & FallbackLineEngine Adversarial Hardening
# ==============================================================================

class TestTuiAppAdversarial(unittest.TestCase):
    """Probes TUI modes, device scanning error suppression, safe debloat execution, and grid preview."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_app_init_modes(self):
        """OpenTVApp initializes correctly under auto, interactive, line, and force_fallback."""
        app_line = OpenTVApp(mode="line", cmd_runner=lambda cmd: (0, "", ""))
        self.assertFalse(app_line.interactive)

        app_fallback = OpenTVApp(force_fallback=True, cmd_runner=lambda cmd: (0, "", ""))
        self.assertFalse(app_fallback.interactive)

        app_interactive = OpenTVApp(mode="interactive", cmd_runner=lambda cmd: (0, "", ""))
        self.assertTrue(app_interactive.interactive)

    def test_app_scan_devices_error_suppression(self):
        """scan_devices suppresses errors and returns [] when ADB device listing fails."""
        def broken_runner(cmd):
            return (1, "", "adb server killed")
        app = OpenTVApp(cmd_runner=broken_runner, force_fallback=True)
        devices = app.scan_devices()
        self.assertEqual(devices, [])

    def test_app_connect_target_success_and_failure(self):
        """connect_target updates all engine default devices on success, records notice on failure."""
        dev = MockDevice(serial="192.168.1.100:5555")
        runner = MockAdbRunner([dev])
        app = OpenTVApp(cmd_runner=runner.execute, force_fallback=True)

        # Successful connect
        ok = app.connect_target("192.168.1.100", 5555)
        self.assertTrue(ok)
        self.assertEqual(app.target_device, "192.168.1.100:5555")
        self.assertEqual(app.adb.default_device, "192.168.1.100:5555")
        self.assertEqual(app.device_mgr.default_serial, "192.168.1.100:5555")
        self.assertEqual(app.deployer.default_serial, "192.168.1.100:5555")
        self.assertIn("Connected to", app.status_message)

        # Failed connect (invalid IP)
        ok_fail = app.connect_target("999.1.1.1", 5555)
        self.assertFalse(ok_fail)
        self.assertIn("Connection failed", app.status_message)

    def test_app_pair_target_success_and_failure(self):
        """pair_target updates status message for success and failure."""
        runner = MockAdbRunner([])
        app = OpenTVApp(cmd_runner=runner.execute, force_fallback=True)

        # Success
        ok = app.pair_target("192.168.1.50", 38450, "123456")
        self.assertTrue(ok)
        self.assertIn("Successfully paired", app.status_message)

        # Failure
        ok_fail = app.pair_target("192.168.1.50", 38450, "000")
        self.assertFalse(ok_fail)
        self.assertIn("Pairing failed", app.status_message)

    def test_app_interrogate_device_graceful_degradation(self):
        """interrogate_device populates fallback brand profile when interrogation fails."""
        def failing_interrogate(cmd):
            return (1, "", "error")
        app = OpenTVApp(target="dev1", cmd_runner=failing_interrogate, force_fallback=True)
        # Should degrade gracefully to Generic brand profile
        self.assertIsNotNone(app.brand_profile)
        self.assertEqual(app.brand_profile.brand_id, "generic")

    def test_app_get_categorized_packages(self):
        """get_categorized_packages groups installed packages into SAFE, KEEP, NEVER, REVIEW."""
        dev = MockDevice(
            serial="dev1",
            installed_packages={
                "android",
                "com.google.android.inputmethod.latin",
                "tv.samba.ssm",
                "com.netflix.ninja",
            }
        )
        runner = MockAdbRunner([dev])
        app = OpenTVApp(target="dev1", cmd_runner=runner.execute, force_fallback=True)
        cat_map = app.get_categorized_packages()

        self.assertIn("android", cat_map[SafetyCategory.NEVER])
        self.assertIn("tv.samba.ssm", cat_map[SafetyCategory.SAFE])
        self.assertIn("com.netflix.ninja", cat_map[SafetyCategory.REVIEW])

    def test_app_execute_debloat_no_target_device(self):
        """execute_debloat returns failure violation when target device is not connected."""
        app = OpenTVApp(target=None, force_fallback=True)
        succ, viol = app.execute_debloat(["tv.samba.ssm"])
        self.assertEqual(succ, [])
        self.assertEqual(viol, [("", "No target device connected")])

    def test_app_execute_debloat_guardrail_blocking(self):
        """execute_debloat blocks critical packages and aborts disabling when none permitted."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        app = OpenTVApp(target="dev1", cmd_runner=runner.execute, force_fallback=True)

        succ, viol = app.execute_debloat(["android", "com.android.settings"])
        self.assertEqual(succ, [])
        self.assertEqual(len(viol), 2)

    def test_app_execute_debloat_success_with_registry_and_rollback(self):
        """execute_debloat disables safe packages, writes registry, generates rollback scripts, logs audit."""
        dev = MockDevice(
            serial="dev1",
            installed_packages={"tv.samba.ssm", "com.sony.dtv.demomode", "android"}
        )
        runner = MockAdbRunner([dev])
        app = OpenTVApp(
            target="dev1",
            cmd_runner=runner.execute,
            output_dir=str(self.output_dir),
            force_fallback=True
        )

        succ, viol = app.execute_debloat(["tv.samba.ssm", "com.sony.dtv.demomode"])
        self.assertEqual(len(succ), 2)
        self.assertIn("tv.samba.ssm", app.disabled_packages)

        # Check on-device registry was updated
        self.assertIn("/data/local/tmp/opentv-disabled.txt", dev.files)

        # Check standalone rollback scripts were written
        self.assertTrue((self.output_dir / "rollback.sh").exists())
        self.assertTrue((self.output_dir / "rollback.bat").exists())
        self.assertTrue((self.output_dir / "rollback.ps1").exists())

        # Check audit log was written
        self.assertTrue((self.output_dir / "audit_log.json").exists())

    def test_app_deploy_launcher_no_target(self):
        """deploy_launcher returns pre-check failure when target device is not connected."""
        app = OpenTVApp(target=None, force_fallback=True)
        results = app.deploy_launcher()
        self.assertEqual(results, [("Pre-check", False, "No target device connected")])

    def test_app_deploy_launcher_5_step_workflow(self):
        """deploy_launcher executes all 5 workflow steps on connected device."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])
        app = OpenTVApp(target="dev1", cmd_runner=runner.execute, force_fallback=True)

        results = app.deploy_launcher("OpenTV.apk")
        self.assertEqual(len(results), 5)
        self.assertEqual(results[0][0], "Push Configuration")
        self.assertEqual(results[1][0], "Install Launcher APK")
        self.assertEqual(results[2][0], "Set Default Home Activity")
        self.assertEqual(results[3][0], "Verify Home Activity Resolution")
        self.assertEqual(results[4][0], "Broadcast Config Reload")

    def test_app_generate_grid_preview_empty(self):
        """generate_grid_preview returns friendly notice when no apps are configured."""
        app = OpenTVApp(force_fallback=True)
        out = app.generate_grid_preview([])
        self.assertIn("No visible apps configured", out)

    def test_app_generate_grid_preview_multiline_6_col(self):
        """generate_grid_preview renders clean ASCII grid borders, derived labels, and empty cells."""
        app = OpenTVApp(force_fallback=True)
        apps = [
            "com.netflix.ninja",
            "com.google.android.youtube.tv",
            "com.plexapp.android",
            "com.amazon.amazonvideo.livingroom",
        ]
        out = app.generate_grid_preview(apps, columns=6)
        self.assertIn("+------------------+", out)
        self.assertIn("1. ninja", out)
        self.assertIn("2. youtube.tv", out)
        self.assertIn("[Empty]", out)

    def test_app_fallback_screens_layout_manager(self):
        """_fallback_layout_manager allows user to confirm and update home apps."""
        # Empty input confirms preselected apps
        stdin = io.StringIO("\n")
        stdout = io.StringIO()
        dev = MockDevice(serial="dev1", installed_packages={"com.netflix.ninja", "com.plexapp.android", "com.youtube.tv"})
        runner = MockAdbRunner([dev])

        app = OpenTVApp(
            target="dev1",
            cmd_runner=runner.execute,
            stdin=stdin,
            stdout=stdout,
            force_fallback=True,
        )
        app._fallback_layout_manager()
        self.assertEqual(len(app.current_config.apps), 2)

    def test_app_fallback_screens_hdmi_manager(self):
        """_fallback_hdmi_manager modifies HDMI port title and toggles visibility."""
        # Choices: 1 (edit title) -> 1 (port HW5) -> new title "Gaming Rig"
        stdin = io.StringIO("1\n1\nGaming Rig\n")
        stdout = io.StringIO()
        app = OpenTVApp(stdin=stdin, stdout=stdout, force_fallback=True)
        app._fallback_hdmi_manager()
        self.assertEqual(app.current_config.hdmi[0].title, "Gaming Rig")

    def test_app_fallback_screens_debloat_assistant(self):
        """_fallback_debloat_assistant allows one-key safe debloat in line mode."""
        # Choice 1 (Disable All SAFE)
        stdin = io.StringIO("1\n")
        stdout = io.StringIO()
        dev = MockDevice(serial="dev1", installed_packages={"tv.samba.ssm", "android"})
        runner = MockAdbRunner([dev])

        app = OpenTVApp(
            target="dev1",
            cmd_runner=runner.execute,
            output_dir=str(self.output_dir),
            stdin=stdin,
            stdout=stdout,
            force_fallback=True,
        )
        app._fallback_debloat_assistant()
        self.assertIn("tv.samba.ssm", app.disabled_packages)

    def test_app_fallback_screens_deploy_launcher(self):
        """_fallback_deploy_launcher prompts for APK and reports deploy steps."""
        stdin = io.StringIO("MyOpenTV.apk\n")
        stdout = io.StringIO()
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])

        app = OpenTVApp(
            target="dev1",
            cmd_runner=runner.execute,
            stdin=stdin,
            stdout=stdout,
            force_fallback=True,
        )
        app._fallback_deploy_launcher()
        out_text = stdout.getvalue()
        self.assertIn("Push Configuration", out_text)
        self.assertIn("Install Launcher APK", out_text)

    def test_app_fallback_main_menu_loop_exit(self):
        """_run_fallback_loop executes and quits cleanly when choice 6 (Exit) is selected."""
        stdin = io.StringIO("6\n")
        stdout = io.StringIO()
        app = OpenTVApp(stdin=stdin, stdout=stdout, force_fallback=True)
        ret = app.run()
        self.assertEqual(ret, 0)
        self.assertIn("Exiting OpenTV Companion", stdout.getvalue())


# ==============================================================================
# Suite 4: CLI Subcommands, Terminal & FallbackLineEngine Adversarial
# ==============================================================================

class TestCliAndTerminalAdversarial(unittest.TestCase):
    """Probes CLI argument parsing, subcommands, exit codes, and non-TTY terminal escapes."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_parse_target_address_valid_and_invalid(self):
        """cli.parse_target_address validates IPv4, handles ports, and rejects invalid strings."""
        adb = AdbClient()
        h, p = cli.parse_target_address("192.168.1.50:5555", adb=adb)
        self.assertEqual((h, p), ("192.168.1.50", 5555))

        h2, p2 = cli.parse_target_address("10.0.0.1", default_port=5555, adb=adb)
        self.assertEqual((h2, p2), ("10.0.0.1", 5555))

        with self.assertRaises(ValueError):
            cli.parse_target_address("192.168.1.50:invalid_port", adb=adb)

        with self.assertRaises(ValueError):
            cli.parse_target_address("999.999.999.999:5555", adb=adb)

    def test_cli_resolve_target_device_priority(self):
        """cli.resolve_target_device honors flag > OPENTV_TARGET env var > auto-detection."""
        adb = AdbClient()
        runner = MockAdbRunner([MockDevice(serial="AUTO_DETECTED")])

        # 1. Explicit target wins
        t1 = cli.resolve_target_device("EXPLICIT_DEV", adb, runner.execute)
        self.assertEqual(t1, "EXPLICIT_DEV")

        # 2. Env var wins over auto-detected
        os.environ["OPENTV_TARGET"] = "ENV_DEV"
        try:
            t2 = cli.resolve_target_device(None, adb, runner.execute)
            self.assertEqual(t2, "ENV_DEV")
        finally:
            del os.environ["OPENTV_TARGET"]

        # 3. Auto-detected fallback
        t3 = cli.resolve_target_device(None, adb, runner.execute)
        self.assertEqual(t3, "AUTO_DETECTED")

    def test_cli_connect_subcommand(self):
        """cli connect handler verifies exit codes for valid, invalid, and failed targets."""
        dev = MockDevice(serial="192.168.1.50:5555")
        runner = MockAdbRunner([dev])

        # Success
        code = cli.main(["connect", "192.168.1.50"], runner=runner.execute)
        self.assertEqual(code, cli.EXIT_SUCCESS)

        # Invalid IP (USAGE error)
        code_usage = cli.main(["connect", "invalid_ip_format"], runner=runner.execute)
        self.assertEqual(code_usage, cli.EXIT_USAGE)

    def test_cli_pair_subcommand(self):
        """cli pair handler checks usage for missing port, non-numeric code, and pairing."""
        runner = MockAdbRunner([])

        # Missing port in target
        code_no_port = cli.main(["pair", "192.168.1.50", "123456"], runner=runner.execute)
        self.assertEqual(code_no_port, cli.EXIT_USAGE)

        # Non-numeric code
        code_bad_code = cli.main(["pair", "192.168.1.50:38450", "abc"], runner=runner.execute)
        self.assertEqual(code_bad_code, cli.EXIT_USAGE)

        # Successful pair
        code_ok = cli.main(["pair", "192.168.1.50:38450", "123456"], runner=runner.execute)
        self.assertEqual(code_ok, cli.EXIT_SUCCESS)

    def test_cli_list_apps_subcommand(self):
        """cli list-apps outputs packages, JSON formatting, and handles missing device."""
        dev = MockDevice(serial="dev1", installed_packages={"com.netflix.ninja", "com.youtube.tv"})
        runner = MockAdbRunner([dev])

        # Plaintext list
        code = cli.main(["-t", "dev1", "list-apps"], runner=runner.execute)
        self.assertEqual(code, cli.EXIT_SUCCESS)

        # JSON list with categories
        code_json = cli.main(["-t", "dev1", "list-apps", "--json", "--categories"], runner=runner.execute)
        self.assertEqual(code_json, cli.EXIT_SUCCESS)

        # Missing device error (ensure empty runner has no default devices)
        empty_runner = MockAdbRunner()
        empty_runner.devices.clear()
        code_no_dev = cli.main(["list-apps"], runner=empty_runner.execute)
        self.assertEqual(code_no_dev, cli.EXIT_DEVICE_NOT_FOUND)

    def test_cli_configure_subcommand(self):
        """cli configure builds config, writes output, rejects negative screensaver idle."""
        out_cfg = self.output_dir / "test_config.json"

        # Valid configuration build
        code = cli.main([
            "configure",
            "-a", "com.app1,com.app2",
            "--hdmi", "HW1:PlayStation:true",
            "--theme", "OLED_Black",
            "--screensaver-idle", "300",
            "--pixel-shift",
            "-o", str(out_cfg),
        ], runner=lambda cmd: (0, "", ""))
        self.assertEqual(code, cli.EXIT_SUCCESS)
        self.assertTrue(out_cfg.exists())

        # Negative screensaver idle rejection
        code_bad = cli.main([
            "configure",
            "--screensaver-idle", "-10",
        ], runner=lambda cmd: (0, "", ""))
        self.assertEqual(code_bad, cli.EXIT_USAGE)

    def test_cli_deploy_subcommand(self):
        """cli deploy handles --skip-install and --set-home."""
        dev = MockDevice(serial="dev1")
        runner = MockAdbRunner([dev])

        code = cli.main([
            "-t", "dev1",
            "deploy",
            "--skip-install",
            "--set-home",
            "--reload",
        ], runner=runner.execute)
        self.assertEqual(code, cli.EXIT_SUCCESS)

    def test_cli_debloat_dry_run_and_guardrails(self):
        """cli debloat honors --dry-run and enforces guardrails against critical system packages."""
        dev = MockDevice(serial="dev1", installed_packages={"android", "tv.samba.ssm"})
        runner = MockAdbRunner([dev])

        # Dry run with safe bloat
        code_dry = cli.main([
            "-t", "dev1",
            "debloat",
            "--safe-only",
            "--dry-run",
        ], runner=runner.execute)
        self.assertEqual(code_dry, cli.EXIT_SUCCESS)

        # Debloat on critical package blocked by guardrails
        code_guard = cli.main([
            "-t", "dev1",
            "debloat",
            "-p", "android",
            "-y",
        ], runner=runner.execute)
        self.assertEqual(code_guard, cli.EXIT_GUARDRAIL_VIOLATION)

    def test_cli_rollback_generate_and_execute(self):
        """cli rollback writes standalone scripts and re-enables packages on device with -e."""
        dev = MockDevice(serial="dev1", installed_packages={"tv.samba.ssm"})
        dev.disabled_packages.add("tv.samba.ssm")
        runner = MockAdbRunner([dev])

        # Generate scripts
        code_gen = cli.main([
            "-t", "dev1",
            "rollback",
            "--output-dir", str(self.output_dir),
            "-p", "tv.samba.ssm",
        ], runner=runner.execute)
        self.assertEqual(code_gen, cli.EXIT_SUCCESS)
        self.assertTrue((self.output_dir / "rollback.sh").exists())

        # Execute rollback
        code_exec = cli.main([
            "-t", "dev1",
            "rollback",
            "-e",
            "-p", "tv.samba.ssm",
            "--output-dir", str(self.output_dir),
        ], runner=runner.execute)
        self.assertEqual(code_exec, cli.EXIT_SUCCESS)
        self.assertNotIn("tv.samba.ssm", dev.disabled_packages)

    def test_terminal_controller_non_tty_escapes(self):
        """TerminalController returns clean empty strings and fallback brackets when not in TTY."""
        stdin = io.StringIO()
        stdout = io.StringIO()
        term = TerminalController(stdin=stdin, stdout=stdout)
        self.assertFalse(term.is_tty)

        self.assertEqual(term.clear_screen(), "")
        self.assertEqual(term.hide_cursor(), "")
        self.assertEqual(term.show_cursor(), "")
        self.assertEqual(term.bold("Heading"), "Heading")
        self.assertEqual(term.color("Text", 31), "Text")
        self.assertEqual(term.invert("Selected"), "[Selected]")

    def test_fallback_line_engine_prompt_choice_retries(self):
        """FallbackLineEngine retries on non-numeric or out-of-range input and returns default on empty."""
        # First "bad", then "99" (out of range), then "" (default to index 1)
        inputs = io.StringIO("bad\n99\n\n")
        outputs = io.StringIO()
        engine = FallbackLineEngine(
            input_fn=lambda prompt="": inputs.readline().strip(),
            output_fn=lambda msg="": outputs.write(str(msg) + "\n")
        )
        choice = engine.prompt_choice("Menu", ["Option A", "Option B"], default_index=1)
        self.assertEqual(choice, 1)
        self.assertIn("Invalid choice", outputs.getvalue())

    def test_fallback_line_engine_prompt_multiselect(self):
        """FallbackLineEngine multiselect toggles indices and returns sorted selection."""
        # Preselected [0], toggle 0 (unselect) and 1 (select), empty to confirm
        inputs = io.StringIO("1, 2\n")
        outputs = io.StringIO()
        engine = FallbackLineEngine(
            input_fn=lambda prompt="": inputs.readline().strip(),
            output_fn=lambda msg="": outputs.write(str(msg) + "\n")
        )
        selected = engine.prompt_multiselect("Select", ["Item 1", "Item 2"], preselected=[0])
        # Item 1 was unselected (1 was passed), Item 2 was selected (2 was passed)
        self.assertEqual(selected, [1])

    def test_fallback_line_engine_prompt_text(self):
        """FallbackLineEngine prompt_text returns default when response is empty."""
        engine = FallbackLineEngine(
            input_fn=lambda prompt="": "",
            output_fn=lambda msg="": None
        )
        val = engine.prompt_text("Enter name", default="OpenTV")
        self.assertEqual(val, "OpenTV")


if __name__ == "__main__":
    unittest.main()
