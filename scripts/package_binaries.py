#!/usr/bin/env python3
"""
OpenTV Standalone Binary Packaging Tool.
Milestone 5 (R5): Standalone Single-File Executables Distribution.

Builds standalone executables for OpenTV:
1. Standard Python executable zipapp (pure stdlib, zero pip dependencies).
2. Generates PyInstaller single-file spec for native Windows (.exe), macOS, and Linux compilation.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import tempfile
import zipapp
import zipfile
from pathlib import Path
from typing import Optional


def build_zipapp(
    source_dir: Path,
    output_path: Path,
    main_entry: str = "opentv.cli:main",
    shebang: str = "/usr/bin/env python3",
    compressed: bool = True,
) -> Path:
    """
    Builds a standalone executable Python zipapp from source directory.
    Uses Python's standard library `zipapp` module.
    """
    source_dir = Path(source_dir).resolve()
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        staging_dir = Path(tmp_dir) / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Copy the opentv package into staging directory
        pkg_src = source_dir / "opentv" if (source_dir / "opentv").exists() else source_dir
        pkg_dest = staging_dir / "opentv"
        shutil.copytree(
            pkg_src,
            pkg_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git*"),
        )

        # Create __main__.py inside staging if not present
        main_py = staging_dir / "__main__.py"
        if not main_py.exists():
            mod_path, func_name = main_entry.split(":")
            main_py.write_text(
                f"import sys\n"
                f"from {mod_path} import {func_name}\n"
                f"if __name__ == '__main__':\n"
                f"    sys.exit({func_name}())\n",
                encoding="utf-8",
            )

        # Build archive using standard zipapp
        zipapp.create_archive(
            source=staging_dir,
            target=output_path,
            interpreter=shebang,
            main=None,  # Handled by __main__.py
            compressed=compressed,
        )

    # Set executable permissions on POSIX systems
    if os.name == "posix":
        current_mode = output_path.stat().st_mode
        output_path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return output_path


def generate_pyinstaller_spec(output_dir: Path, project_root: Path) -> Path:
    """
    Generates a production PyInstaller .spec file configured for single-file,
    cross-platform compilation into native executables.
    """
    output_dir = Path(output_dir).resolve()
    project_root = Path(project_root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    spec_path = output_dir / "opentv.spec"

    companion_path = project_root / "companion"
    entry_script = companion_path / "opentv" / "__main__.py"

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
# OpenTV PyInstaller Build Specification
# Milestone 5: Standalone Single-File Executables Distribution

import sys
from pathlib import Path

block_cipher = None
project_root = Path(r'{project_root.as_posix()}')
companion_dir = Path(r'{companion_path.as_posix()}')

a = Analysis(
    [r'{entry_script.as_posix()}'],
    pathex=[str(companion_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'opentv',
        'opentv.cli',
        'opentv.core',
        'opentv.core.adb',
        'opentv.core.app_names',
        'opentv.core.config',
        'opentv.core.deployer',
        'opentv.core.device',
        'opentv.core.discovery',
        'opentv.debloat',
        'opentv.debloat.audit',
        'opentv.debloat.database',
        'opentv.debloat.guardrails',
        'opentv.debloat.rollback',
        'opentv.profiles',
        'opentv.profiles.detector',
        'opentv.tui',
        'opentv.tui.app',
        'opentv.tui.fallback',
        'opentv.tui.terminal',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'pytest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='opentv',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    spec_path.write_text(spec_content, encoding="utf-8")
    return spec_path


def verify_zipapp(archive_path: Path) -> bool:
    """Verifies that the generated zipapp is a valid, readable ZIP containing required modules."""
    if not archive_path.is_file():
        return False
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            namelist = zf.namelist()
            required = ["__main__.py", "opentv/__init__.py", "opentv/cli.py"]
            for req in required:
                if req not in namelist:
                    return False
        return True
    except Exception:
        return False


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OpenTV Standalone Binary Packaging")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("companion"),
        help="Source directory containing opentv package (default: companion)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Output directory for generated binaries (default: dist)",
    )
    parser.add_argument(
        "--zipapp",
        action="store_true",
        default=True,
        help="Build standard executable .zipapp archive",
    )
    parser.add_argument(
        "--pyinstaller-spec",
        action="store_true",
        help="Generate PyInstaller .spec file for single-file native builds",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Build zipapp and generate PyInstaller spec",
    )

    args = parser.parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    do_zipapp = args.zipapp or args.all
    do_spec = args.pyinstaller_spec or args.all

    success = True
    if do_zipapp:
        zipapp_path = output_dir / "opentv.pyz"
        print(f"Building standalone zipapp executable: {zipapp_path}")
        built_path = build_zipapp(args.source, zipapp_path)
        if verify_zipapp(built_path):
            size_kb = built_path.stat().st_size / 1024
            print(f"SUCCESS: Created {built_path} ({size_kb:.1f} KB)")
        else:
            print(f"ERROR: Failed to verify zipapp archive at {built_path}", file=sys.stderr)
            success = False

    if do_spec:
        scripts_dir = Path("scripts")
        spec_path = generate_pyinstaller_spec(scripts_dir, project_root=Path("."))
        print(f"SUCCESS: Generated PyInstaller spec: {spec_path}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
