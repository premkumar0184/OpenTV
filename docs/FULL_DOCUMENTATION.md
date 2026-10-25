# OpenTV: High-Performance, Privacy-First Android TV Launcher & Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-yellow.svg)](https://www.python.org/)
[![Android TV: 5.0+](https://img.shields.io/badge/Android%20TV-API%2021--35-green.svg)](https://developer.android.com/tv)
[![APK Size: ~49 KB](https://img.shields.io/badge/APK%20Size-49%20KB-success.svg)](app/build.sh)
[![Tests: 97 Passing](https://img.shields.io/badge/Tests-97%20Passing-brightgreen.svg)](tests/)
[![Dependencies: 0 Pip](https://img.shields.io/badge/Dependencies-0%20Pip-orange.svg)](companion/opentv/)

OpenTV is an open-source, ultra-lightweight Android TV and Google TV launcher and cross-platform companion administration toolkit. It delivers a distraction-free smart TV experience with **zero advertisements**, **zero tracking telemetry**, **zero remote cloud dependencies**, and **zero proprietary AI services**.

The project consists of two tightly integrated components:
1. **The OpenTV Launcher (`app/`)**: A native Android TV Home application written in pure Java against Android SDK framework APIs (API level 21 through 35+). It features a high-performance 6-column application grid, physical remote D-pad spatial navigation, TV remote tile reordering, physical HDMI input discovery, hardware-level OLED burn-in protection, and dynamic multi-path configuration loading—all within a release APK footprint under **50 KB**.
2. **The OpenTV Companion Manager (`companion/opentv/`)**: A cross-platform CLI and terminal user interface (TUI) running on **Linux**, **macOS**, and **Windows**. Developed strictly using the **Python 3.9+ standard library** (requiring **0 pip dependencies**), it manages wireless and USB debugging, automates device profile detection, configures the launcher layout, and executes safe debloating with a 10-layer guardrails engine and 100% reversible rollback recovery.

---

## Table of Contents

1. [Project Overview & Philosophy](#1-project-overview--philosophy)
2. [Architecture & Project Layout](#2-architecture--project-layout)
3. [Quickstart & Setup](#3-quickstart--setup)
4. [Wireless Debugging & Pairing Guide](#4-wireless-debugging--pairing-guide)
5. [Interactive Terminal UI (TUI) Manual](#5-interactive-terminal-ui-tui-manual)
6. [CLI Subcommands Reference](#6-cli-subcommands-reference)
7. [Manufacturer & Model Profiles](#7-manufacturer--model-profiles)
8. [Debloat Safety Manual & 10-Layer Guardrails](#8-debloat-safety-manual--10-layer-guardrails)
9. [100% Reversible Rollback Engine](#9-100-reversible-rollback-engine)
10. [Reproducible Build Guide](#10-reproducible-build-guide)
11. [Verification & Testing Guide](#11-verification--testing-guide)

---

## 1. Project Overview & Philosophy

Modern smart TV operating systems have evolved from neutral media portals into intrusive advertising platforms. Modern default TV launchers consume hundreds of megabytes of RAM running recommendation engines, sponsored banner carousels, unskippable full-screen video previews, background content scrapers, and analytics beacons.

OpenTV is engineered around an uncompromising set of architectural principles:

| Core Tenet | OpenTV Implementation | Commercial Smart TV Launchers |
| :--- | :--- | :--- |
| **Advertisements** | **Zero ads**. Absolutely no sponsored rows, promotional banners, or suggested apps. | 50% to 75% of home screen real estate dedicated to sponsored content. |
| **Telemetry & Privacy** | **Zero tracking**. No analytics SDKs, crash beacons, or outbound HTTP telemetry. | Continuous monitoring of app launches, viewing habits, and network telemetry. |
| **Cloud & AI Independence** | **100% Local Execution**. Operates without cloud accounts, remote APIs, or AI feeds. | Dependent on proprietary cloud recommendation services and remote profiles. |
| **Host Dependencies** | **100% Python Standard Library**. Requires **zero pip packages** on host machines. | Requires complex runtime environments, node/npm tooling, or heavy toolchains. |
| **APK Binary Footprint** | **~49 KB** release package. Achieved via procedural bytecode icons and zero bloat. | 25 MB to 120 MB packages bloated with heavy libraries and raster graphics. |
| **Runtime Memory Overhead** | **< 15 MB RAM usage**. Smooth 60 FPS performance on 1 GB RAM dongles and TV sticks. | 150 MB to 450 MB background RAM usage causing UI stutter and app eviction. |
| **Display Panel Longevity** | **Integrated OLED Burn-In Protection**: `#000000` black, 180s screensaver, orbital pixel shift. | Static, high-contrast, high-luminance UI elements that accelerate OLED burn-in. |
| **Remote Navigation** | **Strict Remote D-Pad Navigation**: 100% spatial navigation with anti-bounce protection. | Hybrid pointer/touch-first UI paradigms resulting in lost focus bugs. |
| **Reversibility Guarantee** | **100% Reversible Debloating**: Standalone `.sh`, `.bat`, `.ps1` recovery scripts generated. | One-way debloat scripts that risk bricking remotes, IMEs, or setup wizards. |

---

## 2. Architecture & Project Layout

The repository is organized into three distinct primary modules: the Android TV native launcher application, the cross-platform Python companion manager, and the comprehensive verification test suite, accompanied by global project specifications and documentation.

```
OpenTV/
├── app/                                    # R1: Android TV Launcher Application
│   ├── src/main/AndroidManifest.xml        # Leanback/Home intent filters, permissions, <queries>
│   ├── src/main/java/org/opentv/launcher/
│   │   ├── MainActivity.java               # Home activity, 6-col grid math, dynamic scaling
│   │   ├── FocusController.java            # D-pad spatial engine, Bug #30 anti-bounce, Move Mode
│   │   ├── TvInputHelper.java              # TvInputManager query, 5-tier HDMI fallback chain
│   │   ├── VendorAdapter.java              # Hardware hooks (TCL ShowWindow, Sony, Philips)
│   │   ├── OledProtectionService.java      # 180s screensaver, 60s orbital pixel shift, pure black
│   │   ├── ConfigManager.java              # Dual-path JSON configuration & anti-replay parser
│   │   ├── ConfigReloadReceiver.java       # BroadcastReceiver for live 'RELOAD_CONFIG'
│   │   ├── LineIcon.java                   # Procedural vector line icon interpreter (zero rasters)
│   │   └── Strings.java                    # Embedded 17-language dictionary (zero XML resources)
│   ├── src/test/java/org/opentv/launcher/
│   │   ├── LauncherUnitTest.java           # Android unit tests (25 assertions)
│   │   └── AdversarialMoveModeTest.java    # Focus rollback and boundary verification
│   ├── build.gradle                        # AGP 9.x compatible Gradle build script
│   └── build.sh                            # Standalone zero-Gradle reproducible build script
│
├── companion/                              # R2 & R3: Cross-Platform Companion Manager
│   └── opentv/                             # Pure Python 3.9+ package (0 external dependencies)
│       ├── __init__.py                     # Package metadata (v1.0.0)
│       ├── __main__.py                     # CLI entrypoint: python3 -m opentv
│       ├── cli.py                          # Subcommand parser (8 subcommands, flexible flags)
│       ├── core/                           # Core Host Administration Layer
│       │   ├── adb.py                      # Typed AdbClient, IP validation, subprocess wrapper
│       │   ├── device.py                   # DeviceManager, getprop extractor, USB priority engine
│       │   ├── config.py                   # LauncherConfig schema, dataclasses, JSON serializer
│       │   └── deployer.py                 # APK installer, dual-path config pusher, Home verifier
│       ├── debloat/                        # Debloat & Safety Subsystem
│       │   ├── database.py                 # 4-tier safety catalog (NEVER, KEEP, SAFE, REVIEW)
│       │   ├── guardrails.py               # 10-layer guardrails engine (PERSISTENT, IME, launcherx)
│       │   ├── rollback.py                 # Standalone recovery generators (.sh, .bat, .ps1)
│       │   └── audit.py                    # Real-time dual audit logging (audit_log.json & .txt)
│       ├── profiles/                       # Manufacturer & Model Profiles
│       │   ├── __init__.py                 # Profile exports
│       │   └── detector.py                 # BrandProfile, IntentDefinition, 8 profiles & detector
│       └── tui/                            # Terminal User Interface
│           ├── terminal.py                 # ANSI VT100 control sequences & raw mode abstraction
│           ├── fallback.py                 # FallbackLineEngine (0 ANSI escapes for CI / non-TTY)
│           └── app.py                      # Interactive TUI dashboard, RawTerminalEngine & 6-screen workflow
│
├── tests/                                  # R4: Automated Verification Harness
│   ├── run_tests.py                        # Unified E2E test runner (Tiers 1-4, 79 tests)
│   ├── adapter.py                          # Contract adapter bridging live companion & spec oracle
│   ├── test_tier1_feature_coverage.py      # Tier 1: Core Feature Coverage (35 tests)
│   ├── test_tier2_boundary_cases.py        # Tier 2: Boundary & Corner Cases (32 tests)
│   ├── test_tier3_combinations.py          # Tier 3: Cross-Feature Combinations (7 tests)
│   ├── test_tier4_scenarios.py             # Tier 4: Real-World Scenarios (5 tests)
│   ├── test_launcher_adversarial.py        # Adversarial launcher focus & scaling tests (18 tests)
│   ├── VerifyLauncherLogic.java            # Standalone Java test assertions
│   └── mocks/                              # In-memory ADB subprocess emulator
│       └── mock_adb.py
│
├── PROJECT.md                              # Global project index, feature inventory & milestones
└── README.md                               # Authoritative user manual and developer documentation
```

### Component Contracts & Responsibilities

1. **Launcher APK (`app/`)**:
   - Compiles down to a minimal binary (<50 KB) with zero third-party Java libraries.
   - Listens for `action.MAIN`, `category.HOME` to act as the primary Android TV desktop.
   - Manages an adaptive 6-column grid that automatically scales layout dimensions proportionally for 720p HD, 1080p Full HD, and 3840x2160 4K UHD panels.
   - Handles remote navigation via `FocusController`, preventing double-click execution bugs and providing a defensive in-memory snapshot for 100% reversible tile reordering.
   - Guards OLED displays against burn-in through pure black UI tokens, a 180s idle screensaver/dimmer, and an orbital subpixel micro-drift service running every 60s.
2. **Companion Manager (`companion/opentv/`)**:
   - Zero pip dependencies: written 100% in Python 3.9+ standard library.
   - Detects connected devices over USB and Wi-Fi, automatically prioritizing physical USB connections over network ADB serials.
   - Automatically probes device properties via `getprop` to load tailored manufacturer profiles (Sony, TCL, Philips, Hisense, Xiaomi, CCwGTV, Nvidia Shield, or Generic).
   - Enforces a 10-layer guardrails engine before disabling any application, rejecting attempts to disable critical input methods, Bluetooth remote controllers, or system launchers without an alternative.
   - Generates standalone, zero-dependency recovery scripts (`rollback.sh`, `rollback.bat`, `rollback.ps1`) and maintains an on-device registry at `/data/local/tmp/opentv-disabled.txt` for host-independent recovery.
3. **Verification Harness (`tests/`)**:
   - Zero external testing dependencies: runs entirely on Python's built-in `unittest` framework.
   - Comprehensive multi-tier coverage: 79 E2E tests across 4 tiers + 18 adversarial tests (97 tests total under test discovery).
   - Subprocess mock virtualization for rapid, deterministic testing (<0.05 seconds runtime).

---

## 3. Quickstart & Setup

### Prerequisites

1. **Python 3.9 or newer**:
   - Linux: Pre-installed or available via `sudo apt install python3` / `sudo dnf install python3`.
   - macOS: Pre-installed or available via `brew install python`.
   - Windows: Install from [python.org](https://www.python.org/) or Microsoft Store (ensure "Add Python to PATH" is checked).
2. **Android Debug Bridge (`adb`)**:
   - Linux: `sudo apt install adb` (Debian/Ubuntu) or `sudo dnf install android-tools` (Fedora).
   - macOS: `brew install android-platform-tools`.
   - Windows: `winget install Google.PlatformTools` or download the standalone SDK Platform-Tools zip and add it to your System PATH.
   - Verify installation:
     ```bash
     adb version
     ```

### 1. Clone the Repository

```bash
git clone https://github.com/YourRepo/OpenTV.git
cd OpenTV
```

### 2. Direct Invocation (No Installation Required)

OpenTV runs directly out of the repository directory without running `pip install`:

- **Linux & macOS**:
  ```bash
  PYTHONPATH=companion python3 -m opentv --help
  ```
- **Windows (PowerShell)**:
  ```powershell
  $env:PYTHONPATH="companion"; python -m opentv --help
  ```
- **Windows (Command Prompt)**:
  ```cmd
  set PYTHONPATH=companion && python -m opentv --help
  ```

### 3. Setting Up a Global Alias or Wrapper

To run `opentv` from any directory on your system:

#### Linux & macOS (Bash / Zsh)
Add the following alias to `~/.bashrc` or `~/.zshrc`:
```bash
alias opentv="PYTHONPATH=/path/to/OpenTV/companion python3 -m opentv"
```

Or install an executable wrapper script to your user bin directory:
```bash
cat << 'EOF' > ~/.local/bin/opentv
#!/bin/sh
REPO_PATH="/path/to/OpenTV"
export PYTHONPATH="$REPO_PATH/companion:$PYTHONPATH"
exec python3 -m opentv "$@"
EOF
chmod +x ~/.local/bin/opentv
```

#### Windows (PowerShell Profile)
Add this function to your PowerShell `$PROFILE`:
```powershell
function opentv {
    $env:PYTHONPATH = "C:\path\to\OpenTV\companion;$env:PYTHONPATH"
    python -m opentv @args
}
```

#### Windows (Command Prompt Batch Wrapper)
Create `opentv.bat` in a folder included in your system `PATH` (e.g. `C:\Users\<Username>\bin\opentv.bat`):
```batch
@echo off
setlocal
set "OPENTV_DIR=C:\path\to\OpenTV"
set "PYTHONPATH=%OPENTV_DIR%\companion;%PYTHONPATH%"
python -m opentv %*
endlocal
```

### 4. 60-Second Quickstart Workflow

```bash
# 1. Connect to your TV over Wi-Fi
opentv connect 192.168.1.50

# 2. Deploy the OpenTV launcher and set as default Home screen
opentv deploy --apk app-release.apk --set-home

# 3. Preview confirmed safe debloat candidates without modifying anything
opentv debloat --safe-only --dry-run

# 4. Disable confirmed vendor bloatware and generate recovery scripts
opentv debloat --safe-only --output-dir ./recovery

# 5. Launch the interactive TUI dashboard to customize visible apps & HDMI inputs
opentv tui
```

---

## 4. Wireless Debugging & Pairing Guide

OpenTV communicates with your Android TV or Google TV using the Android Debug Bridge (ADB). You can connect over standard Wi-Fi, Ethernet, or a direct USB cable.

### Enabling Developer Options on Your TV

Before connecting, enable Developer Options and Debugging on your TV:

```
+-----------------------------------------------------------------------------+
|                                TV SETTINGS                                  |
|                                                                             |
|  [ Settings ] -> [ System / Device Preferences ] -> [ About ]              |
|                                                                             |
|      1. Highlight "Android TV OS Build" (or "Build Number")                 |
|      2. Click Remote OK / Center Button 7 times                             |
|         ==> Toast appears: "You are now a developer!"                       |
|                                                                             |
|  [ Developer Options ]                                                      |
|      [*] USB Debugging         --> [ Enabled ]                              |
|      [*] Wireless Debugging    --> [ Enabled ] (Android 11+ / Google TV)     |
+-----------------------------------------------------------------------------+
```

1. Navigate to **Settings** (gear icon) -> **System** (Google TV) or **Device Preferences** (Android TV) -> **About**.
2. Scroll to **Android TV OS Build** (or **Build Number**).
3. Press the **OK / Center** button on your remote **7 times** until the toast message appears: *"You are now a developer!"*.
4. Return to the previous menu and select **Developer options**.
5. Toggle **USB debugging** to **ON**.
6. On Android 11+ (API 30+) devices (including Chromecast with Google TV), also toggle **Wireless debugging** to **ON**.

---

### Android 11+ Wi-Fi Pairing (`adb pair`)

Android 11+ requires a one-time TLS pairing handshake using an ephemeral port and a 6-digit numeric pairing code before accepting network connections.

#### Step 1: Open the Pairing Dialog on the TV
In **Settings** -> **Developer options** -> **Wireless debugging**, select **Pair device with pairing code**.
The TV will display a dialog with:
- **Wi-Fi pairing code**: A 6-digit number (e.g. `482910`).
- **IP address & Port**: An IP with an **ephemeral pairing port** (e.g. `192.168.1.50:38450`).

> **CRITICAL ARCHITECTURAL DISTINCTION: Ephemeral Pairing Port vs Connection Port**  
> The port shown in the pairing modal (e.g. `38450`) is dynamically generated by Android strictly for the one-time TLS pairing handshake. **Do not attempt to connect to this port later.**  
> The steady-state ADB daemon listens on persistent port **`5555`** (or the port displayed on the main Wireless Debugging screen).

#### Step 2: Run the Pairing Command
Run `opentv pair` with the pairing IP:port and the 6-digit code:
```bash
opentv pair 192.168.1.50:38450 482910
```
*Expected Output:*
```text
Successfully paired to 192.168.1.50:38450
You can now connect via: opentv connect 192.168.1.50:5555
```

#### Step 3: Establish the Persistent Connection
Connect to the device's persistent ADB port (`5555`):
```bash
opentv connect 192.168.1.50:5555
```
*Expected Output:*
```text
Successfully connected to 192.168.1.50:5555
```

---

### Standard Wireless Connection (Android 9 & 10)

Older Android TV models (Android 9.0 Pie and 10.0 Q) do not use TLS pairing:
1. Connect the TV to your computer once using a USB cable.
2. Enable TCP/IP mode on port 5555:
   ```bash
   adb tcpip 5555
   ```
3. Disconnect the USB cable.
4. Connect wirelessly:
   ```bash
   opentv connect 192.168.1.50
   ```
*(Port 5555 is assumed automatically when omitted).*

---

### USB Connection & Target Auto-Detection Priority

If your computer is connected directly to the TV via USB (or when developing against a local Android TV emulator or development board):
1. Connect a USB cable from your computer to the TV's OTG / service USB port.
2. An authorization dialog will appear on the TV screen: *"Allow USB debugging?"*.
3. Check **Always allow from this computer** and select **OK**.

#### Deterministic Target Resolution Hierarchy

OpenTV resolves device targets according to a strict priority hierarchy (`companion/opentv/core/device.py`):

```
Target Resolution Flow:
1. CLI Flag (-t / --target)                --> Explicit serial / IP always wins
2. Environment Variable ($OPENTV_TARGET)   --> Used if flag is absent
3. Single Online Device Auto-Detection     --> Selected automatically if count == 1
4. USB Priority Over Wi-Fi                 --> If multiple devices exist, physical USB
                                               serials (no colon) override network serials
5. Ambiguity Shield                        --> Multiple USB or multiple Wi-Fi devices
                                               halt with Exit Code 2/3 and display device list
```

- **Physical USB Priority**: In multi-device setups (for example, a wireless TV and a USB testing dongle simultaneously connected), OpenTV automatically prioritizes the physical USB hardware.
- **Ambiguity Shield**: If multiple conflicting devices are connected without a clear priority, OpenTV safely halts with exit code `2` or `3` and prints all detected serials, preventing accidental execution against the wrong device.

---

## 5. Interactive Terminal UI (TUI) Manual

OpenTV features an interactive terminal interface designed for intuitive, keyboard-driven navigation from your computer.

### Dual-Mode Architecture

The TUI incorporates a dual-mode presentation architecture:

```
                       ┌───────────────────────────────┐
                       │      opentv tui launcher      │
                       └───────────────┬───────────────┘
                                       │
                     Is stdin & stdout an interactive TTY?
                                      / \
                                     /   \
                             YES    /     \   NO / --fallback
                                   ▼       ▼
┌────────────────────────────────────┐   ┌────────────────────────────────────┐
│     Interactive ANSI Dashboard     │   │         FallbackLineEngine         │
│                                    │   │                                    │
│ - ANSI VT100 Escape Sequences      │   │ - 0 ANSI Escapes Emitted           │
│ - Raw Keyboard Mode (termios/msvcrt│   │ - Standard stdin.readline()        │
│ - Dynamic Screen Updates           │   │ - Numbered Choice Menus            │
│ - Real-Time 6-Col Grid Rendering   │   │ - Safe for CI & Headless Scripts   │
└────────────────────────────────────┘   └────────────────────────────────────┘
```

1. **Interactive ANSI VT100 Engine (`RawTerminalEngine`)**:
   - Activates automatically when running inside an interactive terminal emulator (macOS Terminal, Linux Bash/Zsh, Windows Terminal, PowerShell, CMD).
   - Utilizes ANSI VT100 sequences: clears screen (`\033[2J\033[H`), inverts selection bars (`\033[7m`), renders bold typography (`\033[1m`), and hides the cursor (`\033[?25l`).
   - Captures single keystrokes instantly using POSIX `termios`/`tty` on Unix and `msvcrt` on Windows (no `Enter` required).
2. **Fallback Line Engine (`FallbackLineEngine`)**:
   - Activates automatically in non-interactive environments (CI runners, redirected streams, dumb terminals `TERM=dumb`) or when `--fallback` is explicitly provided.
   - **Zero ANSI Emission**: Emits **0 ANSI escape characters**, producing clean plain-text output.
   - **Deterministic Numbered Prompts**: Uses standard line-oriented inputs (`prompt_choice`, `prompt_multiselect`) for reliable scriptability.

---

### Live 6-Column ASCII TV Grid Preview

The Layout Manager renders a real-time ASCII preview that reflects the exact 6-column geometry of the OpenTV launcher on your TV:

```text
+------------------+------------------+------------------+------------------+------------------+------------------+
| 1. YouTube       | 2. Netflix       | 3. Plex          | 4. SmartTube     | 5. Kodi          | 6. Prime Video   |
+------------------+------------------+------------------+------------------+------------------+------------------+
| 7. Twitch        | 8. Spotify       | [Empty]          | [Empty]          | [Empty]          | [Empty]          |
+------------------+------------------+------------------+------------------+------------------+------------------+
```

- **16-Character Column Budget**: Application package IDs are automatically resolved to clean, human-readable titles (e.g. `com.google.android.youtube.tv` renders as `YouTube`).
- **Slot Indexing**: Numbers indicate the precise D-pad traversal order from top-left (tile 1) to bottom-right.
- **Empty Slot Indicators**: Unused positions are clearly identified as `[Empty]`, showing remaining capacity before a new row is created.

---

### Walkthrough of the 6 TUI Screens

#### Screen 1: Main Menu & Dashboard
The entry point provides an at-a-glance status overview of the connected TV, active brand profile, OLED protection status, and debloat status.

```text
================================================================================
                        OpenTV Companion Manager v1.0.0                         
================================================================================
  Target Device:  192.168.1.50:5555
  Brand Profile:  Sony Bravia TV (OLED Protection: Enabled)
  Visible Apps:   6 apps | HDMI Ports: 2 ports
  Debloat Status: 14 package(s) disabled on device
--------------------------------------------------------------------------------
  Main Menu Options:
    [1] Connect Device       - USB auto-detect & Wi-Fi connect / pairing
    [2] Layout Manager       - Select home apps, reorder tiles, 6-col live preview
    [3] Debloat Assistant    - 4-tier package view, safe debloat, rollback scripts
    [4] HDMI Input Manager   - Custom labels and hardware passthrough URIs
    [5] Deploy Launcher      - Push config, install APK, set default Home
    [6] Exit                 - Quit application
--------------------------------------------------------------------------------
  Press [1-6] or corresponding hotkey to enter a workflow, or [Q] to quit: 
```

- **Hotkeys**: Press `1`/`c` (Connect), `2`/`l` (Layout), `3`/`d` (Debloat), `4`/`h` (HDMI), `5`/`p` (Deploy), or `6`/`q`/`Esc` (Exit).

---

#### Screen 2: Connection Wizard
Scans for attached USB devices and guides Wi-Fi pairing and connection.

```text
--- Connection Wizard ---
Discovered 1 attached device(s):
  [1] 192.168.1.50:5555 (BRAVIA 4K VH2)

Options: [C] Connect to IP:5555, [P] Pair Wi-Fi (Android 11+), [B] Back to Menu
Choice: 
```

- **USB Auto-Detect**: Discovered physical devices appear immediately in the list.
- **`C`**: Prompts for device IP and connects on default port `5555`.
- **`P`**: Prompts for pairing `IP:port` and 6-digit code, completes TLS pairing, and immediately establishes connection.

---

#### Screen 3: Home Screen Layout Manager
Select which apps appear on the home screen, adjust tile positions, and preview the resulting grid in real time.

```text
--- Home Screen Layout Manager ---
Live 6-Column TV Grid Preview:
+------------------+------------------+------------------+------------------+------------------+------------------+
| 1. YouTube       | 2. Netflix       | 3. Plex          | 4. SmartTube     | [Empty]          | [Empty]          |
+------------------+------------------+------------------+------------------+------------------+------------------+

App List ([Space] Toggle, [U/+] Move Up, [D/-] Move Down, [B/Esc] Back):
  [X] 1. com.google.android.youtube.tv
> [X] 2. com.netflix.ninja
  [X] 3. com.plexapp.android
  [X] 4. com.teamsmart.videomanager.tv
  [ ] 5. com.amazon.amazonvideo.livingroom
  [ ] 6. com.spotify.tv.android
```

- **`Up` / `Down` Arrow Keys**: Navigate the list of installed applications.
- **`Space`**: Toggle whether the selected application appears on the home screen.
- **`+` / `u` / `U`**: Move the highlighted application earlier in the grid order.
- **`-` / `d` / `D`**: Move the highlighted application later in the grid order.
- **`b` / `Esc`**: Save the layout configuration and return to the Main Menu.

---

#### Screen 4: HDMI Input Manager
Configure physical HDMI ports, assign custom names, and toggle home screen visibility.

```text
--- HDMI Input Manager ---
Configure input titles and visibility on launcher:
> [X] HW5: 'PlayStation 5' 
  [X] HW6: 'Nintendo Switch' 
  [ ] HW7: 'HDMI 3' 

Controls: [Space] Toggle Visibility, [E] Edit Title, [B/Esc] Back
```

- **`Space`**: Toggle whether the HDMI port tile appears in the launcher footer.
- **`e` / `E`**: Rename the port (e.g. change generic `HW5` to `"PlayStation 5"` or `"Apple TV 4K"`).
- **OEM Passthrough**: Automatically resolves vendor passthrough URIs for Sony, TCL, Philips, and generic Android TV hardware.

---

#### Screen 5: Debloat Assistant
Inspect installed packages categorized by safety tier, preview guardrail protections, and execute safe debloating with guaranteed rollback script generation.

```text
--- Debloat Assistant ---
Package Catalog Breakdown for Sony Bravia TV:
  [SAFE]   12 known safe bloat packages
  [KEEP]   5 optional user packages
  [NEVER]  84 critical system packages (protected)
  [REVIEW] 18 third-party / user packages

Actions:
  [S] One-Key Safe Debloat (Disable all confirmed SAFE packages)
  [B] Back to Main Menu
Choice: 
```

- **`S` (One-Key Safe Debloat)**: Immediately evaluates all confirmed `SAFE` packages against the 10-layer guardrails engine and disables them.
- **Guardrails Shield**: Prevents accidental disabling of keyboard IMEs, Bluetooth remote control services, setup wizards, and the Google TV `launcherx` package.
- **Standalone Rollback Scripts**: Automatically creates standalone `rollback.sh`, `rollback.bat`, and `rollback.ps1` recovery scripts.
- **Audit Logging**: Appends structured JSON records to `audit_log.json`.

---

#### Screen 6: Deploy Launcher
Deploys OpenTV to your TV through an automated 5-step pipeline:

```text
--- Deploy Launcher ---
Target: 192.168.1.50:5555
Actions to perform:
  1. Push configuration JSON (/sdcard/OpenTV/config.json)
  2. Install OpenTV Release APK
  3. Set OpenTV as default Home activity
  4. Verify Home activity resolution
  5. Broadcast configuration reload

Press [Enter] to proceed, [B/Esc] to cancel: 
```

- **Pipeline Execution Results**:
  ```text
  Deployment Results:
    [OK]   Push Configuration: Config pushed successfully to /sdcard/OpenTV/config.json
    [OK]   Install Launcher APK: APK installed successfully
    [OK]   Set Default Home Activity: Default home activity set to 'org.opentv.launcher/.MainActivity'
    [OK]   Verify Home Activity Resolution: Active Home: org.opentv.launcher/.MainActivity
    [OK]   Broadcast Config Reload: Broadcast reload triggered successfully

  Press any key to return to menu...
  ```
- **Zero Reboot Required**: OpenTV immediately becomes the active default Home launcher without requiring a device reboot.

---

## 6. CLI Subcommands Reference

OpenTV provides 8 subcommands designed for interactive use, shell automation, and CI/CD pipelines.

### Global Options

Global options can be placed **before** or **after** any subcommand:

| Global Option | Type | Default | Description |
|---|---|---|---|
| `-t`, `--target` | String | `None` / Auto | Target device serial or `IP:port` (e.g. `192.168.1.50:5555`). |
| `--adb-path` | String | `adb` | Custom path to the `adb` binary (can also be set via `ADB` env var). |
| `-v`, `--verbose` | Flag | `False` | Enables verbose debug logging, printing every ADB command and full tracebacks. |
| `--version` | Flag | — | Prints OpenTV version (`OpenTV companion v1.0.0`) and exits. |

#### Flexible Flag Placement
Both argument orderings are fully supported:
```bash
# Option before subcommand:
opentv -t 192.168.1.50:5555 list-apps --launchable

# Option after subcommand:
opentv list-apps -t 192.168.1.50:5555 --launchable
```

### Standardized Exit Codes

Scripts can check standard process exit codes:

| Code | Constant | Meaning | Typical Trigger |
|---|---|---|---|
| `0` | `EXIT_SUCCESS` | Success | Operation completed successfully. |
| `1` | `EXIT_ERROR` | General Failure | Subprocess failure, ADB communication error, or missing file. |
| `2` | `EXIT_USAGE` | Invalid Arguments | Malformed IP/port, non-numeric pairing code, or ambiguous targets. |
| `3` | `EXIT_DEVICE_NOT_FOUND` | Device Offline | No device connected, or specified target device is unreachable. |
| `4` | `EXIT_GUARDRAIL_VIOLATION` | Safety Blocked | Operation rejected by debloat guardrails (e.g. IME or Google TV shield). |
| `130` | `SIGINT` | Aborted | Process interrupted by user with `Ctrl+C`. |

---

### Subcommand 1: `connect`
Connects to an Android TV device over wireless ADB.

```text
Syntax: opentv connect <target> [-p PORT] [--timeout TIMEOUT]
```

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `target` *(positional)* | String | *(Required)* | Device IP address or `IP:port` (e.g. `192.168.1.50` or `192.168.1.50:5555`). |
| `-p`, `--port` | Integer | `5555` | Port number to use if omitted from `target`. |
| `--timeout` | Float | `10.0` | Connection timeout in seconds. |

```bash
# Connect using default port 5555
opentv connect 192.168.1.50

# Connect specifying an explicit port and custom timeout
opentv connect 192.168.1.50:5555 --timeout 15.0
```

---

### Subcommand 2: `pair`
Performs one-time Android 11+ Wi-Fi pairing using an ephemeral port and 6-digit code.

```text
Syntax: opentv pair <target> <code> [--timeout TIMEOUT]
```

| Argument / Option | Type | Default | Description |
|---|---|---|---|
| `target` *(positional)* | String | *(Required)* | Device pairing address with port (`IP:port`, e.g. `192.168.1.50:38450`). |
| `code` *(positional)* | String | *(Required)* | 6-digit numeric pairing code shown on TV (e.g. `123456`). |
| `--timeout` | Float | `15.0` | Pairing timeout in seconds. |

```bash
# Pair device using the ephemeral port and code from the TV dialog
opentv pair 192.168.1.50:38450 123456

# Follow up immediately with connection to persistent port 5555
opentv connect 192.168.1.50:5555
```

---

### Subcommand 3: `list-apps`
Queries installed packages on the connected TV with optional filtering and JSON output.

```text
Syntax: opentv list-apps [-s] [-u] [-l] [--json] [--categories]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `-s`, `--system` | Flag | `False` | List only system packages (`pm list packages -s`). |
| `-u`, `--user` | Flag | `False` | List only user-installed / third-party packages (`pm list packages -3`). |
| `-l`, `--launchable` | Flag | `False` | Filter to only apps declaring a Leanback TV launcher banner. |
| `--json` | Flag | `False` | Output results formatted as JSON. |
| `--categories` | Flag | `False` | Annotate packages with safety categories (`never`, `keep`, `safe`, `review`). |

```bash
# List all apps declaring Leanback TV launcher banners
opentv list-apps --launchable

# Output all installed packages annotated with safety categories as JSON
opentv list-apps --categories --json

# List only third-party installed packages
opentv list-apps --user
```

---

### Subcommand 4: `configure`
Generates, customizes, and pushes the OpenTV launcher configuration (`config.json`).

```text
Syntax: opentv configure [-a APPS...] [--hdmi ID:TITLE...] [--theme THEME]
                         [--screensaver-idle SECS] [--pixel-shift | --no-pixel-shift]
                         [-o PATH] [--push] [--remote-path PATH] [--reload] [--base-config PATH]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `-a`, `--apps` | Strings | Default apps | Space or comma-separated list of package names visible on home screen. |
| `--hdmi` | String (append) | Built-ins | HDMI input in format `ID:Title[:visible]` (e.g. `HW5:PlayStation 5:true`). |
| `--theme` | String | `OLED_Black` | Visual theme (`OLED_Black` or `Dusk`). |
| `--screensaver-idle` | Integer | `180` | OLED screensaver idle timeout in seconds (0 to disable). |
| `--pixel-shift` | Flag | `True` | Enable periodic OLED orbital pixel shifting. |
| `--no-pixel-shift` | Flag | — | Disable OLED pixel shifting. |
| `-o`, `--output` | String | `None` | Local file path to write `config.json`. |
| `--push` | Flag | `False` | Push configuration directly to connected TV storage. |
| `--remote-path` | String | `/sdcard/OpenTV/config.json` | Remote file destination path on TV. |
| `--reload` | Flag | `False` | Send `org.opentv.launcher.RELOAD_CONFIG` broadcast after pushing. |
| `--base-config` | String | `None` | Path to an existing base `config.json` to load and modify. |

```bash
# Generate config with selected apps and custom HDMI labels
opentv configure \
  --apps com.google.android.youtube.tv com.netflix.ninja com.plexapp.android \
  --hdmi "HW5:PlayStation 5" \
  --hdmi "HW6:Nintendo Switch" \
  --screensaver-idle 120 \
  -o config.json

# Push config directly to the TV and trigger an instant UI reload
opentv configure --base-config config.json --push --reload
```

---

### Subcommand 5: `deploy`
Installs the OpenTV launcher APK, pushes configuration, registers OpenTV as default Home activity, and verifies launcher focus.

```text
Syntax: opentv deploy [--apk PATH] [--config PATH] [--set-home] [--reload]
                      [--component COMPONENT] [--skip-install]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--apk` | String | Auto-detected | Path to OpenTV release APK (`app-release.apk`). |
| `--config` | String | `None` | Path to local `config.json` to push to TV. |
| `--set-home` | Flag | `False` | Register OpenTV as default Home via `cmd package set-home-activity`. |
| `--reload` | Flag | `False` | Send configuration reload broadcast after installation. |
| `--component` | String | `org.opentv.launcher/.MainActivity` | Target launcher component. |
| `--skip-install` | Flag | `False` | Skip APK installation; only push config or set Home activity. |

```bash
# Full automated deployment: install APK, push config, and set as default Home
opentv deploy --apk app-release.apk --config config.json --set-home --reload

# Set OpenTV as default launcher on an already-installed device
opentv deploy --skip-install --set-home
```

---

### Subcommand 6: `debloat`
Safely disables manufacturer bloatware, telemetry, and sponsored launchers with 10-layer guardrails.

```text
Syntax: opentv debloat [-p PKGS...] [--safe-only] [-n] [--force-google-tv]
                       [--output-dir DIR] [-y]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `-p`, `--packages` | Strings | `None` | Explicit package names to disable via `pm disable-user --user 0`. |
| `--safe-only` | Flag | `False` | Automatically disable all confirmed `SAFE` packages for detected TV profile. |
| `-n`, `--dry-run` | Flag | `False` | Preview debloat candidates and guardrails without modifying the TV. |
| `--force-google-tv` | Flag | `False` | Bypass Google TV `launcherx` bootloop shield (advanced use only). |
| `--output-dir` | String | `.` | Directory to save rollback recovery scripts and `audit_log.json`. |
| `-y`, `--yes` | Flag | `False` | Automatically confirm prompts without interactive confirmation. |

```bash
# Preview safe debloat candidates on your TV without modifying anything
opentv debloat --safe-only --dry-run

# Disable confirmed safe vendor bloatware and generate recovery scripts
opentv debloat --safe-only --output-dir ./recovery

# Disable a specific sponsored app with automatic confirmation
opentv debloat -p com.tcl.partner.adservice -y
```

---

### Subcommand 7: `rollback`
Generates standalone multi-platform recovery scripts or executes immediate package re-enabling on the TV.

```text
Syntax: opentv rollback [--output-dir DIR] [-e] [-p PKGS...] [--from-registry]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--output-dir` | String | `.` | Destination directory to write standalone rollback scripts. |
| `-e`, `--execute` | Flag | `False` | Immediately re-enable packages directly on the connected TV via ADB. |
| `-p`, `--packages` | Strings | `None` | Specific package names to re-enable. |
| `--from-registry` | Flag | `False` | Read disabled package list from on-device `/data/local/tmp/opentv-disabled.txt`. |

```bash
# Generate standalone recovery scripts for Linux/macOS, Windows CMD, and PowerShell
opentv rollback --output-dir ./backup

# Immediate emergency recovery: re-enable all disabled packages on the TV
opentv rollback --execute
```

---

### Subcommand 8: `tui`
Launches the OpenTV interactive dual-mode terminal interface.

```text
Syntax: opentv tui [--fallback]
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--fallback` | Flag | `False` | Force non-interactive line-oriented engine (for CI, dumb terminals, or redirection). |

```bash
# Launch interactive ANSI VT100 dashboard
opentv tui

# Force line-oriented engine with 0 ANSI escapes
opentv tui --fallback
```

---

## 7. Manufacturer & Model Profiles

Different TV manufacturers customize Android TV and Google TV with proprietary system services, hardware settings activities, and input passthrough routing. Standard Android settings intents (`android.settings.SETTINGS`) often fail or cut active HDMI video feeds.

OpenTV addresses this by maintaining eight canonical brand profiles (`companion/opentv/profiles/detector.py`).

### The 8 Canonical Profiles

| Profile ID | Manufacturer & Hardware | Settings Component / Intent | Picture / Sound Handling | HDMI Hardware Passthrough URIs | Custom Guardrails |
|---|---|---|---|---|---|
| `sony` | Sony BRAVIA (Android TV & Google TV) | `com.sony.dtv.settings/.SettingsMainActivity` (Fallback: Keycode 176) | Component: `com.sony.dtv.settings/.picture.PictureSettingsActivity`<br>Component: `com.sony.dtv.settings/.sound.SoundSettingsActivity` | `content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW0` through `HW3` (Ports 1–4) | `launcherx_shield`<br>`sony_tvx_shield` |
| `tcl` | TCL / FFALCON / iFFALCON | `android.settings.SETTINGS` (Fallback: Keycode 176) | **Proprietary Service Call**:<br>`com.tcl.settings.SHOW_WINDOW`<br>Extras: `{"Type": "picture"}` & `{"Type": "SoundPreset"}` | `content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW1` through `HW3` (Ports 1–3) | `tcl_suspension_shield` |
| `philips` | Philips / TP Vision (Europe & Global) | `android.settings.SETTINGS` (Fallback: Keycode 176) | Standard Display/Sound Intents<br>(Fallback: Keycode 26) | `content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW5` through `HW8` (Ports 1–4) | `philips_homeintent_shield`<br>`philips_xtv_shield` |
| `hisense` | Hisense Android TV / Google TV | `android.settings.SETTINGS` (Fallback: Keycode 176) | Standard Display/Sound Intents | Direct Hardware Passthrough | `hisense_jamdeo_shield` |
| `xiaomi` | Xiaomi Mi TV / PatchWall / Redmi | `com.xiaomi.mitv.settings/.MainActivity` (Fallback: Keycode 176) | Standard Display/Sound Intents | Direct Hardware Passthrough | `xiaomi_input_shield` |
| `ccwgtv` | Chromecast with Google TV (Sabrina/Boreal) | `android.settings.SETTINGS` (Fallback: Keycode 176) | Standard Display/Sound Intents | Google TV CEC passthrough | `launcherx_shield`<br>`setupwraith_shield` |
| `nvidia` | Nvidia SHIELD TV (Foster/Darcy/Sif) | `com.nvidia.shield.settings/.MainActivity` (Fallback: Keycode 176) | Standard Display/Sound Intents | AI Upscaling / HDMI Passthrough | `nvidia_agent_shield` |
| `generic` | Generic / AOSP TV Box / Projectors | `android.settings.SETTINGS` (Fallback: Keycode 176) | Standard Display/Sound Intents | `content://android.media.tv/passthrough/HW{port_index - 1}` | Baseline system shields |

---

### OEM Quirks & Deep Hardware Integrations

#### TCL: ShowWindowService & Picture Overlays
- **Floating Overlays**: On TCL TVs, opening standard settings launches a full-screen app that cuts audio and video. OpenTV directly dispatches to TCL's proprietary `com.tcl.settings.SHOW_WINDOW` service with extra `{"Type": "picture"}` or `{"Type": "SoundPreset"}` to open floating quick-adjustment panels over the active HDMI feed.
- **Input Switching**: Dispatches to `com.tcl.suspension/.SuspensionActivity` for native source selection.
- **Hardware Protection**: `com.tcl.settings`, `com.tcl.suspension`, `com.tcl.providers.config`, and `com.tcl.tcl_bt_rcu_service` are guarded against debloating.

#### Sony BRAVIA: Quicklauncher & TVX HDMI Routing
- **HDMI Engine**: Managed through `com.sony.dtv.tvx` and `com.sony.dtv.tvinput`. Disabling these disables physical HDMI port switching. OpenTV guards these via `sony_tvx_shield`.
- **CEC & Power Controls**: Handled by `com.sony.dtv.braviasync`, `com.sony.dtv.remotepairing`, and `com.sony.dtv.rcpowerkey`.
- **Safe Debloating Targets**: Safely removes Samba TV ACR telemetry (`tv.samba.ssm`), Vewd ad engine (`com.vewd.core.service`), and retail demo loops (`com.sony.dtv.demomode`).

#### Philips (TP Vision): Home Intent Resolver & Label Sanitization
- **Home Button Interception**: Philips firmware routes every remote `HOME` keyevent through `org.droidtv.homeintentresolver`. Disabling this package completely disables the TV remote's `HOME` button. OpenTV classifies this package as `NEVER` and sets `requires_home_focus_test=True`.
- **Label Sanitization**: Philips TVs report HDMI inputs with hardware suffixes (e.g. `PlayStation 5&GAME`, `PC&COMPUTER`). OpenTV strips these suffixes using regex `&([A-Z][A-Z0-9_]{2,})$` to display clean labels.

#### Chromecast with Google TV: Notification Listener Protection
- **LauncherX Core Services**: The stock Google TV launcher (`com.google.android.apps.tv.launcherx`) hosts system notification listeners.
- **Bootloop Prevention**: Disabling `launcherx` without an active alternative launcher causes bootloops. When debloating, OpenTV requires `--force-google-tv`.
- **Privilege Restoration**: During rollback, OpenTV re-grants notification listener permissions:
  ```bash
  adb shell cmd notification allow_listener "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
  ```

---

### Automatic Brand Detection Heuristics

OpenTV automatically detects the TV hardware by querying system properties via `getprop`:
1. `ro.product.manufacturer` (e.g. "Sony", "TCL", "TP Vision", "Google", "NVIDIA", "Xiaomi", "Hisense")
2. `ro.product.brand` (e.g. "Philips", "Redmi", "ffalcon")
3. `ro.product.model` (e.g. "Bravia", "KD-", "XR-", "Chromecast", "SHIELD Android TV")
4. `ro.product.device` (e.g. "sabrina", "boreal", "darcy", "foster", "sif")
5. **Fallback Package Signatures**: If OEM properties are masked, OpenTV scans for signature packages:
   - `com.sony.dtv.*` → Sony
   - `com.tcl.settings` → TCL
   - `org.droidtv.homeintentresolver` → Philips
   - `com.jamdeo.tv.common` → Hisense
   - `com.mitv.tvhome` → Xiaomi
   - `com.nvidia.shield.agent` → Nvidia
6. **OLED Hardware Detection**: Regex `(?i)(oled|a80|a84|a90|a95)` evaluates model and device strings, automatically enabling OLED burn-in protection features.

---

## 8. Debloat Safety Manual & 10-Layer Guardrails

Indiscriminate debloating of smart TVs can cause bricked devices: disabling Bluetooth unpairs the remote control, disabling the only installed keyboard prevents entering Wi-Fi passwords, and disabling `launcherx` on Google TV causes an unrecoverable bootloop.

OpenTV enforces a strict **4-tier package safety taxonomy** and a **10-layer guardrails engine** to guarantee device stability.

### The 4-Tier Safety Taxonomy

```
+-------------------------------------------------------------------------+
|                          4-TIER SAFETY TAXONOMY                         |
+-------------------------------------------------------------------------+
|  [NEVER]   Critical System Services, Kernel, Bluetooth, Input Methods   |
|            -> Disabling bricks hardware, remote, or OS boot sequence    |
+-------------------------------------------------------------------------+
|  [KEEP]    Optional User Features (Chromecast, Assistant, TalkBack)     |
|            -> Non-critical, but kept by default to avoid UX degradation |
+-------------------------------------------------------------------------+
|  [SAFE]    Confirmed Vendor Bloat, Ads, Telemetry, Sponsored Launchers   |
|            -> Confirmed zero negative side effects on hardware/system   |
+-------------------------------------------------------------------------+
|  [REVIEW]  Unrecognized / Third-Party Applications                      |
|            -> Default-to-Safe: Never touched without explicit opt-in    |
+-------------------------------------------------------------------------+
```

#### Tier 1: NEVER (Absolute System & Hardware Shields)
- **Core OS & Framework**: `android`, `com.android.systemui`, `com.android.settings`, `com.android.tv.settings`, `com.android.shell`, `com.android.packageinstaller`, `com.google.android.packageinstaller`, `com.google.android.permissioncontroller`.
- **Connectivity & Input Drivers**: `com.android.bluetooth`, `com.android.inputdevices`, `com.android.networkstack.*`.
- **Input Methods (Keyboards)**: `com.google.android.inputmethod.latin` (Gboard), `com.android.inputmethod.latin` (AOSP), `com.google.android.leanback.ime`, `com.tcl.inputmethod.international`.
- **Google Play Framework**: `com.google.android.gms`, `com.google.android.gsf`, `com.android.vending`.
- **Hardware Audio/Video**: `com.dolby.android.audio.service`, `com.android.providers.tv`.
- **Vendor Core Services**: `com.sony.dtv.tvx`, `com.tcl.settings`, `org.droidtv.homeintentresolver`, `com.jamdeo.tv.common`, `com.xiaomi.mitv.settings`, `com.nvidia.shield.agent`.

#### Tier 2: KEEP (Optional Features Kept by Default)
- `com.google.android.apps.mediashell` (Chromecast built-in)
- `com.google.android.katniss`, `com.google.android.tv.assistant` (Google Assistant)
- `com.google.android.marvin.talkback`, `com.google.android.tts` (Accessibility / Screen Reader)
- `com.google.android.webview` (System WebView)
- `com.android.dreams.basic`, `com.google.android.apps.tv.dreamx` (Screensavers)
- `com.google.android.tv.remote.service` (Smartphone Remote App Pairing)

#### Tier 3: SAFE (Confirmed Bloatware, Ads & Telemetry)
- **Google / Android Ads**: `com.google.android.tvrecommendations`, `com.google.android.backdrop`, `com.google.android.videos`, `com.google.android.youtube.tvmusic`, `com.android.printspooler`.
- **Sony**: `tv.samba.ssm`, `com.vewd.core.service`, `com.sony.dtv.demomode`, `com.sony.dtv.hbbtvlauncher`, `com.sony.dtv.videoframeserver`.
- **TCL**: `com.tcl.waterfall.overseas`, `com.tcl.esticker`, `com.tcl.partnercustomizer`, `com.tcl.messagebox`, `com.tcl.dashboard`, `com.tcl.ttvs`.
- **Philips**: `org.droidtv.nettv`, `org.droidtv.philipstvcollection`, `org.droidtv.demomode`.
- **Hisense**: `net.vidaatv.hisense.android.tv`, `android.autoinstalls.config.hisense`, `com.hisense.storemode`, `com.jamdeo.tv.vod`.
- **Xiaomi**: `com.mitv.tvhome.michannel`, `com.mitv.tvhome.mitvplus`, `com.xiaomi.mitv.updateservice`, `com.xiaomi.mitv.mediaexplorer`.
- **Nvidia**: `com.nvidia.remotelogger`, `com.nvidia.tegrazone3`, `com.nvidia.shield.diagnostics`, `com.nvidia.ota`.

#### Tier 4: REVIEW (Unrecognized Applications)
- Any package not cataloged in `CURATED_PACKAGES` is assigned `REVIEW`.
- **Default-to-Safe Invariant**: OpenTV will **never** disable a `REVIEW` package during automated or batch runs. Disabling requires explicit manual package specification.

---

### The 10-Layer Guardrails Engine

Before `pm disable-user --user 0` is executed for any package, the candidate must pass 10 discrete safety gates (`companion/opentv/debloat/guardrails.py`):

```
[Candidate Package]
       │
       ▼
[Layer 1: Package Syntax & Shell Injection Check] ───────────► [BLOCK: Illegal Characters / Malformed]
       │
       ▼
[Layer 2: PERSISTENT Flag Detection (dumpsys package)] ──────► [BLOCK: System Process Marked PERSISTENT]
       │
       ▼
[Layer 3: Google TV launcherx Bootloop Gate] ────────────────► [BLOCK: launcherx without --force-google-tv]
       │
       ▼
[Layer 4: Device Provisioning Gate (device_provisioned)] ────► [BLOCK: Setup Wizard on Unprovisioned TV]
       │
       ▼
[Layer 5: Keyboard / IME Availability Counter] ──────────────► [BLOCK: Last Active Keyboard Protection]
       │
       ▼
[Layer 6: Bluetooth Remote & Input Service Shield] ──────────► [BLOCK: Remote Disconnection Hazard]
       │
       ▼
[Layer 7: Philips Home Intent Resolver Shield] ──────────────► [BLOCK: Home Button Loss Hazard]
       │
       ▼
[Layer 8: OLED Screensaver Protection Guard] ────────────────► [BLOCK: Panel Burn-in Hazard on OLED]
       │
       ▼
[Layer 9: Core AOSP Platform Hard-Block] ────────────────────► [BLOCK: android, systemui, settings, shell]
       │
       ▼
[Layer 10: Curated Safety DB Cross-Check] ───────────────────► [BLOCK: Classified as SafetyCategory.NEVER]
       │
       ▼
[PERMITTED: Package is Safe to Disable]
```

1. **Syntax & Injection Shield**: Validates against regex `^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$` and blocks shell characters (` ;&$|`'"<>\/`).
2. **PERSISTENT System Process Shield**: Rejects any package declaring the `PERSISTENT` flag in its manifest.
3. **Google TV LauncherX Shield**: Disabling `com.google.android.apps.tv.launcherx` on Google TV devices is blocked unless `--force-google-tv` or `GOOGLE_TV=1` is explicitly provided.
4. **Provisioning Gatekeeper**: Queries `settings get global device_provisioned`. Setup wizards (`setupwraith`, `com.android.provision`) cannot be disabled until value is `1`.
5. **IME Availability Guarantee**: Tallies installed keyboards (`KNOWN_IMES`, `.ime`, `.inputmethod.`). Rejects disablement if it would leave zero active keyboards.
6. **Remote Control & Bluetooth Shield**: Preserves all Bluetooth remote pairing, power button, and uinput services (`com.android.bluetooth`, `com.sony.dtv.remotepairing`, `com.tcl.tcl_bt_rcu_service`, `org.droidtv.GlobalKey`, etc.).
7. **Philips Home Router Shield**: Hard-blocks disabling `org.droidtv.homeintentresolver`.
8. **OLED Burn-In Protection**: If an OLED panel is detected, basic screensavers (`com.android.dreams.basic`, `com.google.android.apps.tv.dreamx`) cannot be disabled.
9. **Core System Hard-Block**: Hard-blocks `android`, `com.android.systemui`, `com.android.settings`, and `com.android.shell`.
10. **Curated Safety DB Cross-Check**: Confirms package is not classified as `SafetyCategory.NEVER`.

---

## 9. 100% Reversible Rollback Engine

OpenTV guarantees that all system changes can be completely undone without relying on Python or local configuration files.

### Standalone Zero-Dependency Recovery Scripts

Whenever OpenTV disables a package, it automatically creates three standalone recovery scripts in the output directory:

```
output_directory/
├── rollback.sh     # For Linux and macOS (POSIX Shell, chmod 0755)
├── rollback.bat    # For Windows Command Prompt (Strict CRLF endings)
└── rollback.ps1    # For Windows PowerShell (Parameterized target device)
```

#### POSIX Shell Script (`rollback.sh`)
- Zero dependencies: runs on any standard Unix shell (`sh`, `bash`, `zsh`).
- Configured with `set -e` for failure safety.
- Quotes device paths to avoid path-mangling when executed from Git Bash / MSYS2.
- Automatically re-enables Google TV notification listener services.

```bash
#!/bin/sh
set -e
ADB="${ADB:-adb}"
DEV_ARG="-s 192.168.1.50:5555"

echo 'Starting OpenTV emergency rollback...'
$ADB $DEV_ARG shell pm enable "tv.samba.ssm"
$ADB $DEV_ARG shell pm enable "com.google.android.tvrecommendations"
# Restore Google TV Notification Listener Service if launcherx was touched
$ADB $DEV_ARG shell cmd notification allow_listener "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
# Clear on-device registry
$ADB $DEV_ARG shell "rm -f /data/local/tmp/opentv-disabled.txt" 2>/dev/null || true
echo 'Rollback completed successfully. All modified packages re-enabled.'
```

#### Windows Command Prompt (`rollback.bat`)
- Strictly generated with Windows CRLF (`\r\n`) line endings.
- Uses `setlocal enabledelayedexpansion` and `%ERRORLEVEL%` validation.

```batch
@echo off
setlocal enabledelayedexpansion
set ADB=adb
set DEV_ARG=-s 192.168.1.50:5555

echo Starting OpenTV emergency rollback...
%ADB% %DEV_ARG% shell pm enable tv.samba.ssm
if %ERRORLEVEL% NEQ 0 (echo Warning: Failed to re-enable tv.samba.ssm)
%ADB% %DEV_ARG% shell pm enable com.google.android.tvrecommendations
if %ERRORLEVEL% NEQ 0 (echo Warning: Failed to re-enable com.google.android.tvrecommendations)
%ADB% %DEV_ARG% shell "rm -f /data/local/tmp/opentv-disabled.txt" >nul 2>&1
echo Rollback completed.
endlocal
```

#### Windows PowerShell (`rollback.ps1`)
- Standard PowerShell script supporting parameter overrides:

```powershell
[CmdletBinding()]
param([string]$Target = "192.168.1.50:5555")
$ErrorActionPreference = 'Continue'
$devArgs = if ($Target) { "-s $Target " } else { "" }

Write-Host 'Starting OpenTV emergency rollback...' -ForegroundColor Cyan
$packages = @("tv.samba.ssm", "com.google.android.tvrecommendations")

foreach ($pkg in $packages) {
    Write-Host "Re-enabling $pkg..."
    Invoke-Expression "adb $devArgs shell pm enable $pkg"
}
adb $devArgs shell "rm -f /data/local/tmp/opentv-disabled.txt" 2>$null
Write-Host 'Rollback finished.' -ForegroundColor Green
```

---

### On-Device State Registry (`/data/local/tmp/opentv-disabled.txt`)

OpenTV also records every disabled package directly on the TV:
1. **Host-Independent Tracking**: Every disabled package is appended to `/data/local/tmp/opentv-disabled.txt`.
2. **Emergency Recovery Without Local Files**: If you run `opentv rollback --from-registry` from a different computer without local backup files, OpenTV reads `/data/local/tmp/opentv-disabled.txt` directly over ADB and re-enables all listed packages.
3. **Auto-Cleanup**: Once rollback finishes, `/data/local/tmp/opentv-disabled.txt` is cleaned up from the TV.

---

### Dual Audit Logging System

Every modification is recorded in real time to two local audit files:

#### `audit_log.json` (Machine-Readable JSON Lines)
Each action is written as an atomic JSON record:
```json
{
  "action": "DISABLE_PACKAGE",
  "package_name": "tv.samba.ssm",
  "device_id": "192.168.1.50:5555",
  "timestamp": "2026-10-25T14:30:00.123456+00:00",
  "brand_profile": "sony",
  "category": "safe",
  "previous_state": "enabled",
  "new_state": "disabled",
  "command": "adb -s 192.168.1.50:5555 shell pm disable-user --user 0 tv.samba.ssm",
  "exit_code": 0,
  "verification_command": "",
  "verified": true,
  "rollback_command": "adb -s 192.168.1.50:5555 shell pm enable tv.samba.ssm",
  "user_confirmed": true,
  "status": "SUCCESS"
}
```

#### `audit_log.txt` (Human-Readable Audit Trail)
```text
[2026-10-25T14:30:00.123456+00:00] ACTION: DISABLE_PACKAGE
  Target: 192.168.1.50:5555 (Brand: SONY)
  Package: tv.samba.ssm (Category: safe)
  Result: SUCCESS (exit code 0)
  State: enabled -> disabled (Verified: YES)
  Command: adb -s 192.168.1.50:5555 shell pm disable-user --user 0 tv.samba.ssm
  Rollback Command: adb -s 192.168.1.50:5555 shell pm enable tv.samba.ssm
```

---

## 10. Reproducible Build Guide

OpenTV features a **dual build pipeline** architected for reproducibility, minimal resource consumption, and seamless IDE integration:

1. **Primary Toolchain — Standalone Zero-Gradle Pipeline (`app/build.sh`)**: The recommended, zero-dependency, reproducible toolchain that builds, aligns, cryptographically signs, and verifies the release APK in under 4 seconds without invoking Gradle or spawning a JVM background daemon.
2. **Secondary Toolchain — Android Gradle Build Pipeline**: An enterprise-grade Android Gradle Plugin (AGP 9.2.1) configuration for Android Studio IDE development, code navigation, and executing the native Java JUnit test suite (`LauncherUnitTest` and `AdversarialMoveModeTest`).

### Toolchain Comparison

| Dimension | Primary Toolchain (`app/build.sh`) | Secondary Toolchain (`gradle`) |
| :--- | :--- | :--- |
| **Philosophy** | **Zero-dependency, reproducible, fast** | **Standard AGP / IDE integration** |
| **Dependencies** | JDK 17/21 + Android SDK tools only | System Gradle (>= 8.x/9.x) or generated wrapper |
| **Daemon Overhead** | **0 MB** (Terminates immediately upon completion) | ~1.5 GB to 2.5 GB background JVM daemon |
| **Build Duration** | **< 4 seconds** (Cold & warm) | 15–30s cold startup, 1–3s warm |
| **Offline Capability** | **100% Offline** (Zero network lookups) | Queries Google / Maven repositories |
| **Signing Automation** | Automatic `release.jks` generation + v1/v2/v3 signing | Automatic `release.jks` generation + v1/v2/v3 signing |
| **Artifact Output** | `OpenTV/app-release.apk` (Project root) | `app/build/outputs/apk/release/app-release.apk` |
| **Unit Testing** | Cryptographic signature verification (`apksigner`) | Host JVM JUnit 4 test runner (`gradle test`) |
| **Recommended For** | **Release builds, packaging, packaging CI, CLI users** | **Android Studio, local test debugging** |

---

### Prerequisites

Both build pipelines require a standard Java Development Kit and the Android SDK command-line tools:

- **Java Development Kit**: OpenJDK 17 or 21 (`javac`, `jar`, `keytool`).
- **Android SDK**: Build-Tools (`34.0.0` or `36.0.0`) and Platform (`android-34` or `android-35`).
- **Environment Configuration**:
  ```bash
  export ANDROID_HOME="$HOME/Android/Sdk"
  export PATH="$ANDROID_HOME/build-tools/36.0.0:$PATH"
  ```
  *(Note: `app/build.sh` automatically probes `$ANDROID_HOME`, `$ANDROID_SDK_ROOT`, `$HOME/Android/Sdk`, and `/home/prem/Android/Sdk`, so manual exports are optional if the SDK is in standard locations.)*

---

### Primary Toolchain: Standalone Zero-Gradle Build Pipeline (`app/build.sh`)

The standalone pipeline produces an optimized, multi-scheme signed release APK directly using Android SDK CLI binaries (`aapt2`, `javac`, `d8`, `zipalign`, and `apksigner`). It requires zero Gradle daemon memory, executes zero network calls, and compiles in **under 4 seconds**.

```bash
# Execute primary standalone reproducible build from repository root
./app/build.sh
```

#### Pipeline Architecture (6 Sequential Stages)

```
[1/6] AAPT2 Link Manifest & Resources
      aapt2 link -o out/base.apk -I android.jar --manifest src/main/AndroidManifest.xml \
        --min-sdk-version 21 --target-sdk-version 34
      ▼
[2/6] Java Bytecode Compilation (Java 17 Target)
      javac -source 17 -target 17 -cp android.jar -d out/classes src/main/java/**/*.java
      ▼
[3/6] DEX Compilation via D8 (Min-API 21 Desugaring)
      d8 --min-api 21 --release --lib android.jar --output out/dex out/classes/**/*.class
      ▼
[4/6] Archive Packaging (Zero-Dependency DEX Injection)
      cd out/dex && jar uf ../unsigned.apk classes.dex
      (Fallback to python3 zipfile or zip if jar binary is not installed)
      ▼
[5/6] 4-Byte Zip Alignment
      zipalign -f 4 out/unsigned.apk out/aligned.apk
      ▼
[6/6] Multi-Scheme Cryptographic Signing (v1, v2, v3)
      apksigner sign --ks release.jks --ks-pass pass:opentv123 --key-pass pass:opentv123 \
        --ks-key-alias opentv --v1-signing-enabled true --v2-signing-enabled true \
        --v3-signing-enabled true --out app-release.apk out/aligned.apk
```

#### Key Capabilities of `app/build.sh`:
1. **Automatic SDK Auto-Discovery**: Automatically scans `$ANDROID_HOME`, `$ANDROID_SDK_ROOT`, `$HOME/Android/Sdk`, `/home/prem/Android/Sdk`, and `/opt/android-sdk` for valid `platforms` and `build-tools`.
2. **Automatic Keystore Provisioning**: If `release.jks` does not exist, automatically creates an RSA 2048-bit release keystore with 10,000-day validity.
3. **Multi-Scheme Cryptographic Verification**: Automatically invokes `apksigner verify --verbose` to guarantee that v1 (JAR signing), v2 (APK Signature Scheme v2), and v3 (APK Signature Scheme v3) are valid before concluding.
4. **Primary Artifact Delivery**: Writes the final, signed release APK directly to `./app-release.apk` in the project root (as well as `app/out/opentv.apk`) for immediate deployment via `python3 -m opentv deploy`.

---

### Secondary Toolchain: Android Gradle Build Pipeline

For developers working inside Android Studio, CI pipelines utilizing Gradle plugins, or when executing the native Java JUnit test suite:

#### Clean-Source Repository Policy
In strict compliance with open-source security hygiene and zero-binary source tree standards, OpenTV **does not commit pre-compiled binary wrapper JARs** (`gradle-wrapper.jar`) or wrapper scripts to version control. You can invoke Gradle either using your system's installed Gradle binary or by generating a local wrapper.

#### Option A: Direct System Gradle (Recommended)
If Gradle (version 8.x or 9.x) is installed on your development workstation:

```bash
# 1. Compile signed release APK
gradle assembleRelease

# Artifact generated at:
# app/build/outputs/apk/release/app-release.apk

# 2. Run Java unit and adversarial test suite (30 assertions: 25 unit + 5 adversarial)
gradle test

# 3. Clean project build cache
gradle clean
```

#### Option B: Generating & Using the Gradle Wrapper
If your workflow, CI environment, or team policy requires the project-local `./gradlew` wrapper:

```bash
# 1. Generate the Gradle wrapper locally (one-time setup)
gradle wrapper

# This generates:
# ├── gradlew              (POSIX shell wrapper)
# ├── gradlew.bat          (Windows batch wrapper)
# └── gradle/wrapper/
#     ├── gradle-wrapper.jar
#     └── gradle-wrapper.properties

# 2. Execute builds using the wrapper:
# Linux / macOS:
./gradlew assembleRelease
./gradlew test

# Windows (Command Prompt):
gradlew.bat assembleRelease
gradlew.bat test

# Windows (PowerShell):
.\gradlew assembleRelease
.\gradlew test
```

---

### Native Launcher Architecture Highlights

1. **Bug #30 Anti-Bounce Protection (`FocusController.java`)**:
   - On physical remotes with high Bluetooth latency or mechanical bounce, rapidly pressing keys can trigger `ACTION_DOWN` on tile A, but focus shifts before `ACTION_UP` fires.
   - `FocusController` binds `okDownKey = key` strictly on `ACTION_DOWN`. On `ACTION_UP`, click execution occurs **only if** `key.equals(okDownKey)`.
   - `onWindowFocusChanged(false)` clears `okDownKey` whenever the window loses focus, preventing click bleeding when returning from dialogs or external apps.
2. **Move Mode with 100% Cancel Rollback**:
   - Long-press OK or press MENU on any app tile to enter Move Mode.
   - The selected tile receives a 4dp white outline; arrow keys swap positions in real time.
   - **Pressing BACK**: Restores the original order from a defensive snapshot and rebuilds the grid without persisting changes.
   - **Pressing OK**: Commits the new order to `SharedPreferences` and configuration files.
3. **Adaptive 6-Column Mathematical Grid**:
   - Computes layout dimensions from a reference 1080p canvas:
     $$\text{scale} = \frac{\text{widthPixels}}{1920.0}$$
     $$\text{tileW} = \frac{\text{widthPixels} - (2 \times \text{margin}) - (\text{gap} \times 5)}{6}$$
     $$\text{tileH} = \text{round}\left(\text{tileW} \times \frac{9}{16}\right)$$
   - Scales smoothly across 720p HD (`172x97 px`), 1080p FHD (`258x145 px`), and 4K UHD (`516x290 px`).
4. **Procedural Vector Line Icons (`LineIcon.java`)**:
   - Replaces raster images with vector opcode arrays (`moveTo`, `lineTo`, `close`, `addCircle`, `addArc`) drawn on a normalized 240x240 coordinate plane.
   - Renders at native display resolution with zero PNG/WebP files.
5. **Zero-Asset 17-Language Localization (`Strings.java`)**:
   - Full localization across 17 languages embedded directly in Java bytecode, requiring zero external XML resource tables.

---

## 11. Verification & Testing Guide

OpenTV includes an automated multi-tier verification harness. The test runner uses Python's standard library `unittest` module and requires **zero pip dependencies**.

### Test Suite Structure

```
tests/
├── run_tests.py                    # Unified test runner with tier filtering
├── adapter.py                      # Contract adapter bridging companion & test oracles
├── mocks/
│   └── mock_adb.py                 # In-memory subprocess ADB emulator
├── test_tier1_feature_coverage.py  # Tier 1: Core Feature Coverage (35 tests)
├── test_tier2_boundary_cases.py    # Tier 2: Boundary & Corner Cases (32 tests)
├── test_tier3_combinations.py      # Tier 3: Cross-Feature Combinations (7 tests)
├── test_tier4_scenarios.py         # Tier 4: Real-World Scenarios (5 tests)
└── test_launcher_adversarial.py    # Adversarial launcher focus & scaling tests (18 tests)
```

---

### Running the Tests

#### 1. Unified 4-Tier Test Runner (79 Tests)
The unified test runner executes all 4 tiers against the mock ADB environment in ~0.02 seconds:

```bash
# Run all 79 tests across Tiers 1-4
python3 tests/run_tests.py

# Run with verbose output (shows every test method name and docstring)
python3 tests/run_tests.py -v

# Stop immediately on the first failure
python3 tests/run_tests.py --failfast
```

#### 2. Tier-by-Tier Execution
```bash
# Tier 1: Core Feature Coverage (35 tests)
python3 tests/run_tests.py --tier 1

# Tier 2: Boundary & Corner Cases (32 tests: injection, malformed IPs, guardrails)
python3 tests/run_tests.py --tier 2

# Tier 3: Cross-Feature Combinations (7 tests: brand profile + debloat presets)
python3 tests/run_tests.py --tier 3

# Tier 4: Real-World Scenarios (5 tests: complete device provisioning)
python3 tests/run_tests.py --tier 4
```

#### 3. Standard Unittest Discovery (All 97 Tests)
To run all 79 E2E tests plus the 18 adversarial launcher logic verification tests:

```bash
python3 -m unittest discover -s tests -v
```

---

### Mock Simulation vs Live Android TV Emulator (AVD)

| Feature | Mock Simulation Mode (Default) | Live Hardware / AVD Mode (`--emulator`) |
| :--- | :--- | :--- |
| **Command** | `python3 tests/run_tests.py` | `python3 tests/run_tests.py --emulator`<br>or `OPENTV_RUN_EMULATOR=1 python3 tests/run_tests.py` |
| **Requirements** | Python 3.9+ standard library only | Android SDK (`adb`, emulator AVD or physical TV) |
| **Execution Time** | ~0.015 seconds | ~10 to 30 seconds |
| **Operations** | In-memory simulated device properties, dumpsys, package states, files, keyevents | Real `adb connect`, live APK installation, live config push, live remote keyevents |
| **Environment Behavior** | Deterministic across all environments | Skips gracefully if no live AVD is running |

#### Running Against a Live Android TV Emulator (AVD):
1. Start your Android TV emulator instance (e.g. `emulator -avd Television_1080p -no-audio -no-window &`).
2. Run the test harness with the `--emulator` flag:
   ```bash
   python3 tests/run_tests.py --emulator
   ```

---

### Verification Summary & Success Assertions

After making modifications to OpenTV, run these three commands to confirm full system integrity:

```bash
# 1. Verify all 79 E2E tests pass
python3 tests/run_tests.py

# 2. Verify all 97 unit tests pass under discovery
python3 -m unittest discover -s tests -v

# 3. Verify standalone release build compiles, aligns, and signs cleanly
./app/build.sh
```

---

## License

OpenTV is licensed under the [MIT License](LICENSE).
You are free to use, modify, and distribute this software for personal and commercial purposes.
