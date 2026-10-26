@echo off
REM OpenTV Standalone Executable Build Script (Windows)
REM Milestone 5: Standalone Single-File Executables Distribution

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

echo === OpenTV Standalone Packaging Pipeline (Windows) ===

REM 1. Build stdlib zipapp executable
echo --^> Step 1: Building pure Python zipapp (.pyz)...
python "%SCRIPT_DIR%package_binaries.py" --all --output-dir "%PROJECT_ROOT%\dist"

REM 2. Check for PyInstaller to build native single-file .exe
where pyinstaller >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo --^> Step 2: Compiling native single-file Windows executable with PyInstaller...
    pyinstaller --clean --noconfirm "%SCRIPT_DIR%opentv.spec" --distpath "%PROJECT_ROOT%\dist"
    if exist "%PROJECT_ROOT%\dist\opentv.exe" (
        copy /Y "%PROJECT_ROOT%\dist\opentv.exe" "%PROJECT_ROOT%\dist\opentv-windows-x64.exe" >nul
        echo SUCCESS: Created native binary at dist\opentv-windows-x64.exe
    )
) else (
    echo Note: PyInstaller not detected. Standard zipapp built at dist\opentv.pyz
    echo Install PyInstaller via 'pip install pyinstaller' to compile native .exe binaries.
)

echo === Standalone Packaging Complete ===
