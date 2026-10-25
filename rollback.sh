#!/bin/sh
# OpenTV Automated Rollback Script for Linux and macOS
# Restores disabled packages and system permissions
set -e

ADB="${ADB:-adb}"
TARGET="192.168.1.100:5555"
DEV_ARG="-s 192.168.1.100:5555"

echo 'Starting OpenTV emergency rollback...'

# Restore disabled packages
$ADB $DEV_ARG shell pm enable "com.sony.dtv.demomode"

# Clear on-device registry if accessible
$ADB $DEV_ARG shell "rm -f /data/local/tmp/opentv-disabled.txt" 2>/dev/null || true

echo 'Rollback completed successfully. All modified packages re-enabled.'
