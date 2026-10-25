"""
Canonical Rollback Generator according to PROJECT.md Feature F3.7.
Generates standalone zero-dependency scripts: rollback.sh (Linux/macOS), rollback.bat (Windows CMD), and rollback.ps1 (PowerShell).
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict

class RollbackEngine:
    def __init__(self):
        pass

    def generate_sh(self, packages: List[str], target_device: str = "") -> str:
        dev_flag = f"-s {target_device} " if target_device else ""
        lines = [
            "#!/bin/sh",
            "# OpenTV Automated Rollback Script for Linux and macOS",
            "# Restores disabled packages and system permissions",
            "set -e",
            "",
            'ADB="${ADB:-adb}"',
            f'TARGET="{target_device}"',
            f'DEV_ARG="{dev_flag.strip()}"',
            "",
            "echo 'Starting OpenTV emergency rollback...'",
            "",
            "# Restore disabled packages",
        ]
        for pkg in packages:
            lines.append(f'$ADB $DEV_ARG shell pm enable "{pkg}"')

        if "com.google.android.apps.tv.launcherx" in packages:
            lines.append("")
            lines.append("# Restore Google TV Notification Listener Service privilege")
            lines.append(
                '$ADB $DEV_ARG shell cmd notification allow_listener '
                '"com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"'
            )

        lines.extend([
            "",
            "# Clear on-device registry if accessible",
            '$ADB $DEV_ARG shell "rm -f /data/local/tmp/opentv-disabled.txt" 2>/dev/null || true',
            "",
            "echo 'Rollback completed successfully. All modified packages re-enabled.'",
        ])
        return "\n".join(lines) + "\n"

    def generate_bat(self, packages: List[str], target_device: str = "") -> str:
        dev_flag = f"-s {target_device} " if target_device else ""
        lines = [
            "@echo off",
            "REM OpenTV Automated Rollback Script for Windows CMD",
            "setlocal enabledelayedexpansion",
            "",
            "set ADB=adb",
            f"set DEV_ARG={dev_flag.strip()}",
            "",
            "echo Starting OpenTV emergency rollback...",
            "",
        ]
        for pkg in packages:
            lines.append(f"%ADB% %DEV_ARG% shell pm enable {pkg}")
            lines.append("if %ERRORLEVEL% NEQ 0 (echo Warning: Failed to re-enable " + pkg + ")")

        if "com.google.android.apps.tv.launcherx" in packages:
            lines.append("")
            lines.append("REM Restore Google TV Notification Listener")
            lines.append(
                "%ADB% %DEV_ARG% shell cmd notification allow_listener "
                "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
            )

        lines.extend([
            "",
            "echo Rollback completed.",
            "endlocal",
        ])
        return "\r\n".join(lines) + "\r\n"

    def generate_ps1(self, packages: List[str], target_device: str = "") -> str:
        dev_flag = f"-s {target_device} " if target_device else ""
        pkg_list_str = ", ".join([f'"{p}"' for p in packages])
        lines = [
            "# OpenTV Automated Rollback Script for Windows PowerShell",
            f'param([string]$Target = "{target_device}")',
            "$ErrorActionPreference = 'Continue'",
            "",
            "Write-Host 'Starting OpenTV emergency rollback...' -ForegroundColor Cyan",
            f"$packages = @({pkg_list_str})",
            "",
            "foreach ($pkg in $packages) {",
            f'    $cmd = "adb {dev_flag}shell pm enable $pkg"',
            "    Write-Host \"Re-enabling $pkg...\"",
            "    Invoke-Expression $cmd",
            "}",
        ]
        if "com.google.android.apps.tv.launcherx" in packages:
            lines.extend([
                "",
                "# Restore Notification Listener",
                f'adb {dev_flag}shell cmd notification allow_listener "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"',
            ])

        lines.extend([
            "",
            "Write-Host 'Rollback finished.' -ForegroundColor Green",
        ])
        return "\n".join(lines) + "\n"

    def write_rollback_scripts(self, output_dir: str | Path, packages: List[str], target_device: str = "") -> Dict[str, str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        sh_path = out / "rollback.sh"
        bat_path = out / "rollback.bat"
        ps1_path = out / "rollback.ps1"

        sh_path.write_text(self.generate_sh(packages, target_device), encoding="utf-8")
        sh_path.chmod(0o755)

        bat_path.write_text(self.generate_bat(packages, target_device), encoding="utf-8")
        ps1_path.write_text(self.generate_ps1(packages, target_device), encoding="utf-8")

        return {
            "sh": str(sh_path),
            "bat": str(bat_path),
            "ps1": str(ps1_path),
        }
