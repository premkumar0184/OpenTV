#!/usr/bin/env python3
"""
OpenTV Tier 5: Adversarial Coverage Hardening Test Suite (Debloat & Profiles).
PROJECT.md Feature F4.4:
White-box adversarial audit covering:
1. `companion/opentv/debloat/database.py` (PackageEntry serialization, DB catalog queries, custom overrides, stats)
2. `companion/opentv/debloat/guardrails.py` (Shell injection, PERSISTENT shield, launcherx bootloop, provisioning, IME accounting, remotes, OLED screensavers)
3. `companion/opentv/debloat/rollback.py` (Multi-platform standalone recovery generators, atomic writes, listener grant)
4. `companion/opentv/debloat/audit.py` (AuditEvent serialization, dual format JSON/TXT logger, corrupted log recovery, concurrency)
5. `companion/opentv/profiles/detector.py` (IntentDefinition am args, quick settings aliases, hardware HDMI URIs, brand heuristics, OLED detection)
"""
from __future__ import annotations

import copy
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path

# Add repo root and companion directory to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANION_DIR = REPO_ROOT / "companion"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))

from opentv.debloat.database import (
    CURATED_PACKAGES,
    PackageEntry,
    PackageSafetyDB,
    SafetyCategory,
)
from opentv.debloat.guardrails import (
    CORE_REMOTE_SERVICES,
    CORE_SYSTEM_PACKAGES,
    ILLEGAL_SHELL_CHARS,
    KNOWN_IMES,
    OLED_SCREENSAVERS,
    SETUP_WIZARDS,
    GuardrailsEngine,
    GuardrailViolation,
)
from opentv.debloat.rollback import (
    DEVICE_REGISTRY_PATH,
    LAUNCHERX_LISTENER_SVC,
    LAUNCHERX_PKG,
    RollbackEngine,
)
from opentv.debloat.audit import (
    AuditEvent,
    AuditLogger,
)
from opentv.profiles.detector import (
    GENERIC_PROFILE,
    NVIDIA_PROFILE,
    PHILIPS_PROFILE,
    PROFILES,
    SONY_PROFILE,
    TCL_PROFILE,
    XIAOMI_PROFILE,
    BrandProfile,
    IntentDefinition,
    detect_brand_profile,
)


class TestDatabaseAdversarialGaps(unittest.TestCase):
    """Adversarial coverage for companion/opentv/debloat/database.py."""

    def test_package_entry_serialization_with_string_category(self):
        """Verifies PackageEntry.to_dict handles raw string category cleanly."""
        entry = PackageEntry(
            package_name="com.test.bloat",
            category="safe",  # Pass as string rather than enum
            human_name="Test Bloat",
            description="Testing string category handling",
            brand="test_brand",
            reasons=["ad_tracker"],
            caveats="none",
            service_impact="minor",
        )
        d = entry.to_dict()
        self.assertEqual(d["category"], "safe")
        self.assertEqual(d["package_name"], "com.test.bloat")
        self.assertEqual(d["brand"], "test_brand")
        self.assertEqual(d["reasons"], ["ad_tracker"])
        self.assertEqual(d["caveats"], "none")
        self.assertEqual(d["service_impact"], "minor")

    def test_package_entry_from_dict_with_invalid_category_fallback(self):
        """Invalid category string falls back safely to SafetyCategory.REVIEW."""
        raw_data = {
            "package_name": "com.unknown.service",
            "category": "not_a_valid_category_xyz",
            "human_name": "Unknown",
        }
        entry = PackageEntry.from_dict(raw_data)
        self.assertEqual(entry.category, SafetyCategory.REVIEW)
        self.assertEqual(entry.human_name, "Unknown")
        self.assertEqual(entry.description, "")
        self.assertEqual(entry.brand, "generic")

    def test_package_entry_from_dict_defaults_missing_fields(self):
        """Missing optional fields in dictionary resolve to deterministic defaults."""
        raw_data = {"package_name": "com.minimal.app"}
        entry = PackageEntry.from_dict(raw_data)
        self.assertEqual(entry.package_name, "com.minimal.app")
        self.assertEqual(entry.human_name, "com.minimal.app")
        self.assertEqual(entry.category, SafetyCategory.REVIEW)
        self.assertEqual(entry.description, "")
        self.assertEqual(entry.brand, "generic")
        self.assertEqual(entry.reasons, [])
        self.assertIsNone(entry.caveats)
        self.assertIsNone(entry.service_impact)

    def test_package_entry_from_dict_missing_package_name_raises_key_error(self):
        """Missing 'package_name' in from_dict raises KeyError."""
        with self.assertRaises(KeyError):
            PackageEntry.from_dict({"human_name": "Missing Package Name"})

    def test_package_safety_db_custom_catalog_injection(self):
        """Initializing PackageSafetyDB with a custom catalog dict isolates the DB from defaults."""
        custom_pkg = PackageEntry("com.custom.app", SafetyCategory.SAFE, "Custom", "Desc")
        custom_catalog = {"com.custom.app": custom_pkg}
        db = PackageSafetyDB(catalog=custom_catalog)
        self.assertEqual(db.classify("com.custom.app").category, SafetyCategory.SAFE)
        # Default package should not exist in this isolated custom catalog
        self.assertEqual(db.classify("android").category, SafetyCategory.REVIEW)

    def test_package_safety_db_get_entry_existing_and_missing(self):
        """get_entry returns PackageEntry for cataloged package, None for uncataloged."""
        db = PackageSafetyDB()
        entry = db.get_entry("com.android.systemui")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.category, SafetyCategory.NEVER)
        self.assertIsNone(db.get_entry("com.completely.unknown.fake.package"))

    def test_package_safety_db_add_custom_entry(self):
        """add_custom_entry dynamically injects or overwrites an entry."""
        db = PackageSafetyDB()
        new_entry = PackageEntry(
            package_name="com.oem.sponsored.launcher",
            category=SafetyCategory.SAFE,
            human_name="Sponsored Launcher",
            description="Replaced by OpenTV",
        )
        db.add_custom_entry(new_entry)
        self.assertEqual(db.categorize("com.oem.sponsored.launcher"), SafetyCategory.SAFE)
        self.assertTrue(db.is_safe_to_disable("com.oem.sponsored.launcher"))

    def test_package_safety_db_load_custom_overrides_nonexistent_file(self):
        """Non-existent file path returns 0 count without raising error."""
        db = PackageSafetyDB()
        loaded = db.load_custom_overrides("/tmp/definitely_non_existent_opentv_overrides.json")
        self.assertEqual(loaded, 0)

    def test_package_safety_db_load_custom_overrides_invalid_type(self):
        """Passing an invalid object type (not str, Path, or dict) raises TypeError."""
        db = PackageSafetyDB()
        with self.assertRaises(TypeError):
            db.load_custom_overrides(12345)  # type: ignore

    def test_package_safety_db_load_custom_overrides_list_format(self):
        """Loads overrides provided as a list and skips malformed items."""
        db = PackageSafetyDB()
        data = {
            "overrides": [
                {"package_name": "com.vendor.adware", "category": "safe", "human_name": "Vendor Ad"},
                {"not_a_valid_entry": 123},  # Should be skipped
                "not_a_dict",  # Should be skipped
                {"package_name": "com.vendor.framework", "category": "never", "human_name": "Vendor Framework"},
            ]
        }
        count = db.load_custom_overrides(data)
        self.assertEqual(count, 2)
        self.assertEqual(db.categorize("com.vendor.adware"), SafetyCategory.SAFE)
        self.assertEqual(db.categorize("com.vendor.framework"), SafetyCategory.NEVER)

    def test_package_safety_db_load_custom_overrides_dict_format(self):
        """Loads overrides provided as a dict mapping package names to info dicts."""
        db = PackageSafetyDB()
        data = {
            "packages": {
                "com.tcl.customad": {"category": "safe", "human_name": "TCL Custom Ad"},
                "com.tcl.malformed": "not_a_dict_skipped",
                "com.tcl.customcore": {"category": "never", "human_name": "TCL Custom Core"},
            }
        }
        count = db.load_custom_overrides(data)
        self.assertEqual(count, 2)
        self.assertEqual(db.categorize("com.tcl.customad"), SafetyCategory.SAFE)
        self.assertEqual(db.categorize("com.tcl.customcore"), SafetyCategory.NEVER)

    def test_package_safety_db_load_custom_overrides_from_real_file(self):
        """Loads overrides from an actual temporary JSON file via Path object."""
        db = PackageSafetyDB()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({
                "overrides": [
                    {"package_name": "com.file.override.app", "category": "safe", "human_name": "File App"}
                ]
            }, f)
            temp_path = Path(f.name)

        try:
            count = db.load_custom_overrides(temp_path)
            self.assertEqual(count, 1)
            self.assertEqual(db.categorize("com.file.override.app"), SafetyCategory.SAFE)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_package_safety_db_get_packages_by_category_brand_filtering(self):
        """get_packages_by_category filters correctly with brand scoping and generic inclusion."""
        db = PackageSafetyDB()
        # Query NEVER packages for Sony: should include Sony specific AND generic packages
        sony_never = db.get_packages_by_category(SafetyCategory.NEVER, brand_id="sony")
        sony_brands = {entry.brand for entry in sony_never}
        self.assertTrue(sony_brands.issubset({"sony", "generic"}))
        self.assertTrue(any(e.package_name == "android" for e in sony_never))
        self.assertTrue(any(e.package_name == "com.sony.dtv.tvx" for e in sony_never))
        self.assertFalse(any(e.package_name == "com.tcl.settings" for e in sony_never))

        # Query without brand filter returns all brands
        all_safe = db.get_packages_by_category(SafetyCategory.SAFE, brand_id=None)
        all_brands = {entry.brand for entry in all_safe}
        self.assertIn("sony", all_brands)
        self.assertIn("tcl", all_brands)
        self.assertIn("generic", all_brands)

    def test_package_safety_db_get_catalog_stats_structure(self):
        """get_catalog_stats returns total count and breakdown by category and brand."""
        db = PackageSafetyDB()
        stats = db.get_catalog_stats()
        self.assertIn("total", stats)
        self.assertIn("by_category", stats)
        self.assertIn("by_brand", stats)
        self.assertGreater(stats["total"], 80)
        self.assertEqual(
            stats["total"],
            sum(stats["by_category"].values())
        )
        self.assertIn("never", stats["by_category"])
        self.assertIn("safe", stats["by_category"])
        self.assertIn("keep", stats["by_category"])
        self.assertIn("sony", stats["by_brand"])
        self.assertIn("tcl", stats["by_brand"])


class TestGuardrailsAdversarialEdgeCases(unittest.TestCase):
    """Adversarial coverage for companion/opentv/debloat/guardrails.py."""

    def setUp(self):
        self.guard = GuardrailsEngine()

    def test_validate_package_name_rejects_non_string_types(self):
        """Validates that non-string types raise ValueError."""
        invalid_types = [123, 45.67, True, False, ["pkg"], {"name": "pkg"}, object()]
        for item in invalid_types:
            with self.assertRaises(ValueError):
                self.guard.validate_package_name(item)  # type: ignore

    def test_validate_package_name_rejects_all_illegal_shell_chars(self):
        """Verifies every individual illegal shell character triggers a ValueError."""
        for char in ILLEGAL_SHELL_CHARS:
            payload = f"com.safe{char}evil.app"
            with self.assertRaises(ValueError) as ctx:
                self.guard.validate_package_name(payload)
            self.assertIn("illegal shell characters", str(ctx.exception))

    def test_validate_package_name_allows_sole_framework_android(self):
        """'android' is explicitly permitted as the only single-token package name."""
        # 'android' should not raise
        self.guard.validate_package_name("android")

        # Other single-token names must raise
        for single in ["system", "app", "linux", "google"]:
            with self.assertRaises(ValueError):
                self.guard.validate_package_name(single)

    def test_validate_package_name_rejects_regex_boundaries(self):
        """Rejects package names violating domain-syntax boundary conditions."""
        malformed_names = [
            ".com.leading.dot",
            "com.trailing.dot.",
            "com..double.dot",
            "com.has-hyphen.app",
            "com.has@symbol.app",
            "com.has:colon.app",
            "123",
            "com.",
            ".com",
        ]
        for name in malformed_names:
            with self.assertRaises(ValueError):
                self.guard.validate_package_name(name)

    def test_persistent_flag_extraction_from_dumpsys(self):
        """Tests parsing of PERSISTENT flag across dumpsys output variants."""
        # 1. pkgFlags=[ ... PERSISTENT ... ]
        dumpsys_1 = "  Package [com.system.daemon]\n    pkgFlags=[ SYSTEM HAS_CODE PERSISTENT ]\n"
        self.assertTrue(GuardrailsEngine.parse_persistent_flag_from_dumpsys(dumpsys_1))

        # 2. flags=0x... PERSISTENT
        dumpsys_2 = "  Package [com.system.daemon]\n    flags=0x12345 PERSISTENT\n"
        self.assertTrue(GuardrailsEngine.parse_persistent_flag_from_dumpsys(dumpsys_2))

        # 3. Substring fallback
        dumpsys_3 = "Some raw output indicating PERSISTENT process status"
        self.assertTrue(GuardrailsEngine.parse_persistent_flag_from_dumpsys(dumpsys_3))

        # 4. Negative case
        dumpsys_4 = "  Package [com.user.app]\n    pkgFlags=[ SYSTEM HAS_CODE ]\n"
        self.assertFalse(GuardrailsEngine.parse_persistent_flag_from_dumpsys(dumpsys_4))

    def test_persistent_shield_blocks_disabling(self):
        """Packages marked PERSISTENT raise GuardrailViolation with rule='persistent_shield'."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable("com.vendor.daemon", pkg_flags="PERSISTENT")
        self.assertEqual(ctx.exception.rule, "persistent_shield")
        self.assertEqual(ctx.exception.package_name, "com.vendor.daemon")

    def test_google_tv_launcherx_shield_via_brand_id_ccwgtv(self):
        """launcherx is shielded when brand_id='ccwgtv' even if is_google_tv=False."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                "com.google.android.apps.tv.launcherx",
                brand_id="ccwgtv",
                is_google_tv=False,
                force_google_tv=False,
            )
        self.assertEqual(ctx.exception.rule, "launcherx_shield")

    def test_google_tv_launcherx_shield_bypass_via_env_var(self):
        """Setting GOOGLE_TV env var allows bypassing launcherx guardrail."""
        for val in ("1", "true", "yes", "True", "YES"):
            os.environ["GOOGLE_TV"] = val
            try:
                allowed = self.guard.can_disable(
                    "com.google.android.apps.tv.launcherx",
                    is_google_tv=True,
                    force_google_tv=False,
                )
                self.assertTrue(allowed)
            finally:
                os.environ.pop("GOOGLE_TV", None)

    def test_google_tv_launcherx_allowed_on_generic_aosp(self):
        """On generic non-Google TV systems, launcherx is not protected by launcherx_shield."""
        allowed = self.guard.can_disable(
            "com.google.android.apps.tv.launcherx",
            brand_id="generic",
            is_google_tv=False,
            force_google_tv=False,
        )
        self.assertTrue(allowed)

    def test_provisioning_gate_blocks_all_setup_wizards_when_unprovisioned(self):
        """All setup wizard packages are blocked when device_provisioned != 1."""
        for wizard in SETUP_WIZARDS:
            for bad_prov in (0, 2, -1):
                with self.assertRaises(GuardrailViolation) as ctx:
                    self.guard.check_can_disable(wizard, device_provisioned=bad_prov)
                self.assertEqual(ctx.exception.rule, "provisioning_gate")
                self.assertEqual(ctx.exception.package_name, wizard)

    def test_provisioning_gate_allows_setup_wizards_when_provisioned(self):
        """All setup wizard packages are allowed when device_provisioned == 1."""
        for wizard in SETUP_WIZARDS:
            self.assertTrue(
                self.guard.can_disable(wizard, device_provisioned=1)
            )

    def test_complex_ime_accounting_custom_ime_suffix_and_middle(self):
        """Custom IMEs ending in '.ime' or containing '.inputmethod.' are subject to IME guard."""
        custom_ime = "com.sample.vendor.ime"
        custom_mid_ime = "com.sample.inputmethod.custom"

        # Disabling when it is the sole keyboard raises violation
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                custom_ime,
                installed_packages=[custom_ime],
                disabled_packages=[],
            )
        self.assertEqual(ctx.exception.rule, "ime_preservation")

        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                custom_mid_ime,
                installed_packages=[custom_mid_ime],
                disabled_packages=[],
            )
        self.assertEqual(ctx.exception.rule, "ime_preservation")

        # Disabling when another keyboard remains active succeeds
        installed = [custom_ime, "com.google.android.inputmethod.latin"]
        self.assertTrue(
            self.guard.can_disable(
                custom_ime,
                installed_packages=installed,
                disabled_packages=[],
            )
        )

    def test_complex_ime_accounting_default_fallback_to_known_imes(self):
        """When installed_packages is None, KNOWN_IMES acts as the active candidate set."""
        known_list = list(KNOWN_IMES)
        # Disable 3 of them
        disabled = known_list[:3]
        target = known_list[3]  # The 4th and last remaining

        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable(
                target,
                installed_packages=None,
                disabled_packages=disabled,
            )
        self.assertEqual(ctx.exception.rule, "ime_preservation")

    def test_filter_safe_to_disable_sequential_ime_exhaustion(self):
        """Sequential filtering disables first IME but blocks second to maintain at least one keyboard."""
        imes = ["com.google.android.inputmethod.latin", "com.android.inputmethod.latin"]
        permitted, violations = self.guard.filter_safe_to_disable(
            packages=imes,
            installed_packages=imes,
            disabled_packages=[],
        )
        self.assertEqual(len(permitted), 1)
        self.assertEqual(permitted[0], imes[0])
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0][0], imes[1])
        self.assertIn("last remaining Input Method", violations[0][1])

    def test_remote_service_shield_blocks_all_oem_remotes(self):
        """Verifies all defined CORE_REMOTE_SERVICES are protected across all brands."""
        for remote_pkg in CORE_REMOTE_SERVICES:
            with self.assertRaises(GuardrailViolation) as ctx:
                self.guard.check_can_disable(remote_pkg)
            self.assertEqual(ctx.exception.rule, "remote_service_shield")
            self.assertEqual(ctx.exception.package_name, remote_pkg)

    def test_philips_homeintent_shield(self):
        """Disabling org.droidtv.homeintentresolver raises GuardrailViolation."""
        with self.assertRaises(GuardrailViolation) as ctx:
            self.guard.check_can_disable("org.droidtv.homeintentresolver")
        self.assertEqual(ctx.exception.rule, "philips_homeintent_shield")

    def test_oled_screensaver_shield_on_oled_vs_lcd(self):
        """Screensavers are blocked on OLED displays, permitted on LCD."""
        for saver in OLED_SCREENSAVERS:
            # Blocked on OLED
            with self.assertRaises(GuardrailViolation) as ctx:
                self.guard.check_can_disable(saver, is_oled=True)
            self.assertEqual(ctx.exception.rule, "oled_burnin_shield")

            # Permitted on standard LCD (since they are KEEP in DB, not NEVER)
            self.assertTrue(
                self.guard.can_disable(saver, is_oled=False)
            )

    def test_core_system_shield_packages(self):
        """android, systemui, settings, shell are strictly blocked by core_system_shield."""
        core_pkgs = ("android", "com.android.systemui", "com.android.settings", "com.android.shell")
        for pkg in core_pkgs:
            with self.assertRaises(GuardrailViolation) as ctx:
                self.guard.check_can_disable(pkg)
            self.assertEqual(ctx.exception.rule, "core_system_shield")

    def test_safety_db_never_shield_blocks_unexempt_brand_criticals(self):
        """Unexempt packages categorized as NEVER trigger safety_db_never_shield."""
        unexempt_criticals = [
            ("com.sony.dtv.tvx", "sony"),
            ("com.tcl.settings", "tcl"),
            ("org.droidtv.playtv", "philips"),
            ("com.jamdeo.tv.common", "hisense"),
            ("com.xiaomi.mitv.settings", "xiaomi"),
            ("com.nvidia.shield.agent", "nvidia"),
        ]
        for pkg, brand in unexempt_criticals:
            with self.assertRaises(GuardrailViolation) as ctx:
                self.guard.check_can_disable(pkg, brand_id=brand)
            self.assertEqual(ctx.exception.rule, "safety_db_never_shield")

    def test_filter_safe_to_disable_handles_malformed_syntax(self):
        """filter_safe_to_disable catches syntax errors into violations output."""
        packages = [
            "valid.safe.pkg",
            "bad;pkg;injection",
            "com.tcl.settings",
            "",
            "com.normal.app",
        ]
        # Register valid.safe.pkg and com.normal.app as safe in db
        self.guard.safety_db.add_custom_entry(
            PackageEntry("valid.safe.pkg", SafetyCategory.SAFE, "Safe1", "Desc")
        )
        self.guard.safety_db.add_custom_entry(
            PackageEntry("com.normal.app", SafetyCategory.SAFE, "Safe2", "Desc")
        )

        permitted, violations = self.guard.filter_safe_to_disable(packages, brand_id="tcl")
        self.assertIn("valid.safe.pkg", permitted)
        self.assertIn("com.normal.app", permitted)
        violation_pkgs = [v[0] for v in violations]
        self.assertIn("bad;pkg;injection", violation_pkgs)
        self.assertIn("com.tcl.settings", violation_pkgs)
        self.assertIn("", violation_pkgs)


class TestRollbackAdversarialResilience(unittest.TestCase):
    """Adversarial coverage for companion/opentv/debloat/rollback.py."""

    def setUp(self):
        self.engine = RollbackEngine()

    def test_generate_sh_empty_packages(self):
        """Empty package list generates valid POSIX script without pm enable lines."""
        sh = self.engine.generate_sh([])
        self.assertTrue(sh.startswith("#!/bin/sh"))
        self.assertIn("set -e", sh)
        self.assertNotIn("pm enable", sh)
        self.assertIn("rm -f /data/local/tmp/opentv-disabled.txt", sh)
        self.assertIn("Rollback completed successfully", sh)

    def test_generate_sh_strips_whitespace_and_ignores_blank_lines(self):
        """Whitespace in package list is stripped and blank entries are discarded."""
        pkgs = ["   ", "  com.app.one  ", "\t\n", "com.app.two"]
        sh = self.engine.generate_sh(pkgs)
        self.assertIn('pm enable "com.app.one"', sh)
        self.assertIn('pm enable "com.app.two"', sh)
        self.assertNotIn('pm enable ""', sh)

    def test_generate_sh_with_target_device_flag(self):
        """Specifying target_device sets TARGET and DEV_ARG."""
        sh = self.engine.generate_sh(["com.app.one"], target_device="192.168.1.100:5555")
        self.assertIn('TARGET="192.168.1.100:5555"', sh)
        self.assertIn('DEV_ARG="-s 192.168.1.100:5555"', sh)

    def test_generate_bat_empty_packages(self):
        """Empty package list generates valid batch script with CRLF endings."""
        bat = self.engine.generate_bat([])
        self.assertTrue(bat.startswith("@echo off\r\n"))
        self.assertIn("setlocal enabledelayedexpansion\r\n", bat)
        self.assertNotIn("pm enable", bat)
        self.assertIn("Rollback completed.\r\n", bat)

    def test_generate_bat_handles_target_device_flag(self):
        """Batch script formats DEV_ARG with device serial."""
        bat = self.engine.generate_bat(["com.app.one"], target_device="emulator-5554")
        self.assertIn("set DEV_ARG=-s emulator-5554\r\n", bat)

    def test_generate_ps1_empty_packages(self):
        """Empty package list formats PowerShell empty array."""
        ps1 = self.engine.generate_ps1([])
        self.assertIn("$packages = @()", ps1)
        self.assertIn("[CmdletBinding()]", ps1)

    def test_generate_ps1_with_target_device(self):
        """PowerShell script embeds target device default parameter."""
        ps1 = self.engine.generate_ps1(["com.app.one"], target_device="192.168.1.50:5555")
        self.assertIn('param([string]$Target = "192.168.1.50:5555")', ps1)

    def test_rollback_launcherx_notification_listener_all_platforms(self):
        """When launcherx is present, all three platforms restore notification listener."""
        pkgs = ["com.google.android.apps.tv.launcherx", "tv.samba.ssm"]
        sh = self.engine.generate_sh(pkgs)
        bat = self.engine.generate_bat(pkgs)
        ps1 = self.engine.generate_ps1(pkgs)

        expected_cmd = "cmd notification allow_listener"
        self.assertIn(expected_cmd, sh)
        self.assertIn(LAUNCHERX_LISTENER_SVC, sh)

        self.assertIn(expected_cmd, bat)
        self.assertIn(LAUNCHERX_LISTENER_SVC, bat)

        self.assertIn(expected_cmd, ps1)
        self.assertIn(LAUNCHERX_LISTENER_SVC, ps1)

    def test_write_rollback_scripts_polymorphic_signatures(self):
        """Verifies both argument orders for write_rollback_scripts."""
        pkgs = ["tv.samba.ssm"]
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            # Order 1: (packages, output_dir)
            res1 = self.engine.write_rollback_scripts(pkgs, tmp1)
            self.assertTrue(Path(res1["sh"]).exists())
            self.assertTrue(Path(res1["bat"]).exists())
            self.assertTrue(Path(res1["ps1"]).exists())

            # Order 2: (output_dir, packages)
            res2 = self.engine.write_rollback_scripts(tmp2, pkgs)
            self.assertTrue(Path(res2["sh"]).exists())
            self.assertTrue(Path(res2["bat"]).exists())
            self.assertTrue(Path(res2["ps1"]).exists())

    def test_write_rollback_scripts_atomic_permissions(self):
        """Verifies file modes (0o755 for POSIX shell script)."""
        pkgs = ["tv.samba.ssm"]
        with tempfile.TemporaryDirectory() as tmp:
            res = self.engine.write_rollback_scripts(pkgs, tmp)
            sh_stat = os.stat(res["sh"])
            # Check executable bit on POSIX
            self.assertTrue(bool(sh_stat.st_mode & stat.S_IXUSR))


class TestAuditLoggerAdversarialErrorPaths(unittest.TestCase):
    """Adversarial coverage for companion/opentv/debloat/audit.py."""

    def test_audit_event_to_dict_with_and_without_details(self):
        """AuditEvent.to_dict omits 'details' if None, preserves if non-None."""
        ev1 = AuditEvent(
            action="DISABLE_PACKAGE",
            package_name="tv.samba.ssm",
            device_id="192.168.1.50:5555",
            details=None,
        )
        d1 = ev1.to_dict()
        self.assertNotIn("details", d1)

        ev2 = AuditEvent(
            action="DISABLE_PACKAGE",
            package_name="tv.samba.ssm",
            device_id="192.168.1.50:5555",
            details="Error code 127",
        )
        d2 = ev2.to_dict()
        self.assertEqual(d2["details"], "Error code 127")

    def test_audit_event_format_text_all_fields(self):
        """AuditEvent.format_text includes command, rollback command, and details when present."""
        ev = AuditEvent(
            action="DISABLE_PACKAGE",
            package_name="tv.samba.ssm",
            device_id="192.168.1.50:5555",
            brand_profile="sony",
            category="safe",
            previous_state="enabled",
            new_state="disabled",
            command="adb shell pm disable-user tv.samba.ssm",
            rollback_command="adb shell pm enable tv.samba.ssm",
            verified=True,
            status="SUCCESS",
            details="Telemetry package disabled",
        )
        text = ev.format_text()
        self.assertIn("ACTION: DISABLE_PACKAGE", text)
        self.assertIn("SONY", text)
        self.assertIn("Command: adb shell pm disable-user", text)
        self.assertIn("Rollback Command: adb shell pm enable", text)
        self.assertIn("Details: Telemetry package disabled", text)
        self.assertIn("Verified: YES", text)

    def test_audit_logger_log_from_dict(self):
        """Logging a raw dict constructs AuditEvent with key aliases."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            raw = {
                "action": "ENABLE_PACKAGE",
                "package": "com.netflix.ninja",  # 'package' alias for 'package_name'
                "device_id": "test_device",
                "status": "enabled",              # 'status' alias for 'new_state'
                "exit_code": 0,
            }
            ev = logger.log(raw)
            self.assertEqual(ev.package_name, "com.netflix.ninja")
            self.assertEqual(ev.action, "ENABLE_PACKAGE")
            events = logger.read_events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["package_name"], "com.netflix.ninja")

    def test_audit_logger_record_disable_and_enable_failure_states(self):
        """Non-zero exit code or unverified state records FAILED status."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)

            # Failure due to exit code != 0
            ev1 = logger.record_disable(
                device_id="192.168.1.50",
                package_name="com.failed.pkg",
                exit_code=1,
                verified=True,
            )
            self.assertEqual(ev1.status, "FAILED")

            # Failure due to unverified post-condition
            ev2 = logger.record_enable(
                device_id="192.168.1.50",
                package_name="com.failed.pkg2",
                exit_code=0,
                verified=False,
            )
            self.assertEqual(ev2.status, "FAILED")

    def test_audit_logger_read_events_from_empty_or_missing_file(self):
        """read_events returns empty list when log file is missing or empty."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            # File missing
            self.assertEqual(logger.read_events(), [])

            # File empty
            logger.json_path.write_text("", encoding="utf-8")
            self.assertEqual(logger.read_events(), [])

            # Whitespace only
            logger.json_path.write_text("   \n\n  ", encoding="utf-8")
            self.assertEqual(logger.read_events(), [])

    def test_audit_logger_read_events_from_json_array(self):
        """read_events parses a JSON array formatted audit log file."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            records = [
                {"action": "DISABLE_PACKAGE", "package_name": "pkg.one"},
                {"action": "DISABLE_PACKAGE", "package_name": "pkg.two"},
            ]
            logger.json_path.write_text(json.dumps(records), encoding="utf-8")
            events = logger.read_events()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["package_name"], "pkg.one")

    def test_audit_logger_read_events_skips_corrupted_json_lines(self):
        """read_events silently ignores corrupted lines in JSONL files."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            content = (
                '{"action": "DISABLE", "package_name": "pkg1"}\n'
                'CORRUPT_NOT_JSON_LINE_HERE\n'
                '{"action": "DISABLE", "package_name": "pkg2"}\n'
                '{"truncated_json": \n'
            )
            logger.json_path.write_text(content, encoding="utf-8")
            events = logger.read_events()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["package_name"], "pkg1")
            self.assertEqual(events[1]["package_name"], "pkg2")

    def test_audit_logger_read_events_recovers_from_corrupted_json_array(self):
        """If file looks like array [ ... ] but is malformed JSON, falls back to line parser."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            content = (
                '[\n'
                '{"action": "DISABLE", "package_name": "valid_line"}\n'
                ']'
            )
            logger.json_path.write_text(content, encoding="utf-8")
            events = logger.read_events()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["package_name"], "valid_line")

    def test_audit_logger_clear_functionality(self):
        """clear unlinks log files safely even if they already do not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            logger.record_disable(device_id="dev", package_name="pkg")
            self.assertTrue(logger.json_path.exists())
            self.assertTrue(logger.txt_path.exists())

            logger.clear()
            self.assertFalse(logger.json_path.exists())
            self.assertFalse(logger.txt_path.exists())

            # Calling clear a second time when files are missing should not raise
            logger.clear()

    def test_audit_logger_thread_safety_concurrency(self):
        """Simultaneous concurrent logging across multiple threads causes no file corruption."""
        with tempfile.TemporaryDirectory() as tmp:
            logger = AuditLogger(log_dir=tmp)
            num_threads = 10
            logs_per_thread = 20

            def worker(thread_idx: int):
                for i in range(logs_per_thread):
                    logger.record_disable(
                        device_id=f"device_{thread_idx}",
                        package_name=f"com.thread{thread_idx}.pkg{i}",
                    )

            threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            events = logger.read_events()
            self.assertEqual(len(events), num_threads * logs_per_thread)


class TestProfilesDetectorAdversarialHeuristics(unittest.TestCase):
    """Adversarial coverage for companion/opentv/profiles/detector.py."""

    def test_intent_definition_to_am_start_args_all_branches(self):
        """Verifies IntentDefinition.to_am_start_args builds flags and extras correctly."""
        intent = IntentDefinition(
            action="android.intent.action.VIEW",
            component="org.opentv.launcher/.MainActivity",
            category="android.intent.category.HOME",
            data_uri="content://tv/input/1",
            flags=0x10000000,
            extras={
                "bool_key": True,
                "bool_false": False,
                "int_key": 42,
                "str_key": "sample_string",
            },
        )
        args = intent.to_am_start_args()
        self.assertEqual(args[0:2], ["am", "start"])
        self.assertIn("-a", args)
        self.assertIn("android.intent.action.VIEW", args)
        self.assertIn("-n", args)
        self.assertIn("org.opentv.launcher/.MainActivity", args)
        self.assertIn("-c", args)
        self.assertIn("android.intent.category.HOME", args)
        self.assertIn("-d", args)
        self.assertIn("content://tv/input/1", args)
        self.assertIn("-f", args)
        self.assertIn(str(0x10000000), args)
        self.assertIn("--ez", args)
        self.assertIn("bool_key", args)
        self.assertIn("true", args)
        self.assertIn("false", args)
        self.assertIn("--ei", args)
        self.assertIn("int_key", args)
        self.assertIn("42", args)
        self.assertIn("--es", args)
        self.assertIn("str_key", args)
        self.assertIn("sample_string", args)

    def test_brand_profile_get_quick_setting_intent_aliases(self):
        """Verifies resolution of quick setting aliases (display, audio, input, ambient)."""
        profile = TCL_PROFILE
        # Settings
        self.assertEqual(profile.get_quick_setting_intent("settings"), profile.settings_intent)
        self.assertEqual(profile.get_quick_setting_intent("main_settings"), profile.settings_intent)
        # Display / Picture
        self.assertEqual(profile.get_quick_setting_intent("display"), profile.picture_intent)
        self.assertEqual(profile.get_quick_setting_intent("picture"), profile.picture_intent)
        # Audio / Sound
        self.assertEqual(profile.get_quick_setting_intent("audio"), profile.sound_intent)
        self.assertEqual(profile.get_quick_setting_intent("sound"), profile.sound_intent)
        # Input / HDMI
        self.assertEqual(profile.get_quick_setting_intent("input"), profile.inputs_intent)
        self.assertEqual(profile.get_quick_setting_intent("hdmi"), profile.inputs_intent)
        self.assertEqual(profile.get_quick_setting_intent("inputs"), profile.inputs_intent)
        # Ambient / Screensaver
        self.assertEqual(profile.get_quick_setting_intent("ambient"), profile.screensaver_intent)
        self.assertEqual(profile.get_quick_setting_intent("screensaver"), profile.screensaver_intent)

        # Unrecognized / empty fallback
        fallback = profile.get_quick_setting_intent("unrecognized_tile")
        self.assertEqual(fallback.action, "android.settings.SETTINGS")
        self.assertEqual(fallback.fallback_keycode, 176)

        fallback_none = profile.get_quick_setting_intent("")
        self.assertEqual(fallback_none.action, "android.settings.SETTINGS")

    def test_brand_profile_get_hdmi_uri_fallbacks(self):
        """Port not mapped in profile returns standard hardware passthrough fallback URI."""
        profile = TCL_PROFILE  # Has HDMI 1, 2, 3
        # Port 1 returns direct OEM intent URI
        self.assertIn("com.tcl.tvinput", profile.get_hdmi_uri(1))

        # Port 4 is unmapped -> fallback to content://android.media.tv/passthrough/HW3
        self.assertEqual(
            profile.get_hdmi_uri(4),
            "content://android.media.tv/passthrough/HW3"
        )
        self.assertEqual(
            profile.get_hdmi_uri(5),
            "content://android.media.tv/passthrough/HW4"
        )

    def test_detect_brand_profile_ccwgtv_variations(self):
        """CCwGTV detection with device 'boreal' and model variations."""
        props1 = {"ro.product.manufacturer": "Google", "ro.product.device": "boreal"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "ccwgtv")

        props2 = {
            "ro.product.manufacturer": "Google LLC",
            "ro.product.model": "Chromecast with Google TV",
        }
        self.assertEqual(detect_brand_profile(props2).brand_id, "ccwgtv")

    def test_detect_brand_profile_nvidia_codenames_and_package(self):
        """Nvidia Shield detection via codenames (foster, sif) or shield agent package."""
        # Codename foster
        props1 = {"ro.product.manufacturer": "OEM", "ro.product.device": "foster_e"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "nvidia")

        # Codename sif
        props2 = {"ro.product.manufacturer": "OEM", "ro.product.device": "sif"}
        self.assertEqual(detect_brand_profile(props2).brand_id, "nvidia")

        # Package signature
        props3 = {"ro.product.manufacturer": "Unknown"}
        self.assertEqual(
            detect_brand_profile(props3, installed_packages=["com.nvidia.shield.agent"]).brand_id,
            "nvidia"
        )

    def test_detect_brand_profile_sony_model_regex_and_package(self):
        """Sony Bravia detection via model patterns (xbr-, xr-) and package signatures."""
        props1 = {"ro.product.manufacturer": "OEM", "ro.product.model": "XBR-65X900H"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "sony")

        props2 = {"ro.product.manufacturer": "OEM", "ro.product.model": "XR-65X90K"}
        self.assertEqual(detect_brand_profile(props2).brand_id, "sony")

        props3 = {"ro.product.manufacturer": "Generic"}
        self.assertEqual(
            detect_brand_profile(props3, installed_packages=["com.sony.dtv.tvinput"]).brand_id,
            "sony"
        )

    def test_detect_brand_profile_philips_tpv_mfg_and_package(self):
        """Philips detection via TPV manufacturer strings or home router package."""
        props1 = {"ro.product.manufacturer": "tpv"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "philips")

        props2 = {"ro.product.brand": "Philips"}
        self.assertEqual(detect_brand_profile(props2).brand_id, "philips")

        props3 = {"ro.product.manufacturer": "Custom"}
        self.assertEqual(
            detect_brand_profile(props3, installed_packages=["org.droidtv.homeintentresolver"]).brand_id,
            "philips"
        )

    def test_detect_brand_profile_tcl_mfg_tte_and_brands(self):
        """TCL detection via TTE manufacturer or FFALCON brands."""
        props1 = {"ro.product.manufacturer": "tte"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "tcl")

        props2 = {"ro.product.brand": "ffalcon"}
        self.assertEqual(detect_brand_profile(props2).brand_id, "tcl")

        props3 = {"ro.product.brand": "iffalcon"}
        self.assertEqual(detect_brand_profile(props3).brand_id, "tcl")

    def test_detect_brand_profile_xiaomi_redmi_and_package(self):
        """Xiaomi detection via Redmi brand or PatchWall package."""
        props1 = {"ro.product.brand": "redmi"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "xiaomi")

        props2 = {"ro.product.manufacturer": "OEM"}
        self.assertEqual(
            detect_brand_profile(props2, installed_packages=["com.mitv.tvhome"]).brand_id,
            "xiaomi"
        )

    def test_detect_brand_profile_hisense_jamdeo_mfg_and_package(self):
        """Hisense detection via Jamdeo manufacturer or common package."""
        props1 = {"ro.product.manufacturer": "jamdeo"}
        self.assertEqual(detect_brand_profile(props1).brand_id, "hisense")

        props2 = {"ro.product.brand": "hisense"}
        self.assertEqual(detect_brand_profile(props2).brand_id, "hisense")

        props3 = {"ro.product.manufacturer": "Generic"}
        self.assertEqual(
            detect_brand_profile(props3, installed_packages=["com.jamdeo.tv.common"]).brand_id,
            "hisense"
        )

    def test_detect_brand_profile_generic_fallback(self):
        """Completely blank props or unrecognized hardware defaults cleanly to generic."""
        self.assertEqual(detect_brand_profile({}).brand_id, "generic")
        self.assertEqual(
            detect_brand_profile({"ro.product.manufacturer": "UnbrandedBox"}).brand_id,
            "generic"
        )

    def test_detect_brand_profile_oled_detection_regex(self):
        """OLED model/device regex or manufacturer substring enables OLED protection on copy."""
        # 1. Model containing 'oled'
        props1 = {
            "ro.product.manufacturer": "LG",
            "ro.product.model": "OLED55C1PUB",
        }
        prof1 = detect_brand_profile(props1)
        self.assertTrue(prof1.has_oled_protection)

        # 2. Sony OLED model (XR-55A80J)
        props2 = {
            "ro.product.manufacturer": "Sony",
            "ro.product.model": "XR-55A80J",
        }
        prof2 = detect_brand_profile(props2)
        self.assertEqual(prof2.brand_id, "sony")
        self.assertTrue(prof2.has_oled_protection)

        # 3. Model with A90 / A95
        props3 = {
            "ro.product.manufacturer": "Sony",
            "ro.product.model": "XR-65A95K",
        }
        prof3 = detect_brand_profile(props3)
        self.assertTrue(prof3.has_oled_protection)

        # 4. Device containing 'oled'
        props4 = {
            "ro.product.manufacturer": "Generic",
            "ro.product.device": "atv_oled_panel",
        }
        prof4 = detect_brand_profile(props4)
        self.assertTrue(prof4.has_oled_protection)

        # 5. Non-OLED does not enable protection
        props5 = {
            "ro.product.manufacturer": "Sony",
            "ro.product.model": "KD-55X85J",
        }
        prof5 = detect_brand_profile(props5)
        self.assertFalse(prof5.has_oled_protection)


if __name__ == "__main__":
    unittest.main()
