@echo off
REM OpenTV Automated Rollback Script for Windows CMD
setlocal enabledelayedexpansion

set ADB=adb
set DEV_ARG=-s 192.168.1.100:5555

echo Starting OpenTV emergency rollback...

%ADB% %DEV_ARG% shell pm enable com.sony.dtv.demomode
if %ERRORLEVEL% NEQ 0 (echo Warning: Failed to re-enable com.sony.dtv.demomode)

REM Clear on-device registry
%ADB% %DEV_ARG% shell "rm -f /data/local/tmp/opentv-disabled.txt" >nul 2>&1

echo Rollback completed.
endlocal
