"""
Canonical Safety Guardrails Engine according to PROJECT.md Feature F3.6.
Enforces PERSISTENT flag rejection, launcherx shield, IME preservation, and provisioning gates.
"""
from __future__ import annotations
import re
from typing import Set, List, Optional

KNOWN_IMES = {
    "com.google.android.inputmethod.latin",
    "com.android.inputmethod.latin",
    "com.google.android.leanback.ime",
    "com.tcl.inputmethod.international",
}

SETUP_WIZARDS = {
    "com.google.android.tungsten.setupwraith",
    "com.android.provision",
    "com.android.tv.provision",
}

PACKAGE_REGEX = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$")

class GuardrailViolation(Exception):
    """Raised when an operation is blocked by a safety guardrail."""
    pass

class GuardrailsEngine:
    def __init__(self):
        pass

    def validate_package_name(self, package_name: str) -> None:
        if not package_name or not isinstance(package_name, str):
            raise ValueError(f"Package name cannot be empty or non-string: {package_name}")
        if any(c in package_name for c in " ;&$|`'\"<>\\/"):
            raise ValueError(f"Package name contains illegal shell characters: {package_name}")
        # 'android' is the sole allowed single-token framework package
        if package_name != "android" and not PACKAGE_REGEX.match(package_name):
            raise ValueError(f"Malformed package name: {package_name}")

    def can_disable(
        self,
        package_name: str,
        brand_id: str = "generic",
        installed_packages: Optional[Set[str] | List[str]] = None,
        disabled_packages: Optional[Set[str] | List[str]] = None,
        pkg_flags: str = "",
        is_google_tv: bool = False,
        force_google_tv: bool = False,
        device_provisioned: int = 1,
    ) -> bool:
        self.check_can_disable(
            package_name=package_name,
            brand_id=brand_id,
            installed_packages=installed_packages,
            disabled_packages=disabled_packages,
            pkg_flags=pkg_flags,
            is_google_tv=is_google_tv,
            force_google_tv=force_google_tv,
            device_provisioned=device_provisioned,
        )
        return True

    def check_can_disable(
        self,
        package_name: str,
        brand_id: str = "generic",
        installed_packages: Optional[Set[str] | List[str]] = None,
        disabled_packages: Optional[Set[str] | List[str]] = None,
        pkg_flags: str = "",
        is_google_tv: bool = False,
        force_google_tv: bool = False,
        device_provisioned: int = 1,
    ) -> None:
        self.validate_package_name(package_name)

        # 1. PERSISTENT system process shield
        if "PERSISTENT" in pkg_flags:
            raise GuardrailViolation(f"Package {package_name} is marked PERSISTENT and cannot be disabled")

        # 2. Google TV LauncherX Shield
        if package_name == "com.google.android.apps.tv.launcherx" and is_google_tv:
            if not force_google_tv:
                raise GuardrailViolation(
                    "Cannot disable Google TV launcher (launcherx) to prevent bootloops unless explicitly forced"
                )

        # 3. All-IME disable prevention
        installed = set(installed_packages or [])
        disabled = set(disabled_packages or [])
        if package_name in KNOWN_IMES:
            # Count how many other IMEs are installed and not currently disabled
            active_imes = [
                ime for ime in KNOWN_IMES
                if (not installed or ime in installed) and (ime not in disabled) and (ime != package_name)
            ]
            if len(active_imes) == 0:
                raise GuardrailViolation("Cannot disable the last remaining Input Method (keyboard)")

        # 4. Setup Wizard & Provisioning Gate
        if package_name in SETUP_WIZARDS and device_provisioned != 1:
            raise GuardrailViolation(
                f"Cannot disable setup wizard {package_name} when device is not fully provisioned"
            )

        # 5. Core System Shields
        if package_name in ("android", "com.android.systemui", "com.android.settings", "com.android.shell"):
            raise GuardrailViolation(f"Critical core system package {package_name} can never be disabled")
