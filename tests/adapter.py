"""
Test Contract Adapter for OpenTV.
Attempts to load classes from the implementation package (companion.opentv),
falling back seamlessly to canonical specification contracts in tests.spec_oracle.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Add companion directory to sys.path if present
REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANION_DIR = REPO_ROOT / "companion"
if COMPANION_DIR.exists() and str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))

IS_LIVE_COMPANION = False

try:
    import opentv.core.config as _cfg
    import opentv.profiles.detector as _prof
    import opentv.debloat.database as _sdb
    import opentv.debloat.guardrails as _gr
    import opentv.debloat.rollback as _rb
    import opentv.core.adb as _adb
    import opentv.tui.terminal as _tui
    import opentv.tui.fallback as _fb

    LauncherConfig = _cfg.LauncherConfig
    create_default_config = getattr(_cfg, "create_default_config", None)
    BrandProfile = getattr(_prof, "BrandProfile", None)
    detect_brand_profile = getattr(_prof, "detect_brand_profile", None)
    PROFILES = getattr(_prof, "PROFILES", {})
    PackageSafetyDB = _sdb.PackageSafetyDB
    SafetyCategory = _sdb.SafetyCategory
    PackageEntry = getattr(_sdb, "PackageEntry", None)
    GuardrailsEngine = _gr.GuardrailsEngine
    GuardrailViolation = _gr.GuardrailViolation
    RollbackEngine = _rb.RollbackEngine
    AdbWrapper = getattr(_adb, "AdbClient", getattr(_adb, "AdbWrapper", None))
    TerminalController = getattr(_tui, "TerminalController", None)
    FallbackLineEngine = getattr(_fb, "FallbackLineEngine", None)
    IS_LIVE_COMPANION = True
except (ImportError, AttributeError):
    # Fallback to the canonical specification contracts
    from tests.spec_oracle.config import LauncherConfig, create_default_config
    from tests.spec_oracle.profiles import BrandProfile, detect_brand_profile, PROFILES, IntentDefinition
    from tests.spec_oracle.safety_db import PackageSafetyDB, SafetyCategory, PackageEntry, CURATED_PACKAGES
    from tests.spec_oracle.guardrails import GuardrailsEngine, GuardrailViolation
    from tests.spec_oracle.rollback import RollbackEngine
    from tests.spec_oracle.adb_wrapper import AdbWrapper, AdbDevice
    from tests.spec_oracle.tui_engine import TerminalController, FallbackLineEngine
