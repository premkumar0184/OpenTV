# OpenTV Test Infrastructure & Verification Architecture (TEST_INFRA)

## Overview & Mission

OpenTV is a high-performance, ad-free Android TV launcher and cross-platform companion toolkit designed for rock-solid stability across diverse TV hardware (Sony, TCL, Philips, Hisense, Xiaomi, Chromecast with Google TV, Nvidia Shield, and generic Android TV).

The OpenTV test infrastructure enforces rigorous, requirement-driven verification across all four project tiers:
- **Tier 1**: Core Feature Coverage
- **Tier 2**: Boundary & Corner Cases
- **Tier 3**: Cross-Feature Combinations & Pairwise Interactions
- **Tier 4**: Real-World Application Scenarios & Emulation Harness

---

## 1. Test Philosophy & Quality Principles

### 1.1 Opaque-Box & Requirement-Driven
Tests treat OpenTV modules and external interfaces as opaque systems. Testing is governed by observable inputs, outputs, file artifacts, state transitions, and exit codes rather than private class internals. Tests are derived directly from the explicit contracts specified in `PROJECT.md`, `ORIGINAL_REQUEST.md`, and OEM architectural handoffs.

### 1.2 Authoritative Expected Output Sources
Every test assertion maps back to an authoritative specification:
1. **Configuration Schema**: Standardized JSON configuration draft contract defining `schema_version`, `apps`, `hdmi_inputs`, `quick_settings`, and `settings`.
2. **Android Framework & CDD Contracts**: Official AOSP Package Manager (`pm disable-user --user 0`, `pm enable`), Activity Manager (`am start`, `cmd package set-home-activity`), TV Input Framework (`TvInputManager`, passthrough URIs), and Keyevent definitions.
3. **Reference Analysis (`tv-detox`)**: Proven safety guardrails, including the on-device rollback registry (`/data/local/tmp/opentv-disabled.txt`), `launcherx` bootloop prevention on Google TV, and `PERSISTENT` package rejection.
4. **Hardware Heuristics**: Validated `getprop` tables and OEM intent dispatch signatures for Sony Bravia, TCL, Philips, Hisense, Xiaomi, CCwGTV, and Nvidia Shield.

### 1.3 Zero External Dependencies
To ensure 100% portable out-of-the-box execution across Linux, macOS, and Windows:
- All unit, mock, and scenario tests run using Python's standard library `unittest` runner.
- No `pip install` or external package dependencies (such as `pytest`, `rich`, or `mock`) are required.
- The test harness runs identically via `python3 tests/run_tests.py` or `python3 -m unittest discover -s tests`.

### 1.4 Hermetic Isolation & Cross-Platform Parity
- Each test runs in an isolated temporary sandbox (`tempfile.TemporaryDirectory`) for file generation, config writing, and audit logs.
- Platform differences (POSIX vs Windows path separators, terminal capabilities, ANSI escape processing) are simulated and validated across simulated Linux, macOS, and Windows environments.
- Subprocess executions are intercepted and validated without mutating host system state.

---

## 2. Feature Inventory Mapping to Test Tiers

The following matrix maps every requirement and feature from `PROJECT.md` to its designated verification tier and test suite:

| Feature ID | Feature Name | Description | Test Tier | Primary Test Suite |
|---|---|---|---|---|
| **F1.1** | Launcher Lifecycle & Intent | Home & Leanback intent filters, landscape, singleTask | Tier 1, Tier 4 | `TestLauncherIntentResolution`, `TestSimulatedDeviceProvisioning` |
| **F1.2** | App Grid & Tile Rendering | 6-column grid layout, banner & icon fallbacks | Tier 1, Tier 4 | `TestConfigParsing`, `TestEmulatorRemoteNavigationHarness` |
| **F1.3** | D-Pad Focus & Key Handling | DPAD navigation, scaling, Bug #30 okDownKey filter | Tier 1, Tier 4 | `TestLauncherIntentResolution`, `TestEmulatorRemoteNavigationHarness` |
| **F1.4** | On-Screen Remote Reordering | Tile swapping, SharedPreferences persistence | Tier 1, Tier 3 | `TestConfigParsing`, `TestConfigReloadWithTvInputResolution` |
| **F1.5** | HDMI & Live TV Inputs | TvInputManager passthrough query & fallback dispatch | Tier 1, Tier 3 | `TestLauncherIntentResolution`, `TestConfigReloadWithTvInputResolution` |
| **F1.6** | Clock & Date Indicator | Localized TextClock, layout width safety | Tier 1, Tier 2 | `TestConfigParsing`, `TestEmptyAndMalformedConfig` |
| **F1.7** | Quick Settings Shortcuts | Bluetooth, Audio, Picture, live connectivity tile | Tier 1, Tier 3 | `TestLauncherIntentResolution`, `TestBrandProfileWithDebloatPresets` |
| **F1.8** | Vendor Adaptations | OLED screensaver, TCL panels, Philips resolver | Tier 1, Tier 2, Tier 3 | `TestProfileResolution`, `TestSetupWraithAndBootloopGuardrails` |
| **F1.9** | Dynamic Configuration Engine | Intent extras, pushed JSON, broadcast reload | Tier 1, Tier 3 | `TestConfigParsing`, `TestConfigReloadWithTvInputResolution` |
| **F1.10** | Reproducible Build & Signing | Dual build (Gradle + build.sh), v1/v2/v3 signatures | Tier 4 | `TestSimulatedDeviceProvisioning` |
| **F2.1** | Zero-Dependency Host Execution | Pure Python 3.9+ standard library compatibility | Tier 1, Tier 2 | All Test Suites |
| **F2.2** | Device Connection Engine | USB auto-detect, direct IP, Android 11+ Wi-Fi pair | Tier 1, Tier 2, Tier 3 | `TestAdbWrapper`, `TestNetworkBoundaryAndInvalidIP`, `TestWirelessPairingWithDeployment` |
| **F2.3** | Package Query & Metadata | Package listing (`-3`, `-s`, `-d`), activity query | Tier 1, Tier 2 | `TestAdbWrapper`, `TestMalformedPackageNames` |
| **F2.4** | Cross-Platform Terminal Engine | ANSI VT100 / FallbackLineEngine for non-TTY | Tier 2 | `TestNonTtyFallback` |
| **F2.5** | Home Screen Layout Manager | Checkbox app selection, order, HDMI renaming | Tier 1, Tier 3 | `TestConfigParsing`, `TestBrandProfileWithDebloatPresets` |
| **F2.6** | Launcher Deploy & Home Verify | APK install, config push, set-home-activity | Tier 3, Tier 4 | `TestWirelessPairingWithDeployment`, `TestSimulatedDeviceProvisioning` |
| **F2.7** | Scriptable Non-Interactive CLI | Connect, list-apps, configure, deploy, debloat | Tier 4 | `TestSimulatedDeviceProvisioning`, `TestDebloatRollbackCycle` |
| **F3.1** | Curated Package Safety DB | 4-tier catalog (never, keep, safe, review) | Tier 1, Tier 2 | `TestSafetyDBCategorization`, `TestAllImeDisablePrevention` |
| **F3.2** | Structured Device Profiles | Profiles for 8 brands (Sony, TCL, Philips, etc.) | Tier 1, Tier 3 | `TestProfileResolution`, `TestBrandProfileWithDebloatPresets` |
| **F3.3** | Device Auto-Detection | getprop heuristics & package fallback detection | Tier 1, Tier 2 | `TestProfileResolution`, `TestSetupWraithAndBootloopGuardrails` |
| **F3.4** | Model-Tailored Settings | TCL SHOW_WINDOW, Sony quicklauncher, Philips | Tier 1, Tier 3 | `TestLauncherIntentResolution`, `TestBrandProfileWithDebloatPresets` |
| **F3.5** | Hardware HDMI Passthrough | Direct passthrough URIs for physical HDMI ports | Tier 1, Tier 3 | `TestLauncherIntentResolution`, `TestConfigReloadWithTvInputResolution` |
| **F3.6** | Safety Guardrails Engine | launcherx shield, PERSISTENT check, IME guard | Tier 2, Tier 3 | `TestAllImeDisablePrevention`, `TestSetupWraithAndBootloopGuardrails`, `TestGuardrailsAuditRollbackIntegration` |
| **F3.7** | Reversible Rollback Engine | Standalone rollback.sh, rollback.bat, rollback.ps1 | Tier 1, Tier 4 | `TestRollbackGeneration`, `TestDebloatRollbackCycle` |
| **F3.8** | Structured Audit Logging | JSONL & text logs capturing all modifications | Tier 3, Tier 4 | `TestGuardrailsAuditRollbackIntegration`, `TestDebloatRollbackCycle` |

---

## 3. Test Architecture & Directory Structure

```
tests/
├── __init__.py
├── run_tests.py                         # Unified test runner CLI with tier filtering & metrics
├── adapter.py                           # Contract adapter (bridges tests to opentv or spec oracle)
├── spec_oracle/                         # Authoritative executable specification reference
│   ├── __init__.py
│   ├── config.py                        # Configuration schema validator & serializer
│   ├── profiles.py                      # DeviceProfile models & getprop brand detector
│   ├── safety_db.py                     # 4-tier package safety database & brand catalog
│   ├── guardrails.py                    # Persistent, launcherx, IME, and provisioning guards
│   ├── rollback.py                      # Standalone .sh, .bat, and .ps1 rollback generator
│   ├── adb_wrapper.py                   # Typed AdbClient command builder & response parser
│   └── tui_engine.py                    # TerminalController & FallbackLineEngine abstraction
├── mocks/
│   ├── __init__.py
│   └── mock_adb.py                      # Realistic simulated ADB subprocess runner & device state
├── test_tier1_feature_coverage.py       # Tier 1: Core Feature Coverage (>=5 test cases per feature)
├── test_tier2_boundary_cases.py         # Tier 2: Boundary, Edge Cases, & Security Guardrails
├── test_tier3_combinations.py           # Tier 3: Pairwise & Cross-Feature Integration Tests
└── test_tier4_scenarios.py              # Tier 4: Real-World Scenarios & Emulator Remote Harness
```

### 3.1 Test Tier Specifications

#### Tier 1: Core Feature Coverage
Validates the fundamental mechanics of every core subsystem with at least 5 isolated test cases per feature:
- **Config Parsing**: Default generation, JSON deserialization, schema version validation, app ordering/visibility, HDMI inputs, OLED protection settings.
- **Profile Resolution**: Brand detection heuristics across Sony, TCL, Philips, Hisense, Xiaomi, CCwGTV, Nvidia Shield, and generic fallback.
- **Safety DB Categorization**: Categorization into `never`, `keep`, `safe`, and `review` across core AOSP and OEM packages.
- **Rollback Generation**: Generation of standalone POSIX `.sh`, Windows `.bat`, and PowerShell `.ps1` scripts with `launcherx` notification listener restoration.
- **ADB Wrapper**: Subprocess list argument safety, `adb devices -l` parser, connection formatting, pairing wizard, and command timeouts.
- **Launcher Intent Resolution**: Proprietary settings intents (Sony, TCL), Philips HDMI passthrough URIs, Google TV Home activities, and hardware keycode fallbacks.

#### Tier 2: Boundary & Corner Cases
Pushes inputs to extremes, stress-tests security constraints, and verifies error handling:
- **Empty & Corrupt Configurations**: Missing keys, malformed JSON syntax, invalid schema versions, type mismatches.
- **Network Boundaries & Malformed IPs**: Invalid octets (`999.999.999.999`), missing ports, non-numeric ports, IPv6 formatting, hostname handling.
- **Malformed Package Names & Shell Injections**: Semicolons, shell expansions (`$(rm -rf /)`), spaces, empty strings, null characters.
- **Input Method Guardrails**: Preventing soft-bricking by rejecting disablement of the last remaining active keyboard/IME.
- **Google TV Bootloop Guardrails**: Blocking disablement of `com.google.android.apps.tv.launcherx` unless explicitly forced, verifying `device_provisioned` before touching setup apps, and blocking `PERSISTENT` system apps.
- **Non-TTY Fallback**: Validating standard line-prompt fallback when `isatty()` is False (CI, piped stdin).
- **Cross-Platform Path Formatting**: Windows backslash conversion and Git Bash path mangling protection (`/data/local/tmp` preservation).

#### Tier 3: Cross-Feature Combinations
Tests pairwise and multi-module interactions:
- **Brand Profile + Debloat Presets**: Verifies that applying "Safe Debloat" under Sony Bravia preserves Sony TVX inputs while disabling Samba TV, and under TCL preserves TCL suspension while removing Waterfall ads.
- **Wireless Pairing + Deployment**: Full sequence of Wi-Fi pairing (`adb pair`) -> network connect (`adb connect`) -> APK install -> config push -> Home activity verification.
- **Config Reload + TV Input Resolution**: Validates that updating `config.json` and triggering `org.opentv.launcher.RELOAD_CONFIG` updates physical HDMI URIs matching the active brand profile.
- **Guardrails + Audit Trail + Rollback**: Validates that batch debloating updates the TV on-device registry (`opentv-disabled.txt`), emits structured JSONL audit entries, and generates valid matching rollback scripts.

#### Tier 4: Real-World Application Scenarios
Simulates realistic end-user operational lifecycles:
- **Scenario A (Device Provisioning)**: Simulates connecting to a brand-new TV, auto-detecting brand and model, querying apps, compiling custom config, and deploying OpenTV launcher.
- **Scenario B (Debloat & Rollback Lifecycle)**: Simulates scanning 20+ installed apps, identifying safe vendor bloat, disabling packages, asserting disabled state, and executing the standalone rollback script to restore 100% of packages.
- **Scenario C (Emulator Remote Navigation Harness)**: Simulates remote D-pad key events (UP, DOWN, LEFT, RIGHT, OK, BACK, HOME), verifies focus state transitions, validates Bug #30 `okDownKey` bounce protection, and supports live execution against an Android TV AVD (`Television_1080p`).

---

## 4. Test Execution & Runner Instructions

### 4.1 Running All Unit & Mock Tests (Default)
To execute all test suites across Tiers 1 through 4 in simulated/mock mode:

```bash
python3 tests/run_tests.py
```
Or via standard Python unittest discovery:
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

### 4.2 Filtering by Test Tier
You can execute specific tiers individually:

```bash
# Run Tier 1 only (Core Feature Coverage)
python3 tests/run_tests.py --tier 1

# Run Tier 2 only (Boundary & Corner Cases)
python3 tests/run_tests.py --tier 2

# Run Tier 3 only (Cross-Feature Combinations)
python3 tests/run_tests.py --tier 3

# Run Tier 4 only (Real-World Scenarios)
python3 tests/run_tests.py --tier 4
```

### 4.3 Verbose & Fast-Fail Modes
```bash
# Verbose output showing each test method name and docstring
python3 tests/run_tests.py -v

# Stop immediately on the first failure
python3 tests/run_tests.py --failfast
```

### 4.4 Live Android TV Emulator Integration Testing
To run live end-to-end assertions against a booted Android TV emulator:

```bash
python3 tests/run_tests.py --emulator
```
If an emulator or physical TV is connected via ADB, this will execute live APK installation, config push, `input keyevent` remote simulation, and window focus verification via `dumpsys window`. If no emulator is running, the harness safely skips live hardware steps and logs actionable boot instructions.

---

## 5. Continuous Integration (CI) Standards

1. **Zero Flakiness**: All mock and unit tests must be 100% deterministic, never rely on external network calls, and execute within < 5 seconds.
2. **Standard Output Reporting**: The test runner returns exit code `0` on clean pass and `1` on any failure or error, outputting structured failure traces.
3. **Clean Teardown**: All temporary files, mock processes, and generated scripts are automatically cleaned up in test `tearDown`.
