"""
Unit tests for Milestone 5: Standalone Single-File Executables Distribution.
Validates zipapp archive creation, module integrity, CLI entry points,
and PyInstaller specification generation.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_binaries import (
    build_zipapp,
    generate_pyinstaller_spec,
    verify_zipapp,
)


class TestPackagingPipeline(unittest.TestCase):
    """Tests for standalone packaging tools in scripts/package_binaries.py."""

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.companion_dir = cls.project_root / "companion"
        cls.scripts_dir = cls.project_root / "scripts"

    def test_build_zipapp_creates_valid_archive(self):
        """build_zipapp creates a valid zipapp containing __main__.py and opentv package."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_opentv.pyz"
            built = build_zipapp(self.companion_dir, out_file)
            self.assertTrue(built.exists())
            self.assertTrue(verify_zipapp(built))

            # Inspect archive contents
            with zipfile.ZipFile(built, "r") as zf:
                names = zf.namelist()
                self.assertIn("__main__.py", names)
                self.assertIn("opentv/__init__.py", names)
                self.assertIn("opentv/cli.py", names)
                self.assertIn("opentv/core/device.py", names)
                self.assertIn("opentv/core/discovery.py", names)
                self.assertIn("opentv/core/app_names.py", names)
                self.assertIn("opentv/debloat/database.py", names)

    def test_built_zipapp_execution_help(self):
        """Executing built zipapp with --help prints usage and exits cleanly with code 0."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_opentv.pyz"
            build_zipapp(self.companion_dir, out_file)

            res = subprocess.run(
                [sys.executable, str(out_file), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("OpenTV Companion", res.stdout)
            self.assertIn("connect", res.stdout)
            self.assertIn("debloat", res.stdout)
            self.assertIn("tui", res.stdout)
            self.assertIn("discover", res.stdout)

    def test_generate_pyinstaller_spec(self):
        """generate_pyinstaller_spec creates a valid spec file referencing all opentv modules."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            spec_file = generate_pyinstaller_spec(Path(tmp_dir), self.project_root)
            self.assertTrue(spec_file.exists())
            content = spec_file.read_text(encoding="utf-8")
            self.assertIn("opentv.cli", content)
            self.assertIn("opentv.core.discovery", content)
            self.assertIn("opentv.core.app_names", content)
            self.assertIn("opentv.debloat.database", content)
            self.assertIn("console=True", content)

    def test_packaging_scripts_exist_and_executable(self):
        """Standalone packaging scripts exist in scripts/ with appropriate execution rights."""
        pkg_py = self.scripts_dir / "package_binaries.py"
        build_sh = self.scripts_dir / "build_standalone.sh"
        build_bat = self.scripts_dir / "build_standalone.bat"

        self.assertTrue(pkg_py.is_file())
        self.assertTrue(build_sh.is_file())
        self.assertTrue(build_bat.is_file())

        if os.name == "posix":
            self.assertTrue(bool(pkg_py.stat().st_mode & stat.S_IXUSR))
            self.assertTrue(bool(build_sh.stat().st_mode & stat.S_IXUSR))


if __name__ == "__main__":
    unittest.main()
