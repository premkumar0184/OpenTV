# 📺 OpenTV

> **Clean, ad-free Android TV & Google TV launcher with a cross-platform companion for Linux, macOS, and Windows.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Android](https://img.shields.io/badge/Android-5.0%2B%20(API%2021--34)-green.svg)](https://developer.android.com)
[![Python](https://img.shields.io/badge/Python-3.8%2B%20(Zero%20Deps)-yellow.svg)](https://www.python.org)
[![Release](https://img.shields.io/badge/Release-GitHub%20Releases-blue.svg)](https://github.com/premkumar0184/OpenTV/releases)
[![APK Size](https://img.shields.io/badge/APK%20Size-~53%20KB-success.svg)](https://github.com/premkumar0184/OpenTV/releases)
[![Tests](https://img.shields.io/badge/Python%20Tests-442%2F442%20Passing-brightgreen.svg)](tests/)
[![Java Tests](https://img.shields.io/badge/Java%20Tests-38%2F38%20Passing-brightgreen.svg)](app/)

---

## 💡 Why OpenTV?

Modern Smart TVs (Android TV and Google TV) have become cluttered with unskippable ads, sponsored rows, background tracking, and laggy animations. 

**OpenTV** restores your television to what it should be: **fast, quiet, and under your control.**
- **No ads, zero telemetry, zero recommendations.**
- **Only the apps you choose**, ordered the way you want.
- **No cloud or AI required at runtime** — works completely locally via standard ADB over Wi-Fi or USB.
- **100% reversible** with standalone, single-command rollback scripts.

---

## ✨ Features

- **📺 Minimalist Home Screen**: A clean, lightning-fast app grid with live HDMI input switching (`TvInputManager`), customizable quick-settings shortcuts, clock, and OLED burn-in prevention.
- **🖼️ Dynamic Sideload Banner Generator**: Automatically synthesizes 16:9 landscape banners for mobile/tablet apps lacking Leanback banners (`BannerGenerator.java`), featuring primary palette gradient extraction from the app icon and in-memory LRU caching for buttery 60fps scrolling.
- **🎮 100% Remote-Controlled**: Built from the ground up for standard TV remote D-pads (Up, Down, Left, Right, OK, Back). Press and hold OK on any tile to Move, Replace, or Remove apps.
- **📡 ZeroConf & mDNS Local Auto-Discovery**: Automatically scans and discovers Android TV / Google TV devices on your local network via mDNS and SSDP without needing to hunt for IP addresses.
- **🏷️ Friendly App Metadata Engine**: Built-in resolution for ~350 popular TV packages into human-readable titles, functional genres (Streaming, Audio, Gaming, Utilities), and smart tokenizer fallbacks.
- **💻 Cross-Platform Companion**: Pure Python 3 standard library CLI and interactive Terminal UI (TUI) running natively on **Linux, macOS, and Windows** (PowerShell / CMD) with **zero `pip` dependencies**, plus standalone single-file executables (`opentv.pyz` and native binaries).
- **🔄 Dynamic Debloat Definitions & Remote Sync**: Update debloat catalogs on the fly (`--update-definitions`) while maintaining an unbypassable immutable shield protecting critical system components.
- **🏷️ Model & OEM Profiles**: Tailored hardware adapters and debloat catalogs for **Sony, TCL, Philips, Hisense, Xiaomi, Chromecast with Google TV, Nvidia Shield**, and generic devices.
- **🛡️ 10-Layer Safety Guardrails**: Strictly prevents device bricking or bootloops (e.g. preserves `com.google.android.apps.tv.launcherx` on Google TV devices).
- **↩️ Standalone Rollback**: Generates executable recovery scripts ([`rollback.sh`](rollback.sh), [`rollback.bat`](rollback.bat), [`rollback.ps1`](rollback.ps1)) that restore disabled apps and the stock launcher anytime without Python.
- **⚡ Featherweight Footprint**: The signed launcher APK ([`opentv.apk`](https://github.com/premkumar0184/OpenTV/releases)) is **under 54 KB**.

---

## 📦 Downloads & Official Releases

Pre-compiled, cryptographically signed release binaries and standalone companion archives are automatically built, verified, and published on **[GitHub Releases](https://github.com/premkumar0184/OpenTV/releases)** for every release version tag (`v*`):

| Release Asset | Description | Target Platform | Link |
|---|---|---|---|
| **`opentv.apk`** | Signed, standalone Android TV launcher APK (<60 KB, v1+v2+v3 signatures). Ready for sideloading. | Android TV / Google TV (API 21+) | [Download Latest](https://github.com/premkumar0184/OpenTV/releases) |
| **`opentv.pyz`** | Zero-dependency standalone Python zipapp executable archive (~85 KB). Run directly with `python3 opentv.pyz`. | Linux, macOS, Windows | [Download Latest](https://github.com/premkumar0184/OpenTV/releases) |
| **`opentv-companion.tar.gz`** | Complete companion manager archive with source, rollback scripts, and documentation. | Linux, macOS, Windows | [Download Latest](https://github.com/premkumar0184/OpenTV/releases) |
| **`SHA256SUMS.txt`** | Cryptographic SHA-256 checksums for verifying binary integrity before sideloading or execution. | All Platforms | [Download Latest](https://github.com/premkumar0184/OpenTV/releases) |

### Integrity Verification
Verify downloaded assets against published checksums:
```bash
sha256sum -c SHA256SUMS.txt
```

---

## ⚡ 60-Second Quick Start

### 1. Enable Debugging on your TV
1. On your TV, navigate to **Settings** → **Device Preferences** (or **System**) → **About**.
2. Click **Build** 7 times until Developer Mode is unlocked.
3. Open **Developer Options** and enable **Network Debugging** / **Wireless Debugging** (or **USB Debugging**).

### 2. Connect Your Computer
Ensure your computer and TV are on the same local network:

```bash
# Standard ADB connection (port 5555)
python3 -m opentv connect <TV_IP>:5555

# Android 11+ Wireless Debugging Pairing (if required)
python3 -m opentv pair <TV_IP>:<PAIRING_PORT> <PAIRING_CODE>
python3 -m opentv connect <TV_IP>:<CONNECT_PORT>
```

### 3. Launch the Interactive Setup Wizard
Run the zero-dependency interactive TUI:
```bash
python3 -m opentv tui
```
*Navigate with arrow keys to connect to your TV, pick your apps, preview your 6-column TV layout, safely debloat vendor ads, and deploy the launcher.*

---

## 🛠️ CLI Subcommands Reference

OpenTV can also be controlled directly via scriptable CLI commands:

| Command | Description | Example |
|---|---|---|
| `discover` | Scan local network for Android TV devices via mDNS & SSDP | `python3 -m opentv discover` |
| `connect` | Connect to TV over network or auto-discover | `python3 -m opentv connect --discover` |
| `pair` | Pair with TV via Android 11+ wireless code | `python3 -m opentv pair 192.168.1.50:38450 123456` |
| `list-apps` | List installed apps with friendly names & genres | `python3 -m opentv list-apps --categories` |
| `configure` | Push custom app grid and shortcuts | `python3 -m opentv configure --apps com.netflix.ninja,com.youtube.tv` |
| `deploy` | Install launcher APK & verify Home default | `python3 -m opentv deploy --set-home` |
| `debloat` | Safely disable vendor bloatware or update definitions | `python3 -m opentv debloat --safe-only --dry-run` |
| `rollback` | Restore all disabled packages & stock launcher | `python3 -m opentv rollback --execute` |
| `tui` | Launch full interactive terminal UI | `python3 -m opentv tui` |

---

## 🏷️ Supported TV Profiles & Hardware Adapters

OpenTV automatically detects your TV brand via `getprop` or allows interactive selection:

| Brand / Model | Key Hardware & Software Adaptations |
|---|---|
| **Google TV / Chromecast** | Protects `com.google.android.apps.tv.launcherx` to eliminate bootloops while removing ads. |
| **Sony BRAVIA** | Maps Sony shelf and input frameworks; cleans Samba TV ACR tracking. |
| **TCL** | Bypasses missing Android sound pages by routing to TCL's panel service (`com.tcl.settings.SHOW_WINDOW`). |
| **Philips** | Routes default Home intent transitions through Philips' `org.droidtv.homeintentresolver`. |
| **Hisense** | Handles VIDAA/Android TV hybrid services and TV tuner frameworks. |
| **Xiaomi / Mi TV** | Cleans PatchWall recommendation feeds while preserving system keyboard and inputs. |
| **Nvidia Shield** | Preserves Shield Hub / GeForce Now gaming settings while silencing recommendations. |
| **OLED TVs** | Enforces screensaver retention and orbital pixel shifting to eliminate burn-in risk. |

---

## 🛡️ Debloat Safety & Rollback Guarantee

OpenTV classifies all packages into 4 strict safety tiers:
1. **`never`**: Critical system services (Wi-Fi, Bluetooth, HDMI, System UI, Play Services, Settings). Never disabled.
2. **`keep`**: Optional features (Chromecast/casting, TV tuners). Disabled only if explicitly opted out.
3. **`safe`**: Known bloatware, telemetry, and promotional ad banners. Safe to disable.
4. **`review`**: Unknown packages. Defaulted to enabled.

### Emergency Rollback
Every time a change is made, OpenTV updates your standalone rollback scripts. To revert everything back to stock:
- **Linux / macOS**: `sh rollback.sh`
- **Windows Command Prompt**: `rollback.bat`
- **Windows PowerShell**: `.\rollback.ps1`
- **Or via CLI**: `python3 -m opentv rollback`

---

## 🏗️ Building from Source

### Standalone Build (Zero Gradle, AAPT2 + D8)
Requires Android SDK (`platforms;android-34` and `build-tools;34.0.0`):
```bash
./app/build.sh
```
*Compiles, dexes, aligns, and signs `app-release.apk` (<50 KB) in under 3 seconds.*

### Gradle Build
```bash
gradle :app:assembleRelease
```

---

## 🧪 Testing & Verification

OpenTV includes a complete automated test harness running without external dependencies:

```bash
# Run all 5 tiers of automated E2E tests (404 tests in <1.5s)
python3 tests/run_tests.py

# Run full discovery test suite across all modules (442 tests)
python3 -m unittest discover -s tests

# Run Java launcher unit tests (38 tests)
gradle test
```

---

## 📁 Repository Structure

```
OpenTV/
├── .github/workflows/          # CI/CD Workflows (Multi-OS CI, Android build, Lint, Release)
├── app/                        # Android TV Native Launcher (Java 8, API 21+)
│   ├── src/main/java/org/opentv/launcher/
│   │   ├── MainActivity.java   # App grid, D-pad focus, remote editing
│   │   ├── BannerGenerator.java# 16:9 sideload banner synthesizer & LRU cache
│   │   ├── FocusController.java# Spatial navigation & Move Mode
│   │   ├── TvInputHelper.java  # Live HDMI inputs discovery & switching
│   │   ├── VendorAdapter.java  # TCL, Philips, Sony hardware adapters
│   │   └── OledProtectionService.java # Orbital pixel drift & burn-in guard
│   └── build.sh                # Standalone AAPT2/D8/apksigner build script
├── companion/                  # Cross-Platform Python Companion (Zero pip deps)
│   └── opentv/
│       ├── core/               # ADB client, device state, config, app names & mDNS discovery
│       ├── debloat/            # Safety database, 10-layer guardrails, sync & rollback
│       ├── profiles/           # OEM brand detectors and device profiles
│       ├── tui/                # Interactive ANSI terminal UI & line fallback
│       └── cli.py              # CLI subcommand dispatcher
├── dist/                       # Standalone binaries (opentv.pyz zipapp)
├── scripts/                    # Packaging & native build automation scripts
├── tests/                      # 5-tier test suite (442 tests)
├── docs/                       # In-depth technical documentation
├── rollback.sh                 # Standalone POSIX rollback script
├── rollback.bat                # Standalone Windows Batch rollback script
├── rollback.ps1                # Standalone PowerShell rollback script
├── LICENSE                     # MIT License
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
