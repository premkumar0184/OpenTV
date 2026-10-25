# OpenTV Test Suite Readiness Report (TEST_READY)

**Date**: 2026-10-25  
**Track**: E2E Testing Track (`TRACK_E2E_TESTING`) & Milestone 5 Final Hardening  
**Status**: **READY** (All 5 Tiers Built, Verified, and Operational)  
**Test Runner Engine**: Python standard library `unittest` (Zero external pip dependencies)

---

## 1. Unified Test Runner Commands

All unit, mock, and adversarial tests across all five tiers run out-of-the-box without requiring any pip installations:

```bash
# Execute the complete 5-tier test suite
python3 tests/run_tests.py

# Or via standard Python unittest discovery
python3 -m unittest discover -s tests
```

### Tier-Specific Execution Commands
```bash
# Tier 1: Feature Coverage (Core mechanics, >=5 tests per feature)
python3 tests/run_tests.py --tier 1

# Tier 2: Boundary & Corner Cases (Extreme inputs, guardrails, non-TTY)
python3 tests/run_tests.py --tier 2

# Tier 3: Cross-Feature Combinations (Pairwise & system interactions)
python3 tests/run_tests.py --tier 3

# Tier 4: Real-World Application Scenarios (End-to-end device flows)
python3 tests/run_tests.py --tier 4

# Tier 5: Adversarial Coverage Hardening (Debloat, guardrails, profiles, core ADB, TUI, and CLI)
python3 tests/run_tests.py --tier 5

# Optional: Run with live Android TV emulator integration
python3 tests/run_tests.py --emulator
```

---

## 2. Test Tier Coverage Counts

| Test Tier | Test Module File | Focus & Scope | Test Cases | Status |
|---|---|---|:---:|:---:|
| **Tier 1: Feature Coverage** | `tests/test_tier1_feature_coverage.py` | Config parsing, profile resolution, safety DB categorization, rollback script generation, ADB wrapper, and launcher intent resolution | **35** | **PASS** |
| **Tier 2: Boundary & Corner Cases** | `tests/test_tier2_boundary_cases.py` | Empty config, invalid IP octets/ports, shell injection attempts, all-IME disable prevention, SetupWraith/bootloop guardrails, non-TTY fallbacks, and Windows CRLF paths | **32** | **PASS** |
| **Tier 3: Cross-Feature Combinations** | `tests/test_tier3_combinations.py` | Brand profiles + safe debloat presets, wireless pairing + launcher deployment, config reload + HDMI URIs, and guardrails + audit logging + rollback integration | **7** | **PASS** |
| **Tier 4: Real-World Scenarios** | `tests/test_tier4_scenarios.py` | Simulated fresh TV device provisioning, complete debloat and emergency rollback cycle, and remote D-pad navigation keyevent harness with anti-bounce guard | **5** | **PASS** |
| **Tier 5: Adversarial Hardening** | `tests/test_tier5_adversarial_hardening.py`<br>`tests/test_tier5_core_tui_hardening.py` | White-box adversarial audit covering debloat safety DB gaps, guardrails edge cases, rollback resilience, concurrent audit logging, profile detector heuristics, device manager error paths, launcher deployer recovery, and non-TTY TUI/CLI fallbacks | **156** | **PASS** |
| **TOTAL** | — | **Full OpenTV E2E Test Suite (Tiers 1–5)** | **235** | **100% PASS** |

*(Note: 1 hardware test in Tier 4 gracefully skips when no live Android TV emulator or physical device is attached, per CI design. Python `unittest discover -s tests` also executes 18 launcher adversarial tests for a grand total of 253 tests across all repository test suites).*

---

## 3. Feature Coverage Checklist

### Tier 1: Core Feature Coverage (>= 5 tests per feature)

#### Feature 1: Configuration Schema & Parsing (`TestConfigParsing`)
- [x] **1.1 Default Config Generation**: Validates `version: 1`, default apps list, quick settings, and OLED burn-in protection (`test_default_config_generation`)
- [x] **1.2 JSON Deserialization**: Validates parsing and field population from standard JSON string (`test_parse_valid_json_config`)
- [x] **1.3 Schema Version Enforcement**: Validates serialization and rejection of mismatched schema versions (`test_schema_version_enforcement`)
- [x] **1.4 App Ordering & Visibility**: Strict preservation of application sequence and filtering of hidden items (`test_apps_ordering_and_filtering`)
- [x] **1.5 HDMI & Quick Settings Parsing**: Deserializes custom HDMI labels, IDs, visibility, and quick settings arrays (`test_hdmi_and_quick_settings_parsing`)
- [x] **1.6 OLED Protection Deserialization**: Validates screensaver idle seconds and pixel shift configuration (`test_oled_protection_config_deserialization`)

#### Feature 2: Profile Resolution (`TestProfileResolution`)
- [x] **2.1 Sony Bravia Resolution**: Validates detection via `ro.product.manufacturer`, model regex (`bravia`), and package signatures (`test_detect_sony_bravia_profile`)
- [x] **2.2 TCL Resolution**: Validates detection via manufacturer and `com.tcl.settings` signature (`test_detect_tcl_profile`)
- [x] **2.3 Philips (TP Vision) Resolution**: Validates detection via manufacturer and `org.droidtv.homeintentresolver` (`test_detect_philips_profile`)
- [x] **2.4 Hisense Resolution**: Validates detection via manufacturer and Jamdeo subsystem (`test_detect_hisense_profile`)
- [x] **2.5 Xiaomi / PatchWall Resolution**: Validates detection via brand and `com.mitv.tvhome` (`test_detect_xiaomi_profile`)
- [x] **2.6 CCwGTV & Nvidia Shield Resolution**: Validates detection for Google Sabrina/Boreal and Nvidia Shield Tegra (`test_detect_ccwgtv_and_nvidia`)
- [x] **2.7 Generic Fallback**: Verifies clean fallback to generic profile for unrecognized hardware (`test_detect_generic_fallback`)

#### Feature 3: Safety DB Categorization (`TestSafetyDBCategorization`)
- [x] **3.1 Core AOSP Protection**: Categorizes `android`, `com.android.systemui`, `com.android.settings`, `com.android.shell` as `NEVER` (`test_categorize_core_aosp_as_never`)
- [x] **3.2 Input Method Protection**: Strictly classifies on-screen keyboards (Gboard, AOSP, TCL IME) as `NEVER` (`test_categorize_input_methods_as_never`)
- [x] **3.3 User Features Protection**: Classifies Chromecast (`mediashell`), Assistant (`katniss`), and TalkBack as `KEEP` (`test_categorize_optional_services_as_keep`)
- [x] **3.4 Known Bloat & Ads**: Classifies recommendation ads, Samba TV ACR, and retail demo apps as `SAFE` (`test_categorize_vendor_bloat_as_safe`)
- [x] **3.5 Unknown Package Safety**: Verifies unrecognized packages permanently default to `REVIEW` (`test_categorize_unknown_package_as_review`)
- [x] **3.6 Safe Debloat Candidates**: Filters installed packages to safely select only confirmed `SAFE` items (`test_get_safe_debloat_candidates_filtering`)

#### Feature 4: Reversible Rollback Generation (`TestRollbackGeneration`)
- [x] **4.1 POSIX Shell Script (.sh)**: Generates standalone script with `#!/bin/sh`, `set -e`, and `pm enable` (`test_generate_posix_shell_script`)
- [x] **4.2 Windows CMD Script (.bat)**: Generates standalone batch script with `ERRORLEVEL` checks and `pm enable` (`test_generate_windows_cmd_batch_script`)
- [x] **4.3 Windows PowerShell Script (.ps1)**: Generates robust PowerShell script with parameters and exception handling (`test_generate_windows_powershell_script`)
- [x] **4.4 Notification Listener Restoration**: Re-authorizes `TvNotificationListenerService` when `launcherx` is restored (`test_rollback_launcherx_notification_listener_privilege`)
- [x] **4.5 Multi-Platform Output**: Writes all three scripts to directory with executable POSIX permissions (`test_write_rollback_scripts_to_directory`)

#### Feature 5: ADB Wrapper (`TestAdbWrapper`)
- [x] **5.1 Argument List Safety**: Formats commands as typed string lists, preventing shell injection vulnerabilities (`test_adb_command_list_formatting`)
- [x] **5.2 Device Table Parsing**: Parses `adb devices -l` output into structured `AdbDevice` records (`test_adb_devices_parsing`)
- [x] **5.3 Network Connect & Disconnect**: Formats `adb connect` and `adb disconnect` with IP validation (`test_adb_connect_and_disconnect_formatting`)
- [x] **5.4 Wi-Fi Pairing Wizard**: Formats Android 11+ `adb pair` with numeric pairing code verification (`test_adb_pair_command_formatting`)
- [x] **5.5 Package Listing Parser**: Strips `package:` prefix and produces sorted unique package lists (`test_adb_package_list_parser`)
- [x] **5.6 Shell Subcommand Builders**: Builds `input keyevent` and `am broadcast RELOAD_CONFIG` (`test_adb_shell_command_builder`)

#### Feature 6: Launcher Intent Resolution (`TestLauncherIntentResolution`)
- [x] **6.1 Sony Bravia Quick Settings**: Resolves `com.sony.dtv.settings/.SettingsMainActivity` and keycode 176 (`test_sony_settings_intents_resolution`)
- [x] **6.2 TCL Proprietary Panels**: Resolves `com.tcl.settings.SHOW_WINDOW` with `Type=SoundPreset`/`picture` (`test_tcl_picture_sound_service_calls`)
- [x] **6.3 Philips HDMI Passthrough URIs**: Resolves `org.droidtv.playtv` direct hardware passthrough URIs (`test_philips_hdmi_passthrough_uris`)
- [x] **6.4 Generic Fallbacks**: Resolves standard AOSP `android.settings.SETTINGS` and keycode fallbacks (`test_generic_settings_and_input_fallbacks`)
- [x] **6.5 Guardrail Rules Query**: Reports vendor-specific rules (`launcherx_shield`, `philips_homeintent_shield`) (`test_brand_profile_guardrails_query`)

---

### Tier 2: Boundary & Corner Cases

- [x] **Empty Configuration**: Handles empty string (`""`) and empty dictionary (`{}`) with valid defaults (`test_empty_config_json_string`, `test_empty_config_dict`)
- [x] **Corrupt JSON & Future Versions**: Rejects malformed JSON and unsupported versions (`test_corrupt_json_string`, `test_unsupported_future_version`)
- [x] **Network IP & Port Boundaries**: Rejects octets > 255, non-numeric ports, and out-of-range ports (`test_invalid_ip_octets`, `test_port_boundary_limits`)
- [x] **Shell Injection Payloads**: Rejects semicolons, subshell expansions (`$(...)`), and illegal characters in package names (`test_shell_command_injection_semicolon`, `test_shell_metacharacters`)
- [x] **All-IME Disable Prevention**: Blocks disabling the only keyboard or the last remaining enabled keyboard (`test_disabling_only_installed_ime_is_blocked`, `test_disabling_last_active_ime_is_blocked`)
- [x] **Google TV LauncherX Bootloop Shield**: Blocks disabling `com.google.android.apps.tv.launcherx` on Google TV unless forced (`test_google_tv_launcherx_blocked_without_force`)
- [x] **SetupWraith & Provisioning Guard**: Blocks disabling setup wizards when device is unprovisioned (`test_unprovisioned_device_setupwraith_blocked`)
- [x] **Persistent Package Shield**: Rejects disabling packages with `PERSISTENT` in manifest flags (`test_persistent_flag_package_rejection`)
- [x] **Non-TTY Fallback Engine**: Validates line-prompt fallback when `isatty()` is False (`test_terminal_controller_detects_non_tty`, `test_fallback_line_engine_choice_default`)
- [x] **Windows Paths & Git Bash Safety**: Asserts Windows `.bat` CRLF endings and quotes `/data/local/tmp/...` paths (`test_windows_batch_carriage_returns`, `test_git_bash_device_tmp_path_preservation`)

---

### Tier 3: Cross-Feature Combinations

- [x] **Brand Profile + Safe Debloat Presets**: Verifies safe bloat is removed while brand hardware components remain protected on Sony, TCL, Philips, and Google TV (`test_sony_profile_with_safe_preset`, `test_tcl_profile_with_safe_preset`, `test_philips_profile_with_safe_preset`)
- [x] **Wireless Pairing + Launcher Deployment**: End-to-end simulated handshake: pairing -> connecting -> installing APK -> pushing config -> verifying Home (`test_wireless_pairing_and_deployment_workflow`)
- [x] **Config Reload + TV Input Resolution**: Dynamic config updates with brand profile HDMI URIs and broadcast reload trigger (`test_config_reload_updates_hdmi_passthrough_uris`)
- [x] **Guardrails + Audit Logging + Rollback Integration**: Debloating updates on-device registry `/data/local/tmp/opentv-disabled.txt`, writes JSONL audit logs, generates rollback scripts, and restores device state (`test_debloat_audit_and_rollback_flow`)

---

### Tier 4: Real-World Application Scenarios

- [x] **Simulated Device Provisioning**: Connects to newly detected TV, auto-detects profile, queries apps, pushes config, and verifies Home registration (`test_complete_device_provisioning_lifecycle`)
- [x] **Debloat & Emergency Rollback Cycle**: Scans installed apps, isolates safe bloat, disables packages, writes on-device registry, generates scripts, and executes full restore (`test_full_debloat_and_recovery_cycle`)
- [x] **Remote D-Pad Navigation Harness**: Dispatches remote keyevent sequence (UP, DOWN, LEFT, RIGHT, OK, BACK, HOME) and tests Bug #30 `okDownKey` anti-bounce protection (`test_remote_dpad_key_dispatch_sequence`, `test_ok_down_key_bounce_guard_simulation`)
- [x] **Live Emulator Smoke Check**: Integration hook for live AVD testing (`test_live_emulator_smoke_check`)

---

### Tier 5: Adversarial Coverage Hardening (156 Tests)

#### Module 1: Debloat, Guardrails, Profiles & Rollback (`test_tier5_adversarial_hardening.py` — 66 Tests)
- [x] **Database Adversarial Gaps (`TestDatabaseAdversarialGaps`) (20 tests)**:
  - Custom overrides, corrupted catalog entries, package name casing, duplicate rules, and category serialization.
  - Verification of edge cases in package filtering and stats calculation.
- [x] **Guardrails Adversarial Edge Cases (`TestGuardrailsAdversarialEdgeCases`) (18 tests)**:
  - Complex shell injection vectors (`$()`, `;`, `&&`, `|`, backticks, null bytes, newlines).
  - PERSISTENT flag bypass attempts, launcherx bootloop defense without force flag.
  - SetupWraith unprovisioned device lockdown, single-IME remaining protection, remote control service shielding, and OLED screensaver protection.
- [x] **Rollback Adversarial Resilience (`TestRollbackAdversarialResilience`) (7 tests)**:
  - Standalone script generation across POSIX sh, Windows BAT, and PowerShell ps1.
  - Device registry parsing with whitespace, missing files, empty lists, and special character sanitization.
  - TvNotificationListenerService automatic re-grant privileges on launcherx recovery.
- [x] **Audit Logger Error Paths & Concurrency (`TestAuditLoggerAdversarialErrorPaths`) (10 tests)**:
  - Concurrent thread writes to JSONL and TXT audit logs without interleaved lines.
  - Corrupted log recovery and non-writable directory fallback handling.
- [x] **Profiles Detector Adversarial Heuristics (`TestProfilesDetectorAdversarialHeuristics`) (11 tests)**:
  - Mixed uppercase/lowercase OEM `getprop` outputs, partial regex matches, and missing property fallbacks.
  - Direct hardware HDMI URI resolution and proprietary settings action dispatch mapping across Sony, TCL, Philips, Hisense, Xiaomi, CCwGTV, and Nvidia Shield.

#### Module 2: Core Device, Deployer, TUI & CLI (`test_tier5_core_tui_hardening.py` — 90 Tests)
- [x] **Device Manager & ADB Adversarial (`TestDeviceManagerAdversarial`) (32 tests)**:
  - Multi-device ambiguity error handling, device selection precedence, and offline device filtering.
  - Subprocess timeouts, non-zero return code formatting, and robust wireless pairing code validation.
- [x] **Launcher Deployer Adversarial (`TestLauncherDeployerAdversarial`) (17 tests)**:
  - Missing APK handling, install permission failures, scoped storage fallback paths for `config.json`.
  - Intent broadcast failure handling, and Home activity resolution verification timeouts.
- [x] **TUI Application Adversarial (`TestTuiAppAdversarial`) (23 tests)**:
  - Non-TTY interactive fallback engine execution, empty application lists, ANSI escape sequence sanitization.
  - Remote key navigation simulation, tile selection/reordering state integrity, and quick-setting toggles.
- [x] **CLI & Terminal Controller Adversarial (`TestCliAndTerminalAdversarial`) (18 tests)**:
  - Subcommand parsing edge cases, invalid flag types, missing parameters, and dry-run flag adherence.
  - JSON output formatting compliance for headless scriptable pipelines.

---

## 4. Instructions for Implementing Agents (Milestones M1–M5)

1. **Test-Driven Implementation**: Implementing agents for `M1_LAUNCHER`, `M2_DEBLOAT_PROFILES`, and `M3_COMPANION_CLI_TUI` can continuously verify compliance by running:
   ```bash
   python3 tests/run_tests.py
   ```
2. **Interface Parity**: `tests/adapter.py` seamlessly bridges to `companion.opentv` as modules are implemented. Ensure class names and method signatures adhere to the contracts documented in `PROJECT.md` and `TEST_INFRA.md`.
3. **Milestone M5 Sign-Off**: Milestone M5 achieved full sign-off with all 235 tests in the unified runner (and 253 tests across the entire repository discover harness) executing and passing with 100% standard library compatibility, 30 passing Java unit tests, and a reproducibly verified signed release APK.
