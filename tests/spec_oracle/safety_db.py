"""
Canonical PackageSafetyDB and 4-tier safety catalog according to PROJECT.md Contract 3.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class SafetyCategory(str, Enum):
    NEVER = "never"   # Critical system service; disabling bricks TV or hardware
    KEEP = "keep"     # Optional user feature (Casting, Assistant, screensaver); keep unless unused
    SAFE = "safe"     # Confirmed vendor bloatware, advertisements, sponsored feeds, telemetry
    REVIEW = "review" # Unrecognized / user application; defaulted to enabled for safety

@dataclass
class PackageEntry:
    package_name: str
    category: SafetyCategory
    human_name: str
    description: str
    brand: str = "generic"

# Curated catalog across all major brands and core AOSP
CURATED_PACKAGES: Dict[str, PackageEntry] = {
    # Core Android Platform & AOSP (never)
    "android": PackageEntry("android", SafetyCategory.NEVER, "Android System", "Core OS framework", "generic"),
    "com.android.systemui": PackageEntry("com.android.systemui", SafetyCategory.NEVER, "System UI", "Navigation and status bar", "generic"),
    "com.android.settings": PackageEntry("com.android.settings", SafetyCategory.NEVER, "Settings", "System settings provider", "generic"),
    "com.android.tv.settings": PackageEntry("com.android.tv.settings", SafetyCategory.NEVER, "TV Settings", "Android TV settings UI", "generic"),
    "com.android.providers.settings": PackageEntry("com.android.providers.settings", SafetyCategory.NEVER, "Settings Storage", "System settings SQLite provider", "generic"),
    "com.android.shell": PackageEntry("com.android.shell", SafetyCategory.NEVER, "Android Shell", "ADB shell executor", "generic"),
    "com.android.packageinstaller": PackageEntry("com.android.packageinstaller", SafetyCategory.NEVER, "Package Installer", "App installer and permissions", "generic"),
    "com.google.android.packageinstaller": PackageEntry("com.google.android.packageinstaller", SafetyCategory.NEVER, "Google Package Installer", "Google app installer", "generic"),
    "com.google.android.permissioncontroller": PackageEntry("com.google.android.permissioncontroller", SafetyCategory.NEVER, "Permission Controller", "Runtime permission manager", "generic"),
    "com.android.bluetooth": PackageEntry("com.android.bluetooth", SafetyCategory.NEVER, "Bluetooth Service", "Remote controls and audio devices", "generic"),
    "com.android.externalstorage": PackageEntry("com.android.externalstorage", SafetyCategory.NEVER, "External Storage", "USB and external storage access", "generic"),
    "com.android.providers.tv": PackageEntry("com.android.providers.tv", SafetyCategory.NEVER, "TV Provider", "HDMI passthrough and tuner database", "generic"),
    "com.android.networkstack.inprocess": PackageEntry("com.android.networkstack.inprocess", SafetyCategory.NEVER, "Network Stack", "Wi-Fi and IP connectivity", "generic"),
    "com.dolby.android.audio.service": PackageEntry("com.dolby.android.audio.service", SafetyCategory.NEVER, "Dolby Audio", "Hardware Dolby decoding", "generic"),
    "com.google.android.gms": PackageEntry("com.google.android.gms", SafetyCategory.NEVER, "Google Play Services", "Play APIs and DRM", "generic"),
    "com.google.android.gsf": PackageEntry("com.google.android.gsf", SafetyCategory.NEVER, "Google Services Framework", "Push notifications foundation", "generic"),
    "com.android.vending": PackageEntry("com.android.vending", SafetyCategory.NEVER, "Google Play Store", "App store client", "generic"),
    "com.android.inputdevices": PackageEntry("com.android.inputdevices", SafetyCategory.NEVER, "Input Devices", "Remote buttons translation", "generic"),
    
    # Input Methods (never)
    "com.google.android.inputmethod.latin": PackageEntry("com.google.android.inputmethod.latin", SafetyCategory.NEVER, "Gboard TV", "On-screen keyboard", "generic"),
    "com.android.inputmethod.latin": PackageEntry("com.android.inputmethod.latin", SafetyCategory.NEVER, "AOSP Keyboard", "Default fallback keyboard", "generic"),
    "com.google.android.leanback.ime": PackageEntry("com.google.android.leanback.ime", SafetyCategory.NEVER, "Leanback Keyboard", "Legacy TV keyboard", "generic"),
    "com.tcl.inputmethod.international": PackageEntry("com.tcl.inputmethod.international", SafetyCategory.NEVER, "TCL Keyboard", "TCL on-screen keyboard", "tcl"),

    # Optional System Features (keep)
    "com.google.android.apps.mediashell": PackageEntry("com.google.android.apps.mediashell", SafetyCategory.KEEP, "Chromecast Built-in", "Google Cast receiver", "generic"),
    "com.google.android.katniss": PackageEntry("com.google.android.katniss", SafetyCategory.KEEP, "Google Assistant", "Voice search", "generic"),
    "com.google.android.tv.assistant": PackageEntry("com.google.android.tv.assistant", SafetyCategory.KEEP, "Google Assistant TV", "TV voice assistant", "generic"),
    "com.google.android.marvin.talkback": PackageEntry("com.google.android.marvin.talkback", SafetyCategory.KEEP, "TalkBack", "Accessibility screen reader", "generic"),
    "com.google.android.webview": PackageEntry("com.google.android.webview", SafetyCategory.KEEP, "Android System WebView", "In-app browser engine", "generic"),
    "com.android.dreams.basic": PackageEntry("com.android.dreams.basic", SafetyCategory.KEEP, "Basic Screensaver", "Burn-in protection screensaver", "generic"),
    "com.google.android.tv.remote.service": PackageEntry("com.google.android.tv.remote.service", SafetyCategory.KEEP, "Android TV Remote", "Mobile app remote service", "generic"),

    # Sony Bravia Specific (never & safe)
    "com.sony.dtv.tvx": PackageEntry("com.sony.dtv.tvx", SafetyCategory.NEVER, "Sony Live TV / HDMI", "Core HDMI input manager", "sony"),
    "com.sony.dtv.tvinput": PackageEntry("com.sony.dtv.tvinput", SafetyCategory.NEVER, "Sony TV Input", "Hardware HDMI service", "sony"),
    "com.sony.braviasync": PackageEntry("com.sony.dtv.braviasync", SafetyCategory.NEVER, "BRAVIA Sync", "HDMI-CEC control", "sony"),
    "com.sony.dtv.remotepairing": PackageEntry("com.sony.dtv.remotepairing", SafetyCategory.NEVER, "Sony Remote Pairing", "Bluetooth remote pairing", "sony"),
    "tv.samba.ssm": PackageEntry("tv.samba.ssm", SafetyCategory.SAFE, "Samba TV ACR", "Viewing habit telemetry", "sony"),
    "com.sony.dtv.demomode": PackageEntry("com.sony.dtv.demomode", SafetyCategory.SAFE, "Retail Demo", "Store display loop", "sony"),

    # TCL Specific (never & safe)
    "com.tcl.settings": PackageEntry("com.tcl.settings", SafetyCategory.NEVER, "TCL Settings", "Picture & sound hardware settings", "tcl"),
    "com.tcl.suspension": PackageEntry("com.tcl.suspension", SafetyCategory.NEVER, "TCL Source Picker", "Input switching menu", "tcl"),
    "com.tcl.tvinput": PackageEntry("com.tcl.tvinput", SafetyCategory.NEVER, "TCL TV Input", "Hardware tuner/HDMI provider", "tcl"),
    "com.tcl.waterfall.overseas": PackageEntry("com.tcl.waterfall.overseas", SafetyCategory.SAFE, "TCL Waterfall Feed", "Promotional ad banner feed", "tcl"),
    "com.tcl.esticker": PackageEntry("com.tcl.esticker", SafetyCategory.SAFE, "TCL E-Sticker", "Store feature badges", "tcl"),
    "com.tcl.messagebox": PackageEntry("com.tcl.messagebox", SafetyCategory.SAFE, "TCL Message Box", "Marketing notification popups", "tcl"),

    # Philips Specific (never & safe)
    "org.droidtv.homeintentresolver": PackageEntry("org.droidtv.homeintentresolver", SafetyCategory.NEVER, "Philips Home Router", "Routes remote Home key", "philips"),
    "org.droidtv.playtv": PackageEntry("org.droidtv.playtv", SafetyCategory.NEVER, "Philips PlayTV", "HDMI passthrough switching", "philips"),
    "org.droidtv.nettv": PackageEntry("org.droidtv.nettv", SafetyCategory.SAFE, "NetTV Portal", "Legacy smart app gallery", "philips"),
    "org.droidtv.philipstvcollection": PackageEntry("org.droidtv.philipstvcollection", SafetyCategory.SAFE, "Philips TV Collection", "Sponsored recommendations", "philips"),

    # Hisense Specific (never & safe)
    "com.jamdeo.tv.common": PackageEntry("com.jamdeo.tv.common", SafetyCategory.NEVER, "Hisense HAL Service", "Display board interface", "hisense"),
    "net.vidaatv.hisense.android.tv": PackageEntry("net.vidaatv.hisense.android.tv", SafetyCategory.SAFE, "Hisense FAST Channels", "Ad-supported stream banners", "hisense"),
    "android.autoinstalls.config.hisense": PackageEntry("android.autoinstalls.config.hisense", SafetyCategory.SAFE, "Partner Auto-installer", "Pushes bloatware", "hisense"),

    # Xiaomi Specific (never & safe)
    "com.xiaomi.mitv.settings": PackageEntry("com.xiaomi.mitv.settings", SafetyCategory.NEVER, "Mi TV Settings", "Picture & sound hardware settings", "xiaomi"),
    "com.mitv.tvhome.michannel": PackageEntry("com.mitv.tvhome.michannel", SafetyCategory.SAFE, "PatchWall Sponsored", "Content recommendation ads", "xiaomi"),
    "com.mitv.tvhome.mitvplus": PackageEntry("com.mitv.tvhome.mitvplus", SafetyCategory.SAFE, "Mi TV+ Channels", "Promotional streaming feed", "xiaomi"),

    # Google TV & Common Bloat (never/safe)
    "com.google.android.apps.tv.launcherx": PackageEntry("com.google.android.apps.tv.launcherx", SafetyCategory.NEVER, "Google TV Home", "Stock launcher guarded from bootloop", "google"),
    "com.google.android.tungsten.setupwraith": PackageEntry("com.google.android.tungsten.setupwraith", SafetyCategory.NEVER, "Google TV Setup Wizard", "Setup recovery handler", "google"),
    "com.google.android.tvrecommendations": PackageEntry("com.google.android.tvrecommendations", SafetyCategory.SAFE, "TV Recommendations", "Sponsored home carousel ads", "generic"),
    "com.google.android.backdrop": PackageEntry("com.google.android.backdrop", SafetyCategory.SAFE, "TV Backdrop Ads", "Sponsored wallpaper promotions", "generic"),
    "com.nvidia.remotelogger": PackageEntry("com.nvidia.remotelogger", SafetyCategory.SAFE, "Shield Remote Logger", "Telemetry uploader", "nvidia"),
    "com.nvidia.tegrazone3": PackageEntry("com.nvidia.tegrazone3", SafetyCategory.SAFE, "TegraZone", "Legacy gaming store ads", "nvidia"),
}

class PackageSafetyDB:
    def __init__(self, catalog: Optional[Dict[str, PackageEntry]] = None):
        self._catalog = dict(catalog or CURATED_PACKAGES)

    def categorize(self, package_name: str, brand: str = "generic") -> SafetyCategory:
        if package_name in self._catalog:
            return self._catalog[package_name].category
        return SafetyCategory.REVIEW

    def get_entry(self, package_name: str) -> Optional[PackageEntry]:
        return self._catalog.get(package_name)

    def is_safe_to_disable(self, package_name: str) -> bool:
        return self.categorize(package_name) == SafetyCategory.SAFE

    def get_safe_debloat_candidates(self, installed_packages: List[str]) -> List[str]:
        return [pkg for pkg in installed_packages if self.is_safe_to_disable(pkg)]
