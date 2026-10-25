"""
OpenTV Rollback Engine: Standalone Script Generator.
PROJECT.md Feature F3.7 / Contract 3:
Generates zero-dependency standalone recovery scripts:
- rollback.sh  (Linux / macOS POSIX shell)
- rollback.bat (Windows CMD batch script with CRLF line endings)
- rollback.ps1 (Windows PowerShell script with CmdletBinding and parameter overrides)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Union

LAUNCHERX_PKG = "com.google.android.apps.tv.launcherx"
LAUNCHERX_LISTENER_SVC = (
    "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
)
DEVICE_REGISTRY_PATH = "/data/local/tmp/opentv-disabled.txt"


class RollbackEngine:
    """Generates standalone multi-platform recovery scripts for restoring disabled packages."""

    def __init__(self) -> None:
        pass

    def generate_sh(self, packages: Iterable[str], target_device: str = "") -> str:
        """
        Generate standalone POSIX shell rollback script for Linux and macOS.
        Enforces `set -e`, quotes device path to prevent Git Bash expansion,
        and re-enables Google TV notification listener if launcherx was disabled.
        """
        target_device = (target_device or "").strip()
        dev_flag = f"-s {target_device} " if target_device else ""
        dev_arg = dev_flag.strip()

        pkg_list = list(packages)

        lines: List[str] = [
            "#!/bin/sh",
            "# OpenTV Automated Rollback Script for Linux and macOS",
            "# Restores disabled packages and system permissions",
            "set -e",
            "",
            'ADB="${ADB:-adb}"',
            f'TARGET="{target_device}"',
            f'DEV_ARG="{dev_arg}"',
            "",
            "echo 'Starting OpenTV emergency rollback...'",
            "",
            "# Restore disabled packages",
        ]

        for pkg in pkg_list:
            clean_pkg = pkg.strip()
            if clean_pkg:
                lines.append(f'$ADB $DEV_ARG shell pm enable "{clean_pkg}"')

        if LAUNCHERX_PKG in pkg_list:
            lines.extend([
                "",
                "# Restore Google TV Notification Listener Service privilege",
                f'$ADB $DEV_ARG shell cmd notification allow_listener "{LAUNCHERX_LISTENER_SVC}"',
            ])

        lines.extend([
            "",
            "# Clear on-device registry if accessible",
            f'$ADB $DEV_ARG shell "rm -f {DEVICE_REGISTRY_PATH}" 2>/dev/null || true',
            "",
            "echo 'Rollback completed successfully. All modified packages re-enabled.'",
        ])

        return "\n".join(lines) + "\n"

    def generate_bat(self, packages: Iterable[str], target_device: str = "") -> str:
        """
        Generate standalone Windows CMD batch script.
        Strictly uses CRLF (\\r\\n) line endings, `setlocal enabledelayedexpansion`,
        and %ERRORLEVEL% validation.
        """
        target_device = (target_device or "").strip()
        dev_flag = f"-s {target_device} " if target_device else ""
        dev_arg = dev_flag.strip()

        pkg_list = list(packages)

        lines: List[str] = [
            "@echo off",
            "REM OpenTV Automated Rollback Script for Windows CMD",
            "setlocal enabledelayedexpansion",
            "",
            "set ADB=adb",
            f"set DEV_ARG={dev_arg}",
            "",
            "echo Starting OpenTV emergency rollback...",
            "",
        ]

        for pkg in pkg_list:
            clean_pkg = pkg.strip()
            if clean_pkg:
                lines.append(f"%ADB% %DEV_ARG% shell pm enable {clean_pkg}")
                lines.append(f"if %ERRORLEVEL% NEQ 0 (echo Warning: Failed to re-enable {clean_pkg})")

        if LAUNCHERX_PKG in pkg_list:
            lines.extend([
                "",
                "REM Restore Google TV Notification Listener",
                f"%ADB% %DEV_ARG% shell cmd notification allow_listener {LAUNCHERX_LISTENER_SVC}",
            ])

        lines.extend([
            "",
            "REM Clear on-device registry",
            f'%ADB% %DEV_ARG% shell "rm -f {DEVICE_REGISTRY_PATH}" >nul 2>&1',
            "",
            "echo Rollback completed.",
            "endlocal",
        ])

        return "\r\n".join(lines) + "\r\n"

    def generate_ps1(self, packages: Iterable[str], target_device: str = "") -> str:
        """
        Generate standalone Windows PowerShell script.
        Includes [CmdletBinding()], parameter override for target TV address,
        and structured output.
        """
        target_device = (target_device or "").strip()
        pkg_list = list(packages)
        pkg_list_str = ", ".join([f'"{p.strip()}"' for p in pkg_list if p.strip()])
        dev_flag = f"-s {target_device} " if target_device else ""

        lines: List[str] = [
            "# OpenTV Automated Rollback Script for Windows PowerShell",
            "[CmdletBinding()]",
            f'param([string]$Target = "{target_device}")',
            "$ErrorActionPreference = 'Continue'",
            "",
            "$devArgs = if ($Target) { \"-s $Target \" } else { \"\" }",
            "",
            "Write-Host 'Starting OpenTV emergency rollback...' -ForegroundColor Cyan",
            f"$packages = @({pkg_list_str})",
            "",
            "foreach ($pkg in $packages) {",
            f'    $cmd = "adb {dev_flag}shell pm enable $pkg"',
            '    Write-Host "Re-enabling $pkg..."',
            "    Invoke-Expression $cmd",
            "}",
        ]

        if LAUNCHERX_PKG in pkg_list:
            lines.extend([
                "",
                "# Restore Notification Listener",
                f'adb {dev_flag}shell cmd notification allow_listener "{LAUNCHERX_LISTENER_SVC}"',
            ])

        lines.extend([
            "",
            "# Clear on-device registry",
            f'adb {dev_flag}shell "rm -f {DEVICE_REGISTRY_PATH}" 2>$null',
            "",
            "Write-Host 'Rollback finished.' -ForegroundColor Green",
        ])

        return "\n".join(lines) + "\n"

    def write_rollback_scripts(
        self,
        arg1: Union[Iterable[str], str, Path],
        arg2: Union[Iterable[str], str, Path],
        target_device: str = "",
    ) -> Dict[str, str]:
        """
        Atomically write rollback.sh, rollback.bat, and rollback.ps1.
        Polymorphic signature supports both:
          write_rollback_scripts(packages, target_dir, target_device="")
          write_rollback_scripts(output_dir, packages, target_device="")
        """
        if isinstance(arg1, (list, tuple, set)):
            packages = list(arg1)
            output_dir = Path(arg2)
        else:
            output_dir = Path(arg1)
            packages = list(arg2)

        output_dir.mkdir(parents=True, exist_ok=True)

        sh_path = output_dir / "rollback.sh"
        bat_path = output_dir / "rollback.bat"
        ps1_path = output_dir / "rollback.ps1"

        # Generate script contents
        sh_content = self.generate_sh(packages, target_device=target_device)
        bat_content = self.generate_bat(packages, target_device=target_device)
        ps1_content = self.generate_ps1(packages, target_device=target_device)

        # Atomic write helper
        def _atomic_write(dest_path: Path, content: str, mode: int | None = None) -> None:
            tmp_path = dest_path.with_suffix(dest_path.suffix + f".tmp.{os.getpid()}")
            try:
                tmp_path.write_text(content, encoding="utf-8")
                if mode is not None:
                    os.chmod(tmp_path, mode)
                os.replace(tmp_path, dest_path)
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()
                raise

        # Write all three scripts atomically
        _atomic_write(sh_path, sh_content, mode=0o755)
        _atomic_write(bat_path, bat_content)
        _atomic_write(ps1_path, ps1_content)

        return {
            "sh": str(sh_path),
            "bat": str(bat_path),
            "ps1": str(ps1_path),
        }
