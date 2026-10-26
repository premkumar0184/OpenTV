#!/usr/bin/env bash
# OpenTV Standalone Executable Build Script (Linux & macOS)
# Milestone 5: Standalone Single-File Executables Distribution
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== OpenTV Standalone Packaging Pipeline ==="
echo "Project Root: ${PROJECT_ROOT}"

# 1. Build stdlib zipapp executable
echo "--> Step 1: Building pure Python zipapp (.pyz)..."
python3 "${SCRIPT_DIR}/package_binaries.py" --all --output-dir "${PROJECT_ROOT}/dist"

# 2. Check for PyInstaller to build native single-file binary
if command -v pyinstaller >/dev/null 2>&1; then
    echo "--> Step 2: Compiling native single-file executable with PyInstaller..."
    OS_NAME="$(uname -s | tr '[:upper:]' '[:lower:]')"
    ARCH_NAME="$(uname -m)"
    OUTPUT_BIN="opentv-${OS_NAME}-${ARCH_NAME}"

    pyinstaller --clean --noconfirm "${SCRIPT_DIR}/opentv.spec" --distpath "${PROJECT_ROOT}/dist"
    if [ -f "${PROJECT_ROOT}/dist/opentv" ]; then
        mv "${PROJECT_ROOT}/dist/opentv" "${PROJECT_ROOT}/dist/${OUTPUT_BIN}"
        chmod +x "${PROJECT_ROOT}/dist/${OUTPUT_BIN}"
        echo "SUCCESS: Created native binary at dist/${OUTPUT_BIN}"
    fi
else
    echo "Note: PyInstaller not detected. Standard zipapp built at dist/opentv.pyz"
    echo "Install PyInstaller via 'pip install pyinstaller' to compile native ELF/Mach-O binaries."
fi

echo "=== Standalone Packaging Complete ==="
