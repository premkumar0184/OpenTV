"""
Safety Guardrails Engine for OpenTV Debloating.
PROJECT.md Feature F3.6 / Contract 3:

Enforces:
1. Shell injection prevention and package name validation.
2. PERSISTENT system process shield.
3. Google TV launcherx bootloop protection.
4. Setup wizard & provisioning gatekeeper.
5. All-IME disable prevention (keyboard availability guarantee).
6. Core remote control & Bluetooth service preservation.
7. Philips Home Intent Resolver guard.
8. Core system package hard-block.
9. Package Safety DB (SafetyCategory.NEVER) cross-check.
"""
from __future__ import annotations

import os
import re
from typing import Any, List, Optional, Set, Tuple, Union

PACKAGE_REGEX = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$")
ILLEGAL_SHELL_CHARS = " ;&$|`'\"<>\\/"

KNOWN_IMES: Set[str] = {
    "com.google.android.inputmethod.latin",
    "com.android.inputmethod.latin",
    "com.google.android.leanback.ime",
    "com.tcl.inputmethod.international",
}

SETUP_WIZARDS: Set[str] = {
    "com.google.android.tungsten.setupwraith",
    "com.android.provision",
    "com.android.tv.provision",
    "com.android.managedprovisioning",
}

CORE_REMOTE_SERVICES: Set[str] = {
    "com.android.bluetooth",
    "com.sony.dtv.remotepairing",
    "com.sony.dtv.rcpowerkey",
    "com.sony.dtv.uinputservice",
    "com.tcl.tcl_bt_rcu_service",
    "org.droidtv.GlobalKey",
    "com.hisense.service.remote",
    "com.mitv.remoteservice",
    "com.nvidia.tegraremote.server",
    "com.nvidia.inputdevices",
    "com.android.inputdevices",
}

CORE_SYSTEM_PACKAGES: Set[str] = {
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.tv.settings",
    "com.android.providers.settings",
    "com.android.shell",
    "com.android.packageinstaller",
    "com.google.android.packageinstaller",
    "com.google.android.permissioncontroller",
    "com.google.android.gms",
    "com.google.android.gsf",
}

OLED_SCREENSAVERS: Set[str] = {
    "com.android.dreams.basic",
    "com.google.android.apps.tv.dreamx",
}


class GuardrailViolation(Exception):
    """Raised when an operation is blocked by a safety guardrail."""

    def __init__(
        self,
        message: str,
        package_name: Optional[str] = None,
        rule: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.package_name = package_name
        self.rule = rule


class GuardrailsEngine:
    """
    Evaluates candidate packages against strict safety guardrails
    prior to executing disabling commands.
    """

    def __init__(self, safety_db: Optional[Any] = None) -> None:
        self._safety_db = safety_db

    @property
    def safety_db(self) -> Any:
        if self._safety_db is None:
            try:
                from opentv.debloat.database import PackageSafetyDB
                self._safety_db = PackageSafetyDB()
            except ImportError:
                from .database import PackageSafetyDB
                self._safety_db = PackageSafetyDB()
        return self._safety_db

    def validate_package_name(self, package_name: str) -> None:
        """
        Validates package name syntax and prevents shell command injection.
        """
        if not package_name or not isinstance(package_name, str):
            raise ValueError(f"Package name cannot be empty or non-string: {package_name}")

        if any(c in package_name for c in ILLEGAL_SHELL_CHARS):
            raise ValueError(f"Package name contains illegal shell characters: {package_name}")

        # 'android' is the sole allowed single-token framework package
        if package_name != "android" and not PACKAGE_REGEX.match(package_name):
            raise ValueError(f"Malformed package name: {package_name}")

    def can_disable(
        self,
        package_name: str,
        brand_id: str = "generic",
        installed_packages: Optional[Union[Set[str], List[str]]] = None,
        disabled_packages: Optional[Union[Set[str], List[str]]] = None,
        pkg_flags: str = "",
        is_google_tv: bool = False,
        force_google_tv: bool = False,
        device_provisioned: int = 1,
        is_oled: bool = False,
    ) -> bool:
        """
        Convenience wrapper returning True if package can be disabled,
        or raising GuardrailViolation / ValueError on violation.
        """
        self.check_can_disable(
            package_name=package_name,
            brand_id=brand_id,
            installed_packages=installed_packages,
            disabled_packages=disabled_packages,
            pkg_flags=pkg_flags,
            is_google_tv=is_google_tv,
            force_google_tv=force_google_tv,
            device_provisioned=device_provisioned,
            is_oled=is_oled,
        )
        return True

    def check_can_disable(
        self,
        package_name: str,
        brand_id: str = "generic",
        installed_packages: Optional[Union[Set[str], List[str]]] = None,
        disabled_packages: Optional[Union[Set[str], List[str]]] = None,
        pkg_flags: str = "",
        is_google_tv: bool = False,
        force_google_tv: bool = False,
        device_provisioned: int = 1,
        is_oled: bool = False,
    ) -> None:
        """
        Evaluates all safety guardrails against the specified package.
        """
        # 1. Syntax & Shell Injection Check
        self.validate_package_name(package_name)

        # 2. PERSISTENT System Process Shield
        if "PERSISTENT" in pkg_flags:
            raise GuardrailViolation(
                f"Package {package_name} is marked PERSISTENT and cannot be disabled",
                package_name=package_name,
                rule="persistent_shield",
            )

        # 3. Google TV launcherx Shield
        is_gtv = is_google_tv or brand_id == "ccwgtv"
        forced = force_google_tv or os.environ.get("GOOGLE_TV", "0").lower() in ("1", "true", "yes")
        if package_name == "com.google.android.apps.tv.launcherx" and is_gtv:
            if not forced:
                raise GuardrailViolation(
                    "Cannot disable Google TV launcher (launcherx) to prevent bootloops unless explicitly forced",
                    package_name=package_name,
                    rule="launcherx_shield",
                )

        # 4. Setup Wizard & Provisioning Gate
        if package_name in SETUP_WIZARDS and device_provisioned != 1:
            raise GuardrailViolation(
                f"Cannot disable setup wizard {package_name} when device is not fully provisioned",
                package_name=package_name,
                rule="provisioning_gate",
            )

        # 5. IME / Keyboard Preservation
        installed = set(installed_packages or [])
        disabled = set(disabled_packages or [])
        if package_name in KNOWN_IMES or package_name.endswith(".ime") or ".inputmethod." in package_name:
            if installed:
                candidate_imes = {
                    p for p in installed if p in KNOWN_IMES or p.endswith(".ime") or ".inputmethod." in p
                }
            else:
                candidate_imes = set(KNOWN_IMES)
            active_imes = [p for p in candidate_imes if p not in disabled and p != package_name]
            if len(active_imes) == 0:
                raise GuardrailViolation(
                    "Cannot disable the last remaining Input Method (keyboard)",
                    package_name=package_name,
                    rule="ime_preservation",
                )

        # 6. Core Remote / Bluetooth Services Shield
        if package_name in CORE_REMOTE_SERVICES:
            raise GuardrailViolation(
                f"Cannot disable core remote control or Bluetooth service: {package_name}",
                package_name=package_name,
                rule="remote_service_shield",
            )

        # 7. Philips Home Intent Resolver Shield
        if package_name == "org.droidtv.homeintentresolver":
            raise GuardrailViolation(
                "Cannot disable Philips Home Intent Resolver (org.droidtv.homeintentresolver)",
                package_name=package_name,
                rule="philips_homeintent_shield",
            )

        # 8. OLED Screensaver Shield
        if is_oled and package_name in OLED_SCREENSAVERS:
            raise GuardrailViolation(
                f"Cannot disable screensaver {package_name} on OLED displays to prevent panel burn-in",
                package_name=package_name,
                rule="oled_burnin_shield",
            )

        # 9. Core System Package Shield
        if package_name in ("android", "com.android.systemui", "com.android.settings", "com.android.shell"):
            raise GuardrailViolation(
                f"Critical core system package {package_name} can never be disabled",
                package_name=package_name,
                rule="core_system_shield",
            )

        # 10. Package Safety DB Cross-Check (SafetyCategory.NEVER)
        # Packages in SETUP_WIZARDS, KNOWN_IMES, and launcherx were already validated
        # by their conditional gates above. All other NEVER packages are strictly blocked.
        if (
            package_name not in SETUP_WIZARDS
            and package_name not in KNOWN_IMES
            and package_name != "com.google.android.apps.tv.launcherx"
        ):
            from .database import SafetyCategory
            category = self.safety_db.categorize(package_name, brand=brand_id)
            if category == SafetyCategory.NEVER:
                raise GuardrailViolation(
                    f"Package {package_name} is classified as SafetyCategory.NEVER and cannot be disabled",
                    package_name=package_name,
                    rule="safety_db_never_shield",
                )

    def filter_safe_to_disable(
        self,
        packages: List[str],
        brand_id: str = "generic",
        installed_packages: Optional[Union[Set[str], List[str]]] = None,
        disabled_packages: Optional[Union[Set[str], List[str]]] = None,
        is_google_tv: bool = False,
        force_google_tv: bool = False,
        device_provisioned: int = 1,
        is_oled: bool = False,
    ) -> Tuple[List[str], List[Tuple[str, str]]]:
        """
        Filters a collection of package names, separating permitted packages
        from those blocked by guardrails.

        Returns:
            Tuple of (permitted_packages_list, list_of_(package, violation_reason)_tuples)
        """
        permitted: List[str] = []
        violations: List[Tuple[str, str]] = []

        current_disabled = set(disabled_packages or [])

        for pkg in packages:
            try:
                self.check_can_disable(
                    package_name=pkg,
                    brand_id=brand_id,
                    installed_packages=installed_packages,
                    disabled_packages=current_disabled,
                    is_google_tv=is_google_tv,
                    force_google_tv=force_google_tv,
                    device_provisioned=device_provisioned,
                    is_oled=is_oled,
                )
                permitted.append(pkg)
                current_disabled.add(pkg)
            except (GuardrailViolation, ValueError) as exc:
                violations.append((pkg, str(exc)))

        return permitted, violations

    @staticmethod
    def parse_persistent_flag_from_dumpsys(dumpsys_output: str) -> bool:
        """Extracts whether the PERSISTENT flag is declared in dumpsys package output."""
        for line in dumpsys_output.splitlines():
            if "pkgFlags=" in line or "flags=" in line:
                if "PERSISTENT" in line:
                    return True
        return "PERSISTENT" in dumpsys_output
