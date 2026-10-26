"""
OpenTV Debloat Subpackage: Safety database, guardrails, rollback scripts, and audit logging.
"""

from .database import (
    SafetyCategory,
    PackageEntry,
    CURATED_PACKAGES,
    IMMUTABLE_NEVER_PACKAGES,
    DEFAULT_DEFINITIONS_URL,
    get_definitions_cache_path,
    update_definitions,
    PackageSafetyDB,
)
from .guardrails import (
    GuardrailViolation,
    GuardrailsEngine,
)
from .rollback import (
    RollbackEngine,
)
from .audit import (
    AuditEvent,
    AuditLogger,
)

__all__ = [
    "SafetyCategory",
    "PackageEntry",
    "CURATED_PACKAGES",
    "IMMUTABLE_NEVER_PACKAGES",
    "DEFAULT_DEFINITIONS_URL",
    "get_definitions_cache_path",
    "update_definitions",
    "PackageSafetyDB",
    "GuardrailViolation",
    "GuardrailsEngine",
    "RollbackEngine",
    "AuditEvent",
    "AuditLogger",
]
