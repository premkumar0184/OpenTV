# Project: OpenTV

OpenTV is an open-source, cross-platform toolkit and clean Android TV launcher that allows users to configure and control their smart TV home screen, select visible apps, and manage debloating safely with manufacturer and model-specific profiles, without requiring AI or remote cloud dependencies.

## Architecture

OpenTV is structured into four primary functional components and two execution tracks:

```
OpenTV/
├── app/                                  # R1: Android TV Launcher APK
│   ├── src/main/java/org/opentv/launcher/
│   │   ├── MainActivity.java             # Core Home activity & grid rendering
│   │   ├── ConfigManager.java            # Intent extra, JSON file, and SharedPreferences config
│   │   ├── FocusController.java          # D-pad spatial navigation, elevation, Bug #30 filter
│   │   ├── TvInputHelper.java            # TvInputManager HDMI queries & passthrough dispatch
│   │   ├── VendorAdapter.java            # TCL panels, Philips resolver, Sony/Google TV hooks
│   │   ├── OledProtectionService.java    # Daydream screensaver idle timer & pixel shift
│   │   ├── LineIcon.java                 # Pure Java vector line icon rendering
│   │   └── Strings.java                  # Multi-lingual UI strings
│   ├── src/main/AndroidManifest.xml      # Home intent filter, Leanback launcher, permissions
│   ├── build.gradle                      # Gradle build script (AGP 9.x compatible)
│   └── build.sh                          # Standalone reproducible build script (AAPT2/D8/jar)
│
├── companion/opentv/                     # R2 & R3: Cross-Platform Companion Manager
│   ├── __init__.py
│   ├── __main__.py                       # Entry point: python3 -m opentv
│   ├── cli.py                            # Subcommand parser for non-interactive CLI
│   ├── core/
│   │   ├── adb.py                        # Typed AdbClient (USB, Wi-Fi connect, pair)
│   │   ├── device.py                     # DeviceInfo, PackageInfo, ActivityComponent
│   │   ├── config.py                     # LauncherConfig schema, validator, serializer
│   │   └── deployer.py                   # APK installer, config pusher, Home verifier
│   ├── debloat/                          # R3: Debloat & Guardrails Engine
│   │   ├── database.py                   # 4-tier package safety catalog (never, keep, safe, review)
│   │   ├── guardrails.py                 # Persistent check, launcherx shield, IME guard
│   │   ├── manager.py                    # Package disabling engine (pm disable-user --user 0)
│   │   ├── rollback.py                   # Standalone generator: rollback.sh, rollback.bat, rollback.ps1
│   │   └── audit.py                      # Audit trail logger (audit_log.json, audit_log.txt)
│   ├── profiles/                         # R3: Device Profiles
│   │   ├── detector.py                   # getprop heuristics for brand & model detection
│   │   ├── base.py                       # DeviceProfile base class & intent structures
│   │   └── brands/                       # Sony, TCL, Philips, Hisense, Xiaomi, CCwGTV, Nvidia, Generic
│   └── tui/                              # R2: Interactive Terminal UI
│       ├── terminal.py                   # Cross-platform terminal abstraction (ANSI/VT100)
│       ├── engine.py                     # RawTerminalEngine (POSIX termios + Windows msvcrt)
│       ├── fallback.py                   # FallbackLineEngine (for CI, non-TTY, redirected stdin)
│       └── views/                        # App picker, reorder view, HDMI view, quick settings, debloat view
│
├── tests/                                # R4: Test Suite & Verification Harness
│   ├── unit/                             # Tier 1: Config, profile matcher, safety DB, rollback generator
│   ├── mock/                             # Tier 2: Subprocess mock ADB behavioral tests (Linux/Mac/Win)
│   ├── emulator/                         # Tier 3: Live headless Android TV AVD provisioning & test runner
│   └── conftest.py / runner.py           # Unified test runner
│
└── docs/                                 # Documentation & Guides
    ├── debloat_safety.md
    ├── device_profiles.md
    └── architecture.md
```

## Feature Inventory

Every requirement and discovered feature is enumerated below with its assigned milestone:

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | F1.1 Launcher Identity & Lifecycle | Home & Leanback intent filters, singleTask, landscape orientation, configuration change handling | M1 | Survey / R1 |
| 2 | F1.2 App Grid & Tile Rendering | Clean 6-column grid scaling to 1080p/4K, Leanback banners, glass fallback tiles, OOM-safe bitmap buffer | M1 | Survey / R1 |
| 3 | F1.3 D-Pad Remote Focus & Key Handling | TV remote key handling (DPAD, OK, BACK, MENU), focus ring scaling/elevation, Bug #30 okDownKey filter | M1 | Survey / R1 |
| 4 | F1.4 On-Screen Remote Reordering | Long-press OK / MENU context menu, real-time D-pad tile swapping, persistent SharedPreferences | M1 | Survey / R1 |
| 5 | F1.5 HDMI & Live TV Inputs | TvInputManager passthrough query, custom label loading, OEM fallback dispatch chain | M1 | Survey / R1 |
| 6 | F1.6 Clock & Date Indicator | High-legibility TextClock, localized 12/24h and formatted date, single-digit hour layout safety | M1 | Survey / R1 |
| 7 | F1.7 Quick Settings & Live Connectivity | Top-right shortcuts (Bluetooth, Audio, Picture), live Wi-Fi/Ethernet signal indicator tile | M1 | Survey / R1 |
| 8 | F1.8 Vendor Adaptations | OLED 180s screensaver & pixel shift; TCL picture/sound panel service; Philips resolver; Sony/GTV bootloop shield | M1 | Survey / R1 |
| 9 | F1.9 Dynamic Configuration Engine | 3-tier config: Intent extras with timestamp, pushed JSON (/sdcard/OpenTV/config.json), in-app settings | M1 | Survey / R1 |
| 10 | F1.10 Reproducible Build & Release Signing | Dual build pipeline: Gradle AGP build & standalone build.sh using AAPT2/D8/jar; signed v1/v2/v3 release APK | M1 | Survey / R1 |
| 11 | F2.1 Zero-Dependency Host Execution | Pure Python 3.9+ standard library implementation running without pip dependencies on Linux, macOS, and Windows | M3 | Survey / R2 |
| 12 | F2.2 Device Connection Engine | USB auto-detection, direct IP connect, Android 11+ Wi-Fi pairing wizard (adb pair), timeout safeguards | M3 | Survey / R2 |
| 13 | F2.3 Package Querying & Metadata Resolution | Enumerates user/system packages via ADB, resolves launchable TV apps via intent queries | M3 | Survey / R2 |
| 14 | F2.4 Cross-Platform TUI Engine | RawTerminalEngine ANSI VT100 (termios/tty on POSIX, msvcrt on Windows) + FallbackLineEngine for CI/non-TTY | M3 | Survey / R2 |
| 15 | F2.5 Interactive Home Screen Layout Manager | Interactive checkbox app picker, D-pad reordering (+/-, u/d), HDMI label renaming, quick settings toggles | M3 | Survey / R2 |
| 16 | F2.6 Launcher Deployment & Home Verification | Pushes config JSON, installs APK, configures Home activity via cmd package set-home-activity, Home intent chooser fallback | M3 | Survey / R2 |
| 17 | F2.7 Scriptable Non-Interactive CLI Interface | Subcommands: connect, list-apps, configure, deploy, debloat, rollback for headless automation | M3 | Survey / R2 |
| 18 | F3.1 Curated Package Safety Database | 4-tier classification (never, keep, safe, review) across 8 brand profiles; unrecognized packages default to review | M2 | Survey / R3 |
| 19 | F3.2 Structured Device Profiles | Profiles for Sony, TCL, Philips, Hisense, Xiaomi, CCwGTV, Nvidia Shield, Generic with detection signatures | M2 | Survey / R3 |
| 20 | F3.3 Device Auto-Detection Heuristics | Multi-property extraction via getprop (manufacturer, brand, model, device) + package fallback detection | M2 | Survey / R3 |
| 21 | F3.4 Model-Tailored Settings Shortcuts | Dispatches proprietary OEM settings intents (TCL SHOW_WINDOW, Sony quicklauncher, Philips setup) | M2 | Survey / R3 |
| 22 | F3.5 Hardware HDMI Passthrough Resolution | Generates direct hardware passthrough URIs for physical HDMI ports across OEM frameworks | M2 | Survey / R3 |
| 23 | F3.6 Safety Guardrails Engine | launcherx preservation on Google TV, PERSISTENT flag rejection, provisioning gate, IME/remote preservation, Home focus check | M2 | Survey / R3 |
| 24 | F3.7 Reversible Rollback Engine | Standalone zero-dependency rollback scripts: rollback.sh (Linux/Mac), rollback.bat (CMD), rollback.ps1 (PowerShell), on-device registry | M2 | Survey / R3 |
| 25 | F3.8 Real-Time Structured Audit Logging | Captures every command, timestamp, previous state, and exit code in audit_log.json (JSONL) and audit_log.txt | M2 | Survey / R3 |
| 26 | F4.1 Comprehensive Documentation | README.md developer & user guide, architecture breakdown, debloat safety manual, device profile guide | M4 | Survey / Spec |
| 27 | F4.2 Test Infrastructure & Test Suite Creation | E2E Testing Track: designs test infra (TEST_INFRA.md) and creates 4-tier test suite (unit, mock, emulator) | E2E Track | Survey / R4 |
| 28 | F4.3 E2E Test Suite Execution & Verification | Implementation Track: runs 100% of E2E test suite (Tiers 1-4) across unit, mock, and emulator assertions | M5 | Survey / R4 |
| 29 | F4.4 Adversarial Coverage Hardening | White-box challenger-driven testing (Tier 5) searching for edge cases, race conditions, and error recovery | M5 | Survey / R4 |

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | `M1_LAUNCHER` | Android TV Launcher APK (`org.opentv.launcher`): Grid UI, D-pad navigation, HDMI inputs, quick settings, vendor adaptations, dynamic config, reproducible build & signing | none | DONE |
| M2 | `M2_DEBLOAT_PROFILES` | Device Profiles & Safe Debloating Engine: Package safety DB, brand profiles (8 brands), guardrails engine, standalone rollback script generators, audit logging | none | DONE |
| M3 | `M3_COMPANION_CLI_TUI` | Cross-Platform CLI / TUI Companion Manager: Pure Python ADB client, connection wizard, interactive TUI, layout manager, deployment & Home verification, CLI subcommands | M1, M2 | DONE |
| M4 | `M4_DOCUMENTATION` | Comprehensive Developer & User Documentation: Complete README.md, quickstart, pairing guides, debloat safety guide, profile customization docs | M1, M2, M3 | DONE |
| M5 | `M5_E2E_VERIFICATION_HARDENING` | Pass 100% of E2E test suite published by E2E Testing Track (Tiers 1-4), followed by Tier 5 Adversarial Coverage Hardening | M1, M2, M3, TEST_READY | DONE |
| E2E | `TRACK_E2E_TESTING` | Parallel E2E Testing Track: Test infra design (`TEST_INFRA.md`), 4-tier opaque-box test suite creation, publishes `TEST_READY.md` | none | DONE |
| S1 | `CI_CD_WORKFLOWS` | Comprehensive multi-platform CI matrix testing across Ubuntu, macOS, Windows, and Python 3.8-3.14 + ShellCheck / Lint | none | DONE |
| S2 | `RELEASE_AUTOMATION` | Binary decoupling, signed APK packaging, GitHub Releases automation, and SHA256 checksums | S1 | DONE |
| S3 | `AUTODISCOVERY` | Pure-Python standard library mDNS & SSDP local TV discovery (`companion/opentv/core/discovery.py`) | none | DONE |
| S4 | `APP_METADATA_ENGINE` | Curated app catalog (~350 apps), 9 taxonomy categories, smart tokenizer fallback (`app_names.py`) | none | DONE |
| S5 | `STANDALONE_BINARIES` | Pure standard library `zipapp` packaging (`dist/opentv.pyz`), native binaries build scripts | S4 | DONE |
| S6 | `DYNAMIC_DEFINITIONS` | Remote community sync (`--update-definitions`), JSON schema validator, immutable `NEVER` shield | S2 | DONE |
| S7 | `SIDELOAD_BANNER_GEN` | Native 16:9 landscape banner generator with palette gradient extraction & LRU caching (<54 KB APK) | none | DONE |

## Interface Contracts

### 1. Launcher APK ↔ Configuration Format (`config.json`)
The Launcher loads its layout and visual preferences from JSON:
```json
{
  "version": 1,
  "apps": [
    "com.google.android.youtube.tv",
    "com.netflix.ninja",
    "com.plexapp.android"
  ],
  "hdmi": [
    {"id": "HW5", "title": "PlayStation 5", "visible": true},
    {"id": "HW6", "title": "Nintendo Switch", "visible": true}
  ],
  "quick_settings": ["wifi", "bluetooth", "sound", "picture", "settings"],
  "theme": "OLED_Black",
  "oled_protection": {
    "screensaver_idle_seconds": 180,
    "pixel_shift_enabled": true
  }
}
```
- **Push location**: `/sdcard/Android/data/org.opentv.launcher/files/config.json` or `/sdcard/OpenTV/config.json`.
- **Broadcast reload trigger**: `adb shell am broadcast -a org.opentv.launcher.RELOAD_CONFIG`.
- **Intent extras alternative**: `am start -n org.opentv.launcher/.MainActivity --es apps "pkg1,pkg2" --es quick "wifi,bluetooth" --es theme "OLED_Black" --es stamp "<timestamp>"`.

### 2. Device Profiles ↔ Companion Manager
- `BrandProfile.detect(device_properties: dict[str, str], installed_packages: set[str]) -> BrandProfile`: Resolves the active profile.
- `BrandProfile.get_quick_setting_intent(action: str) -> IntentSpec`: Returns action, component, or fallback keycode.
- `BrandProfile.get_hdmi_uri(port_index: int) -> str`: Returns direct passthrough URI or fallback TV input URI.
- `BrandProfile.get_guardrails() -> list[GuardrailRule]`: Returns device-specific rules (e.g. `launcherx_shield`).

### 3. Debloat Engine ↔ Rollback Generator
- `DebloatManager.disable_packages(packages: list[str], dry_run: bool = False) -> DebloatResult`:
  - Enforces guardrails.
  - Appends to `/data/local/tmp/opentv-disabled.txt` on the TV.
  - Generates standalone `rollback.sh`, `rollback.bat`, `rollback.ps1` in the output/working directory.
  - Writes structured audit event to `audit_log.json`.

## Code Layout

- `app/`: Android TV Native Launcher application (Java, Android SDK, Gradle/standalone build).
- `companion/`: Cross-platform Python companion tool.
  - `companion/opentv/`: Main Python package.
  - `companion/opentv/core/`: ADB client, device models, configuration logic.
  - `companion/opentv/debloat/`: Package safety DB, guardrails, rollback scripts.
  - `companion/opentv/profiles/`: Brand detection and OEM profile definitions.
  - `companion/opentv/tui/`: Cross-platform ANSI terminal presentation layer.
- `tests/`: Automated test suite (unit, mock ADB, and live emulator runner).
- `docs/`: Technical manuals and safety guides.
- `PROJECT.md`: Global project architecture and milestone index.
- `README.md`: Primary user guide and developer documentation.
