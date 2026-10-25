# OpenTV Automated Rollback Script for Windows PowerShell
[CmdletBinding()]
param([string]$Target = "192.168.1.100:5555")
$ErrorActionPreference = 'Continue'

$devArgs = if ($Target) { "-s $Target " } else { "" }

Write-Host 'Starting OpenTV emergency rollback...' -ForegroundColor Cyan
$packages = @("com.sony.dtv.demomode")

foreach ($pkg in $packages) {
    $cmd = "adb -s 192.168.1.100:5555 shell pm enable $pkg"
    Write-Host "Re-enabling $pkg..."
    Invoke-Expression $cmd
}

# Clear on-device registry
adb -s 192.168.1.100:5555 shell "rm -f /data/local/tmp/opentv-disabled.txt" 2>$null

Write-Host 'Rollback finished.' -ForegroundColor Green
