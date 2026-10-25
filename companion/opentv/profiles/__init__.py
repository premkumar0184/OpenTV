"""
OpenTV Device Profiles Subpackage: Brand definitions, intent specs, and heuristic detector.
"""

from .detector import (
    IntentDefinition,
    BrandProfile,
    detect_brand_profile,
    PROFILES,
    SONY_PROFILE,
    TCL_PROFILE,
    PHILIPS_PROFILE,
    HISENSE_PROFILE,
    XIAOMI_PROFILE,
    CCWGTV_PROFILE,
    NVIDIA_PROFILE,
    GENERIC_PROFILE,
)

__all__ = [
    "IntentDefinition",
    "BrandProfile",
    "detect_brand_profile",
    "PROFILES",
    "SONY_PROFILE",
    "TCL_PROFILE",
    "PHILIPS_PROFILE",
    "HISENSE_PROFILE",
    "XIAOMI_PROFILE",
    "CCWGTV_PROFILE",
    "NVIDIA_PROFILE",
    "GENERIC_PROFILE",
]
