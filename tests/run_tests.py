#!/usr/bin/env python3
"""
OpenTV Unified Test Suite Runner.
Executes Tier 1 (Feature Coverage), Tier 2 (Boundary & Corner Cases),
Tier 3 (Cross-Feature Combinations), Tier 4 (Real-World Scenarios),
and Tier 5 (Adversarial Coverage Hardening)
using Python's built-in unittest runner without external dependencies.
"""
from __future__ import annotations
import sys
import os
import argparse
import unittest
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

TIER_FILES: dict[int, list[str]] = {
    1: ["test_tier1_feature_coverage.py"],
    2: ["test_tier2_boundary_cases.py"],
    3: ["test_tier3_combinations.py"],
    4: ["test_tier4_scenarios.py"],
    5: [
        "test_tier5_adversarial_hardening.py",
        "test_tier5_core_tui_hardening.py",
    ],
}

TIER_NAMES = {
    1: "Tier 1: Feature Coverage",
    2: "Tier 2: Boundary & Corner Cases",
    3: "Tier 3: Cross-Feature Combinations",
    4: "Tier 4: Real-World Scenarios",
    5: "Tier 5: Adversarial Coverage Hardening",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenTV Unified Test Runner (Tiers 1-5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tests/run_tests.py                 # Run all unit and mock tests across all tiers
  python3 tests/run_tests.py --tier 1        # Run Tier 1 Feature Coverage tests only
  python3 tests/run_tests.py --tier 2        # Run Tier 2 Boundary & Corner Cases only
  python3 tests/run_tests.py --tier 5        # Run Tier 5 Adversarial Coverage Hardening only
  python3 tests/run_tests.py --emulator      # Run with live Android TV emulator integration
  python3 tests/run_tests.py -v              # Verbose test reporting
        """
    )
    parser.add_argument(
        "-t", "--tier",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run tests for a specific tier (1, 2, 3, 4, or 5)"
    )
    parser.add_argument(
        "--emulator",
        action="store_true",
        help="Enable live Android TV emulator / hardware device integration tests"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output with test names"
    )
    parser.add_argument(
        "-f", "--failfast",
        action="store_true",
        help="Stop execution on first failure or error"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.emulator:
        os.environ["OPENTV_RUN_EMULATOR"] = "1"

    # Ensure repo root and tests dir are in sys.path
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(TESTS_DIR) not in sys.path:
        sys.path.insert(0, str(TESTS_DIR))

    print("=" * 70)
    print(" " * 22 + "OpenTV E2E Test Runner")
    print("=" * 70)
    print(f"Working Directory: {REPO_ROOT}")
    print(f"Python Version:    {sys.version.split()[0]}")
    print(f"Runner Engine:     Python unittest (zero external pip dependencies)")
    print(f"Emulator Testing:  {'Enabled (Live ADB)' if args.emulator else 'Disabled (Mock / Simulation Mode)'}")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    selected_tiers = [args.tier] if args.tier else [1, 2, 3, 4, 5]

    tier_suites = {}
    for tier in selected_tiers:
        tier_suite = unittest.TestSuite()
        files = TIER_FILES[tier]
        if isinstance(files, str):
            files = [files]
        for test_file in files:
            loaded = loader.discover(
                start_dir=str(TESTS_DIR),
                pattern=test_file,
                top_level_dir=str(REPO_ROOT)
            )
            tier_suite.addTest(loaded)
        tier_suites[tier] = tier_suite
        suite.addTest(tier_suite)

    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=args.failfast
    )

    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print(" " * 25 + "Test Execution Summary")
    print("=" * 70)

    for tier in selected_tiers:
        count = tier_suites[tier].countTestCases()
        name = TIER_NAMES[tier]
        print(f"  {name:<40}: {count:>3} test cases")

    print("-" * 70)
    print(f"  Total Tests Executed               : {result.testsRun:>3}")
    print(f"  Passed                             : {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped):>3}")
    print(f"  Failures                           : {len(result.failures):>3}")
    print(f"  Errors                             : {len(result.errors):>3}")
    print(f"  Skipped (Hardware/Env)             : {len(result.skipped):>3}")
    print(f"  Execution Time                     : {elapsed:.3f} seconds")
    print("=" * 70)

    if result.wasSuccessful():
        print("  VERDICT: SUCCESS (All selected test suites passed cleanly)")
        print("=" * 70 + "\n")
        return 0
    else:
        print("  VERDICT: FAILURE (One or more tests failed)")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
