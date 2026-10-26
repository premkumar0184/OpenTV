"""
Unit and integration tests for Dynamic Debloat Definitions & Remote Sync.
PROJECT.md Milestone 6:
- Validates platform-specific definitions cache paths.
- Enforces strict immutability for critical system packages (IMMUTABLE_NEVER_PACKAGES).
- Tests downloading and local syncing of definitions.
- Tests adversarial resistance against payload attempting to downgrade system components.
- Tests CLI integration with `opentv debloat --update-definitions`.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "companion"))

from opentv.cli import main, EXIT_SUCCESS, EXIT_ERROR
from opentv.debloat.database import (
    CURATED_PACKAGES,
    DEFAULT_DEFINITIONS_URL,
    IMMUTABLE_NEVER_PACKAGES,
    PackageEntry,
    PackageSafetyDB,
    SafetyCategory,
    get_definitions_cache_path,
    update_definitions,
)


class TestDynamicDebloatDefinitions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.cache_file = self.cache_dir / "definitions.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_immutable_never_packages_membership(self):
        """Verifies critical system and launcher packages are in IMMUTABLE_NEVER_PACKAGES."""
        critical = [
            "android",
            "com.android.systemui",
            "com.android.settings",
            "com.android.tv.settings",
            "com.android.shell",
            "com.android.packageinstaller",
            "com.google.android.packageinstaller",
            "com.google.android.permissioncontroller",
            "com.google.android.apps.tv.launcherx",
        ]
        for pkg in critical:
            self.assertIn(
                pkg,
                IMMUTABLE_NEVER_PACKAGES,
                f"Critical package {pkg} must be immutable NEVER",
            )

    def test_get_definitions_cache_path_posix(self):
        """Tests XDG and home directory cache paths on POSIX."""
        with patch("sys.platform", "linux"):
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}):
                p = get_definitions_cache_path()
                self.assertEqual(p, Path("/custom/config/opentv/definitions.json"))

            with patch.dict(os.environ, {}, clear=True):
                p = get_definitions_cache_path()
                self.assertEqual(p, Path.home() / ".config" / "opentv" / "definitions.json")

    def test_get_definitions_cache_path_windows(self):
        """Tests APPDATA cache path on Windows."""
        with patch("sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "/custom/appdata"}):
                p = get_definitions_cache_path()
                self.assertEqual(p, Path("/custom/appdata") / "OpenTV" / "definitions.json")

    def test_add_custom_entry_blocks_immutable_downgrade(self):
        """PackageSafetyDB.add_custom_entry strictly blocks downgrading NEVER packages."""
        db = PackageSafetyDB(auto_load_cache=False)
        # Attempt to mark android as SAFE
        malicious = PackageEntry(
            package_name="android",
            category=SafetyCategory.SAFE,
            human_name="Exploit Attempt",
            description="Trying to disable system",
        )
        res = db.add_custom_entry(malicious, enforce_immutable=True)
        self.assertFalse(res)
        self.assertEqual(db.classify("android").category, SafetyCategory.NEVER)

        # Attempt to mark launcherx as SAFE
        malicious_launcher = PackageEntry(
            package_name="com.google.android.apps.tv.launcherx",
            category=SafetyCategory.SAFE,
            human_name="Exploit Launcher",
            description="Trying to bootloop GTV",
        )
        res_launcher = db.add_custom_entry(malicious_launcher, enforce_immutable=True)
        self.assertFalse(res_launcher)
        self.assertEqual(
            db.classify("com.google.android.apps.tv.launcherx").category,
            SafetyCategory.NEVER,
        )

        # Legitimate custom SAFE entry
        legit = PackageEntry(
            package_name="com.custom.bloat",
            category=SafetyCategory.SAFE,
            human_name="Custom Bloat",
            description="Vendor junk",
        )
        res_legit = db.add_custom_entry(legit, enforce_immutable=True)
        self.assertTrue(res_legit)
        self.assertEqual(db.classify("com.custom.bloat").category, SafetyCategory.SAFE)

    def test_load_custom_overrides_filters_immutable(self):
        """Loading overrides JSON ignores immutable packages and counts applied entries."""
        db = PackageSafetyDB(auto_load_cache=False)
        overrides = {
            "overrides": [
                {"package_name": "android", "category": "safe"},
                {"package_name": "com.android.systemui", "category": "safe"},
                {"package_name": "com.test.valid.bloat1", "category": "safe"},
                {"package_name": "com.test.valid.bloat2", "category": "safe"},
            ]
        }
        count = db.load_custom_overrides(overrides, enforce_immutable=True)
        self.assertEqual(count, 2)
        self.assertEqual(db.classify("android").category, SafetyCategory.NEVER)
        self.assertEqual(db.classify("com.android.systemui").category, SafetyCategory.NEVER)
        self.assertEqual(db.classify("com.test.valid.bloat1").category, SafetyCategory.SAFE)
        self.assertEqual(db.classify("com.test.valid.bloat2").category, SafetyCategory.SAFE)

    def test_update_definitions_from_local_file(self):
        """update_definitions successfully syncs from a local definitions JSON file."""
        src_file = self.cache_dir / "src_defs.json"
        data = {
            "version": "1.2.0",
            "updated_at": "2026-10-26T15:00:00Z",
            "packages": [
                {
                    "package_name": "com.oem.telemetry",
                    "category": "safe",
                    "human_name": "OEM Telemetry",
                    "description": "Background tracking",
                },
                {
                    "package_name": "com.oem.adchannel",
                    "category": "safe",
                    "human_name": "OEM Ad Channel",
                    "description": "Banner ads",
                },
            ],
        }
        with open(src_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        success, msg, count = update_definitions(source=str(src_file), cache_path=self.cache_file)
        self.assertTrue(success)
        self.assertEqual(count, 2)
        self.assertTrue(self.cache_file.is_file())

        with open(self.cache_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(len(saved["packages"]), 2)
        self.assertEqual(saved["version"], "1.2.0")

    def test_update_definitions_adversarial_rejected(self):
        """update_definitions strips dangerous system package overrides from payload."""
        src_file = self.cache_dir / "adversarial.json"
        data = {
            "version": "1.0.0",
            "packages": [
                {"package_name": "android", "category": "safe"},
                {"package_name": "com.android.systemui", "category": "safe"},
                {"package_name": "com.google.android.apps.tv.launcherx", "category": "safe"},
                {"package_name": "com.real.bloatware", "category": "safe"},
            ],
        }
        with open(src_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        success, msg, count = update_definitions(source=str(src_file), cache_path=self.cache_file)
        self.assertTrue(success)
        self.assertEqual(count, 1)
        self.assertIn("dangerous overrides blocked", msg)

        with open(self.cache_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
        saved_names = [p["package_name"] for p in saved["packages"]]
        self.assertEqual(saved_names, ["com.real.bloatware"])

    def test_update_definitions_remote_mock(self):
        """update_definitions downloads via HTTP request with user agent."""
        mock_response = MagicMock()
        payload = json.dumps({
            "version": "1.0.5",
            "packages": [
                {"package_name": "com.remote.adware", "category": "safe"}
            ]
        }).encode("utf-8")
        mock_response.read.return_value = payload
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            success, msg, count = update_definitions(
                source="https://example.com/definitions.json",
                cache_path=self.cache_file,
            )
            self.assertTrue(success)
            self.assertEqual(count, 1)
            self.assertTrue(self.cache_file.is_file())

            # Verify request headers
            req = mock_urlopen.call_args[0][0]
            self.assertIn("OpenTV-Companion", req.headers["User-agent"])

    def test_update_definitions_corrupted_json(self):
        """update_definitions gracefully handles syntax errors in JSON source."""
        bad_file = self.cache_dir / "bad.json"
        bad_file.write_text("{ incomplete json: ...")

        success, msg, count = update_definitions(source=str(bad_file), cache_path=self.cache_file)
        self.assertFalse(success)
        self.assertIn("Invalid JSON format", msg)
        self.assertEqual(count, 0)

    def test_update_definitions_missing_packages_key(self):
        """update_definitions rejects schema without packages or overrides."""
        empty_schema_file = self.cache_dir / "empty_schema.json"
        empty_schema_file.write_text(json.dumps({"some_key": 123}))

        success, msg, count = update_definitions(source=str(empty_schema_file), cache_path=self.cache_file)
        self.assertFalse(success)
        self.assertIn("must contain 'packages' or 'overrides'", msg)

    def test_database_auto_loads_cache(self):
        """PackageSafetyDB automatically loads definitions from cached file if present."""
        data = {
            "version": "1.0.0",
            "packages": [
                {"package_name": "com.cached.adservice", "category": "safe", "human_name": "Cached Ads"}
            ]
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with patch("opentv.debloat.database.get_definitions_cache_path", return_value=self.cache_file):
            db = PackageSafetyDB(auto_load_cache=True)
            entry = db.classify("com.cached.adservice")
            self.assertEqual(entry.category, SafetyCategory.SAFE)
            self.assertEqual(entry.human_name, "Cached Ads")

    def test_cli_debloat_update_definitions(self):
        """Tests `opentv debloat --update-definitions --source <path>`."""
        src_file = self.cache_dir / "cli_defs.json"
        data = {
            "packages": [
                {"package_name": "com.cli.bloat", "category": "safe"}
            ]
        }
        with open(src_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("opentv.debloat.database.get_definitions_cache_path", return_value=self.cache_file):
            code = main(
                ["debloat", "--update-definitions", "--source", str(src_file)],
                stdout=stdout,
            )
            self.assertEqual(code, EXIT_SUCCESS)
            out = stdout.getvalue()
            self.assertIn("Definitions update successful", out)
            self.assertTrue(self.cache_file.is_file())


if __name__ == "__main__":
    unittest.main()
