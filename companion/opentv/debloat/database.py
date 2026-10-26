"""
OpenTV Package Safety Database & 4-Tier Catalog.
PROJECT.md Feature F3.1 / Contract 3:
Categorizes Android TV packages across all major OEM brands into:
- NEVER: Critical system framework, boot services, input methods, HDMI drivers.
- KEEP: Optional user features (Chromecast, Assistant, TalkBack, screensavers).
- SAFE: Confirmed vendor bloatware, advertisements, sponsored carousels, telemetry.
- REVIEW: Unrecognized / third-party apps, permanently defaulted to enabled.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class SafetyCategory(str, Enum):
    """4-tier package safety classification."""
    NEVER = "never"   # Critical system service; disabling bricks TV or hardware
    KEEP = "keep"     # Optional user feature (Casting, Assistant, screensaver); keep unless unused
    SAFE = "safe"     # Confirmed vendor bloatware, advertisements, sponsored feeds, telemetry
    REVIEW = "review" # Unrecognized / user application; defaulted to enabled for safety


@dataclass
class PackageEntry:
    """Metadata record for a package within the safety database."""
    package_name: str
    category: SafetyCategory
    human_name: str
    description: str
    brand: str = "generic"
    reasons: List[str] = field(default_factory=list)
    caveats: Optional[str] = None
    service_impact: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize PackageEntry to a dictionary."""
        return {
            "package_name": self.package_name,
            "category": self.category.value if isinstance(self.category, SafetyCategory) else str(self.category),
            "human_name": self.human_name,
            "description": self.description,
            "brand": self.brand,
            "reasons": self.reasons,
            "caveats": self.caveats,
            "service_impact": self.service_impact,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PackageEntry:
        """Construct PackageEntry from a dictionary."""
        cat_raw = data.get("category", "review")
        try:
            category = SafetyCategory(cat_raw)
        except ValueError:
            category = SafetyCategory.REVIEW
        return cls(
            package_name=data["package_name"],
            category=category,
            human_name=data.get("human_name", data["package_name"]),
            description=data.get("description", ""),
            brand=data.get("brand", "generic"),
            reasons=data.get("reasons", []),
            caveats=data.get("caveats"),
            service_impact=data.get("service_impact"),
        )


# Curated catalog across all major brands and core AOSP (100+ packages)
CURATED_PACKAGES: Dict[str, PackageEntry] = {
    # Core Android Platform & AOSP (never)
    "android": PackageEntry("android", SafetyCategory.NEVER, "Android System", "Core OS framework", "generic"),
    "com.android.systemui": PackageEntry("com.android.systemui", SafetyCategory.NEVER, "System UI", "Navigation and status bar", "generic"),
    "com.android.settings": PackageEntry("com.android.settings", SafetyCategory.NEVER, "Settings", "System settings provider", "generic"),
    "com.android.tv.settings": PackageEntry("com.android.tv.settings", SafetyCategory.NEVER, "TV Settings", "Android TV settings UI", "generic"),
    "com.android.providers.settings": PackageEntry("com.android.providers.settings", SafetyCategory.NEVER, "Settings Storage", "System settings SQLite provider", "generic"),
    "com.android.settings.intelligence": PackageEntry("com.android.settings.intelligence", SafetyCategory.NEVER, "Settings Intelligence", "Settings indexing service", "generic"),
    "com.android.shell": PackageEntry("com.android.shell", SafetyCategory.NEVER, "Android Shell", "ADB shell executor", "generic"),
    "com.android.packageinstaller": PackageEntry("com.android.packageinstaller", SafetyCategory.NEVER, "Package Installer", "App installer and permissions", "generic"),
    "com.google.android.packageinstaller": PackageEntry("com.google.android.packageinstaller", SafetyCategory.NEVER, "Google Package Installer", "Google app installer", "generic"),
    "com.google.android.permissioncontroller": PackageEntry("com.google.android.permissioncontroller", SafetyCategory.NEVER, "Permission Controller", "Runtime permission manager", "generic"),
    "com.android.bluetooth": PackageEntry("com.android.bluetooth", SafetyCategory.NEVER, "Bluetooth Service", "Remote controls and audio devices", "generic"),
    "com.android.externalstorage": PackageEntry("com.android.externalstorage", SafetyCategory.NEVER, "External Storage", "USB and external storage access", "generic"),
    "com.android.providers.media": PackageEntry("com.android.providers.media", SafetyCategory.NEVER, "Media Provider", "Indexed media storage", "generic"),
    "com.android.providers.media.module": PackageEntry("com.android.providers.media.module", SafetyCategory.NEVER, "Media Module", "Modular media provider", "generic"),
    "com.android.providers.downloads": PackageEntry("com.android.providers.downloads", SafetyCategory.NEVER, "Download Manager", "System download provider", "generic"),
    "com.android.keychain": PackageEntry("com.android.keychain", SafetyCategory.NEVER, "Key Chain", "System certificate store", "generic"),
    "com.android.inputdevices": PackageEntry("com.android.inputdevices", SafetyCategory.NEVER, "Input Devices", "Remote buttons translation", "generic"),
    "com.android.location.fused": PackageEntry("com.android.location.fused", SafetyCategory.NEVER, "Fused Location", "Hardware location provider", "generic"),
    "com.android.se": PackageEntry("com.android.se", SafetyCategory.NEVER, "Secure Element", "Hardware crypto keystore", "generic"),
    "com.android.providers.tv": PackageEntry("com.android.providers.tv", SafetyCategory.NEVER, "TV Provider", "HDMI passthrough and tuner database", "generic"),
    "com.android.networkstack.inprocess": PackageEntry("com.android.networkstack.inprocess", SafetyCategory.NEVER, "Network Stack", "Wi-Fi and IP connectivity", "generic"),
    "com.android.networkstack.permissionconfig": PackageEntry("com.android.networkstack.permissionconfig", SafetyCategory.NEVER, "Network Permission Config", "Network permissions", "generic"),
    "com.android.certinstaller": PackageEntry("com.android.certinstaller", SafetyCategory.NEVER, "Certificate Installer", "X509 security cert installer", "generic"),
    "com.android.companiondevicemanager": PackageEntry("com.android.companiondevicemanager", SafetyCategory.NEVER, "Companion Device Manager", "Accessory pairing manager", "generic"),
    "com.android.statementservice": PackageEntry("com.android.statementservice", SafetyCategory.NEVER, "Intent Statement Service", "App links verification", "generic"),
    "com.android.vpndialogs": PackageEntry("com.android.vpndialogs", SafetyCategory.NEVER, "VPN Dialogs", "Secure VPN setup dialogs", "generic"),
    "com.android.proxyhandler": PackageEntry("com.android.proxyhandler", SafetyCategory.NEVER, "Proxy Handler", "System network proxy client", "generic"),
    "com.android.pacprocessor": PackageEntry("com.android.pacprocessor", SafetyCategory.NEVER, "PAC Processor", "Proxy auto-config script runner", "generic"),
    "com.android.captiveportallogin": PackageEntry("com.android.captiveportallogin", SafetyCategory.NEVER, "Captive Portal Login", "Wi-Fi web authentication", "generic"),
    "com.dolby.android.audio.service": PackageEntry("com.dolby.android.audio.service", SafetyCategory.NEVER, "Dolby Audio", "Hardware Dolby decoding", "generic"),
    "com.google.android.gms": PackageEntry("com.google.android.gms", SafetyCategory.NEVER, "Google Play Services", "Play APIs and DRM", "generic"),
    "com.google.android.gsf": PackageEntry("com.google.android.gsf", SafetyCategory.NEVER, "Google Services Framework", "Push notifications foundation", "generic"),
    "com.android.vending": PackageEntry("com.android.vending", SafetyCategory.NEVER, "Google Play Store", "App store client", "generic"),
    "com.android.provision": PackageEntry("com.android.provision", SafetyCategory.NEVER, "AOSP Provision", "Initial device provisioning flag", "generic"),
    "com.android.tv.provision": PackageEntry("com.android.tv.provision", SafetyCategory.NEVER, "TV Provision", "Android TV provisioning gate", "generic"),
    "com.android.managedprovisioning": PackageEntry("com.android.managedprovisioning", SafetyCategory.NEVER, "Managed Provisioning", "Enterprise device setup", "generic"),

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
    "com.google.android.tts": PackageEntry("com.google.android.tts", SafetyCategory.KEEP, "Text-to-Speech", "Speech synthesizer", "generic"),
    "com.google.android.webview": PackageEntry("com.google.android.webview", SafetyCategory.KEEP, "Android System WebView", "In-app browser engine", "generic"),
    "com.android.dreams.basic": PackageEntry("com.android.dreams.basic", SafetyCategory.KEEP, "Basic Screensaver", "Burn-in protection screensaver", "generic"),
    "com.google.android.apps.tv.dreamx": PackageEntry("com.google.android.apps.tv.dreamx", SafetyCategory.KEEP, "Google TV Ambient", "Ambient mode screensaver", "generic"),
    "com.google.android.tv.remote.service": PackageEntry("com.google.android.tv.remote.service", SafetyCategory.KEEP, "Android TV Remote", "Mobile app remote service", "generic"),

    # Safe Generic / Google bloatware (safe)
    "com.google.android.tvrecommendations": PackageEntry("com.google.android.tvrecommendations", SafetyCategory.SAFE, "TV Recommendations", "Sponsored home carousel ads", "generic"),
    "com.google.android.backdrop": PackageEntry("com.google.android.backdrop", SafetyCategory.SAFE, "TV Backdrop Ads", "Sponsored wallpaper promotions", "generic"),
    "com.google.android.videos": PackageEntry("com.google.android.videos", SafetyCategory.SAFE, "Google TV Movies", "Promotional movie store", "generic"),
    "com.google.android.youtube.tvmusic": PackageEntry("com.google.android.youtube.tvmusic", SafetyCategory.SAFE, "YouTube Music TV", "Music streaming bloat", "generic"),
    "com.google.android.play.games": PackageEntry("com.google.android.play.games", SafetyCategory.SAFE, "Google Play Games", "Gaming hub bloatware", "generic"),
    "com.google.android.feedback": PackageEntry("com.google.android.feedback", SafetyCategory.SAFE, "Feedback Reporter", "Bug report telemetry", "generic"),
    "com.android.printspooler": PackageEntry("com.android.printspooler", SafetyCategory.SAFE, "Print Spooler", "Unnecessary printer service on TV", "generic"),
    "com.android.htmlviewer": PackageEntry("com.android.htmlviewer", SafetyCategory.SAFE, "HTML Viewer", "Static HTML viewer", "generic"),
    "com.android.soundpicker": PackageEntry("com.android.soundpicker", SafetyCategory.SAFE, "Sound Picker", "Ringtone picker on TV", "generic"),

    # Sony Bravia Specific (never & safe)
    "com.sony.dtv.tvx": PackageEntry("com.sony.dtv.tvx", SafetyCategory.NEVER, "Sony Live TV / HDMI", "Core HDMI input manager", "sony"),
    "com.sony.dtv.tvinput": PackageEntry("com.sony.dtv.tvinput", SafetyCategory.NEVER, "Sony TV Input", "Hardware HDMI service", "sony"),
    "com.sony.braviasync": PackageEntry("com.sony.dtv.braviasync", SafetyCategory.NEVER, "BRAVIA Sync", "HDMI-CEC control", "sony"),
    "com.sony.dtv.braviasync": PackageEntry("com.sony.dtv.braviasync", SafetyCategory.NEVER, "BRAVIA Sync Service", "HDMI-CEC service", "sony"),
    "com.sony.dtv.remotepairing": PackageEntry("com.sony.dtv.remotepairing", SafetyCategory.NEVER, "Sony Remote Pairing", "Bluetooth remote pairing", "sony"),
    "com.sony.dtv.rcpowerkey": PackageEntry("com.sony.dtv.rcpowerkey", SafetyCategory.NEVER, "Sony Power Key Handler", "Power button key handler", "sony"),
    "com.sony.dtv.uinputservice": PackageEntry("com.sony.dtv.uinputservice", SafetyCategory.NEVER, "Sony UInput Service", "Hardware remote input service", "sony"),
    "com.sony.sonysystemservice": PackageEntry("com.sony.sonysystemservice", SafetyCategory.NEVER, "Sony System Service", "Hardware board controller", "sony"),
    "com.sony.dtv.settings": PackageEntry("com.sony.dtv.settings", SafetyCategory.NEVER, "Sony Bravia Settings", "Hardware picture/sound menu", "sony"),
    "com.sony.dtv.systemui": PackageEntry("com.sony.dtv.systemui", SafetyCategory.NEVER, "Sony System UI", "Bravia quick launcher overlay", "sony"),
    "tv.samba.ssm": PackageEntry("tv.samba.ssm", SafetyCategory.SAFE, "Samba TV ACR", "Viewing habit telemetry", "sony"),
    "com.vewd.core.service": PackageEntry("com.vewd.core.service", SafetyCategory.SAFE, "Vewd Core", "Third-party ad and app engine", "sony"),
    "com.sony.dtv.demomode": PackageEntry("com.sony.dtv.demomode", SafetyCategory.SAFE, "Retail Demo", "Store display loop", "sony"),
    "com.sony.dtv.hbbtvlauncher": PackageEntry("com.sony.dtv.hbbtvlauncher", SafetyCategory.SAFE, "HbbTV Launcher", "Broadcast interactive ads", "sony"),
    "com.sony.dtv.airplayapp": PackageEntry("com.sony.dtv.airplayapp", SafetyCategory.SAFE, "AirPlay Receiver", "Optional Apple streaming app", "sony"),
    "com.sony.dtv.videoframeserver": PackageEntry("com.sony.dtv.videoframeserver", SafetyCategory.SAFE, "Video Frame Server", "Retail video streamer", "sony"),

    # TCL Specific (never, keep, & safe)
    "com.tcl.settings": PackageEntry("com.tcl.settings", SafetyCategory.NEVER, "TCL Settings", "Picture & sound hardware settings", "tcl"),
    "com.tcl.suspension": PackageEntry("com.tcl.suspension", SafetyCategory.NEVER, "TCL Source Picker", "Input switching menu", "tcl"),
    "com.tcl.tvinput": PackageEntry("com.tcl.tvinput", SafetyCategory.NEVER, "TCL TV Input", "Hardware tuner/HDMI provider", "tcl"),
    "com.tcl.providers.config": PackageEntry("com.tcl.providers.config", SafetyCategory.NEVER, "TCL Config Provider", "Hardware panel configuration", "tcl"),
    "com.tcl.useragreement": PackageEntry("com.tcl.useragreement", SafetyCategory.NEVER, "TCL User Agreement", "System agreement enforcement", "tcl"),
    "com.tcl.tcl_bt_rcu_service": PackageEntry("com.tcl.tcl_bt_rcu_service", SafetyCategory.NEVER, "TCL Bluetooth RCU", "Remote control connection service", "tcl"),
    "com.tcl.tv": PackageEntry("com.tcl.tv", SafetyCategory.KEEP, "TCL Live TV", "TCL Channel tuner app", "tcl"),
    "com.tcl.micmanager": PackageEntry("com.tcl.micmanager", SafetyCategory.KEEP, "TCL Mic Manager", "Far-field microphone driver", "tcl"),
    "com.tcl.waterfall.overseas": PackageEntry("com.tcl.waterfall.overseas", SafetyCategory.SAFE, "TCL Waterfall Feed", "Promotional ad banner feed", "tcl"),
    "com.tcl.esticker": PackageEntry("com.tcl.esticker", SafetyCategory.SAFE, "TCL E-Sticker", "Store feature badges", "tcl"),
    "com.tcl.partnercustomizer": PackageEntry("com.tcl.partnercustomizer", SafetyCategory.SAFE, "TCL Partner Customizer", "Carrier/partner bloat injector", "tcl"),
    "com.tcl.messagebox": PackageEntry("com.tcl.messagebox", SafetyCategory.SAFE, "TCL Message Box", "Marketing notification popups", "tcl"),
    "com.tcl.smartalexa": PackageEntry("com.tcl.smartalexa", SafetyCategory.SAFE, "TCL Alexa Integration", "Optional Alexa bridge", "tcl"),
    "com.tcl.copydatatotv": PackageEntry("com.tcl.copydatatotv", SafetyCategory.SAFE, "TCL Migration Tool", "Setup data transfer tool", "tcl"),
    "com.tcl.audioplayer": PackageEntry("com.tcl.audioplayer", SafetyCategory.SAFE, "TCL Audio Player", "Stock USB audio player", "tcl"),
    "com.tcl.imageplayer": PackageEntry("com.tcl.imageplayer", SafetyCategory.SAFE, "TCL Image Player", "Stock USB image gallery", "tcl"),
    "com.tcl.videoplayer": PackageEntry("com.tcl.videoplayer", SafetyCategory.SAFE, "TCL Video Player", "Stock USB video player", "tcl"),
    "com.tcl.keyhelp": PackageEntry("com.tcl.keyhelp", SafetyCategory.SAFE, "TCL Remote Guide", "Remote helper overlay", "tcl"),
    "com.tcl.usercenter": PackageEntry("com.tcl.usercenter", SafetyCategory.SAFE, "TCL Account Center", "TCL Cloud account prompt", "tcl"),
    "com.tcl.dashboard": PackageEntry("com.tcl.dashboard", SafetyCategory.SAFE, "TCL Dashboard Feed", "Promotional dashboard panel", "tcl"),
    "com.tcl.ttvs": PackageEntry("com.tcl.ttvs", SafetyCategory.SAFE, "TCL TTVS Assistant", "TCL voice promotion app", "tcl"),
    "com.tcl.factory.view": PackageEntry("com.tcl.factory.view", SafetyCategory.SAFE, "TCL Factory Mode", "Factory test utility", "tcl"),

    # Philips Specific (never & safe)
    "org.droidtv.homeintentresolver": PackageEntry("org.droidtv.homeintentresolver", SafetyCategory.NEVER, "Philips Home Router", "Routes remote Home key", "philips"),
    "org.droidtv.GlobalKey": PackageEntry("org.droidtv.GlobalKey", SafetyCategory.NEVER, "Philips Global Key", "Hardware button event mapper", "philips"),
    "org.droidtv.playtv": PackageEntry("org.droidtv.playtv", SafetyCategory.NEVER, "Philips PlayTV", "HDMI passthrough switching", "philips"),
    "org.droidtv.hdmiservice": PackageEntry("org.droidtv.hdmiservice", SafetyCategory.NEVER, "Philips HDMI Service", "Hardware HDMI CEC / ARC service", "philips"),
    "org.droidtv.channels": PackageEntry("org.droidtv.channels", SafetyCategory.NEVER, "Philips Channel Database", "Tuner channel provider", "philips"),
    "org.droidtv.tvsystemui": PackageEntry("org.droidtv.tvsystemui", SafetyCategory.NEVER, "Philips TV System UI", "OSD menu system overlay", "philips"),
    "org.droidtv.tvpowermanagerservice": PackageEntry("org.droidtv.tvpowermanagerservice", SafetyCategory.NEVER, "Philips Power Service", "Power state manager", "philips"),
    "org.droidtv.tv.tptvservice": PackageEntry("org.droidtv.tv.tptvservice", SafetyCategory.NEVER, "Philips TP TV Service", "Panel timing controller", "philips"),
    "org.droidtv.settings": PackageEntry("org.droidtv.settings", SafetyCategory.NEVER, "Philips TV Settings", "Ambilight & picture settings", "philips"),
    "org.droidtv.lkb": PackageEntry("org.droidtv.lkb", SafetyCategory.NEVER, "Philips Local Keyboard", "Physical TV side buttons", "philips"),
    "org.droidtv.xtv": PackageEntry("org.droidtv.xtv", SafetyCategory.NEVER, "Philips xTV Platform", "Hardware platform binder", "philips"),
    "org.droidtv.menudataapp": PackageEntry("org.droidtv.menudataapp", SafetyCategory.NEVER, "Philips Menu Data", "Settings metadata catalog", "philips"),
    "org.droidtv.eum": PackageEntry("org.droidtv.eum", SafetyCategory.NEVER, "Philips EUM User Manual", "Electronic user manual service", "philips"),
    "org.droidtv.aurora": PackageEntry("org.droidtv.aurora", SafetyCategory.NEVER, "Philips Aurora Framework", "Core display driver bridge", "philips"),
    "org.droidtv.demomode": PackageEntry("org.droidtv.demomode", SafetyCategory.SAFE, "Philips Demo Mode", "Retail store loop mode", "philips"),
    "org.droidtv.nettv": PackageEntry("org.droidtv.nettv", SafetyCategory.SAFE, "NetTV Portal", "Legacy smart app gallery", "philips"),
    "org.droidtv.philipstvcollection": PackageEntry("org.droidtv.philipstvcollection", SafetyCategory.SAFE, "Philips TV Collection", "Sponsored recommendations", "philips"),

    # Hisense Specific (never & safe)
    "com.jamdeo.tv.common": PackageEntry("com.jamdeo.tv.common", SafetyCategory.NEVER, "Hisense HAL Service", "Display board interface", "hisense"),
    "com.jamdeo.tv.input": PackageEntry("com.jamdeo.tv.input", SafetyCategory.NEVER, "Hisense TV Input", "Hardware HDMI/tuner bridge", "hisense"),
    "com.hisense.tv.settings": PackageEntry("com.hisense.tv.settings", SafetyCategory.NEVER, "Hisense TV Settings", "Hardware picture settings", "hisense"),
    "com.hisense.service.remote": PackageEntry("com.hisense.service.remote", SafetyCategory.NEVER, "Hisense Remote Service", "Bluetooth remote driver", "hisense"),
    "net.vidaatv.hisense.android.tv": PackageEntry("net.vidaatv.hisense.android.tv", SafetyCategory.SAFE, "Hisense FAST Channels", "Ad-supported stream banners", "hisense"),
    "android.autoinstalls.config.hisense": PackageEntry("android.autoinstalls.config.hisense", SafetyCategory.SAFE, "Partner Auto-installer", "Pushes bloatware", "hisense"),
    "com.hisense.storemode": PackageEntry("com.hisense.storemode", SafetyCategory.SAFE, "Hisense Store Mode", "Retail shop promotional video loop", "hisense"),
    "com.jamdeo.tv.vod": PackageEntry("com.jamdeo.tv.vod", SafetyCategory.SAFE, "Hisense On-Demand Bloat", "Promoted video catalog", "hisense"),

    # Xiaomi Specific (never, keep, & safe)
    "com.xiaomi.mitv.settings": PackageEntry("com.xiaomi.mitv.settings", SafetyCategory.NEVER, "Mi TV Settings", "Picture & sound hardware settings", "xiaomi"),
    "com.mitv.inputservice": PackageEntry("com.mitv.inputservice", SafetyCategory.NEVER, "Mi TV Input Service", "Hardware HDMI switcher", "xiaomi"),
    "com.mitv.remoteservice": PackageEntry("com.mitv.remoteservice", SafetyCategory.NEVER, "Mi Remote Service", "Bluetooth remote control pairing", "xiaomi"),
    "com.mitv.tvhome": PackageEntry("com.mitv.tvhome", SafetyCategory.KEEP, "PatchWall Core", "PatchWall home launcher core", "xiaomi"),
    "com.mitv.tvhome.atv": PackageEntry("com.mitv.tvhome.atv", SafetyCategory.KEEP, "PatchWall ATV Bridge", "Android TV home bridge", "xiaomi"),
    "com.mitv.tvhome.michannel": PackageEntry("com.mitv.tvhome.michannel", SafetyCategory.SAFE, "PatchWall Sponsored", "Content recommendation ads", "xiaomi"),
    "com.mitv.tvhome.mitvplus": PackageEntry("com.mitv.tvhome.mitvplus", SafetyCategory.SAFE, "Mi TV+ Channels", "Promotional streaming feed", "xiaomi"),
    "com.xiaomi.mitv.updateservice": PackageEntry("com.xiaomi.mitv.updateservice", SafetyCategory.SAFE, "Mi TV Update Notifier", "Promotional update popup", "xiaomi"),
    "com.xiaomi.mitv.mediaexplorer": PackageEntry("com.xiaomi.mitv.mediaexplorer", SafetyCategory.SAFE, "Mi Media Explorer", "Stock ad-supported file viewer", "xiaomi"),
    "com.mitv.videoplayer": PackageEntry("com.mitv.videoplayer", SafetyCategory.SAFE, "Mi Video Player", "Ad-supported stock video player", "xiaomi"),

    # Google TV & Chromecast with Google TV (never, keep, safe)
    "com.google.android.apps.tv.launcherx": PackageEntry("com.google.android.apps.tv.launcherx", SafetyCategory.NEVER, "Google TV Home", "Stock launcher guarded from bootloop", "google"),
    "com.google.android.tungsten.setupwraith": PackageEntry("com.google.android.tungsten.setupwraith", SafetyCategory.NEVER, "Google TV Setup Wizard", "Setup recovery handler", "google"),
    "com.google.android.tungsten.overscanmouselayer": PackageEntry("com.google.android.tungsten.overscanmouselayer", SafetyCategory.NEVER, "Google TV Overscan Layer", "Display overscan calibration", "google"),
    "com.google.android.apps.nbu.smartconnect.tv": PackageEntry("com.google.android.apps.nbu.smartconnect.tv", SafetyCategory.KEEP, "Google Smart Connect", "Google Home device linking", "google"),

    # Nvidia Shield (never & safe)
    "com.nvidia.shield.agent": PackageEntry("com.nvidia.shield.agent", SafetyCategory.NEVER, "Shield Core Agent", "Shield hardware management daemon", "nvidia"),
    "com.nvidia.tegraremote.server": PackageEntry("com.nvidia.tegraremote.server", SafetyCategory.NEVER, "Shield Remote Server", "Tegra remote pairing service", "nvidia"),
    "com.nvidia.inputdevices": PackageEntry("com.nvidia.inputdevices", SafetyCategory.NEVER, "Shield Controller Service", "Shield gamepad/remote driver", "nvidia"),
    "com.nvidia.sharedstorage": PackageEntry("com.nvidia.sharedstorage", SafetyCategory.NEVER, "Shield Storage Provider", "NAS and USB external storage mount", "nvidia"),
    "com.nvidia.shield.settings": PackageEntry("com.nvidia.shield.settings", SafetyCategory.NEVER, "Shield TV Settings", "AI upscaling & HDMI CEC settings", "nvidia"),
    "com.nvidia.remotelogger": PackageEntry("com.nvidia.remotelogger", SafetyCategory.SAFE, "Shield Remote Logger", "Telemetry uploader", "nvidia"),
    "com.nvidia.tegrazone3": PackageEntry("com.nvidia.tegrazone3", SafetyCategory.SAFE, "TegraZone", "Legacy gaming store ads", "nvidia"),
    "com.nvidia.shield.diagnostics": PackageEntry("com.nvidia.shield.diagnostics", SafetyCategory.SAFE, "Shield Diagnostics", "Background telemetry collection", "nvidia"),
    "com.nvidia.ota": PackageEntry("com.nvidia.ota", SafetyCategory.SAFE, "Shield OTA Notifier", "Promotional OS update banners", "nvidia"),
}

# Critical packages that can NEVER be downgraded to SAFE or KEEP
IMMUTABLE_NEVER_PACKAGES: Set[str] = {
    pkg for pkg, entry in CURATED_PACKAGES.items() if entry.category == SafetyCategory.NEVER
}
IMMUTABLE_NEVER_PACKAGES.update({
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.tv.settings",
    "com.android.shell",
    "com.android.packageinstaller",
    "com.google.android.packageinstaller",
    "com.google.android.permissioncontroller",
    "com.google.android.apps.tv.launcherx",
})

DEFAULT_DEFINITIONS_URL = (
    "https://raw.githubusercontent.com/premkumar0184/OpenTV/main/companion/opentv/debloat/definitions.json"
)


def get_definitions_cache_path() -> Path:
    """
    Returns platform-specific configuration path for cached debloat definitions.
    - Windows: %APPDATA%/OpenTV/definitions.json (fallback ~/.config/opentv/definitions.json)
    - POSIX / macOS: $XDG_CONFIG_HOME/opentv/definitions.json (fallback ~/.config/opentv/definitions.json)
    """
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / "OpenTV" / "definitions.json"
        return Path.home() / "AppData" / "Roaming" / "OpenTV" / "definitions.json"
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "opentv" / "definitions.json"
    return Path.home() / ".config" / "opentv" / "definitions.json"


def update_definitions(
    source: Optional[str] = None,
    cache_path: Optional[Path] = None,
    timeout: float = 10.0,
) -> Tuple[bool, str, int]:
    """
    Downloads or copies debloat definitions and stores them in the cache path.
    Validates JSON schema and enforces immutable NEVER guardrails.
    Returns (success, message, package_count).
    """
    if cache_path is None:
        cache_path = get_definitions_cache_path()

    src = source if source is not None else DEFAULT_DEFINITIONS_URL
    raw_content = ""

    try:
        if src.startswith("http://") or src.startswith("https://"):
            req = urllib.request.Request(
                src,
                headers={"User-Agent": "OpenTV-Companion/1.0 (Python urllib)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_content = resp.read().decode("utf-8")
        else:
            src_path = Path(src)
            if not src_path.is_file():
                return False, f"Source definitions file not found: {src}", 0
            with open(src_path, "r", encoding="utf-8") as f:
                raw_content = f.read()

        data = json.loads(raw_content)
    except urllib.error.URLError as err:
        return False, f"Network error downloading definitions: {err.reason}", 0
    except json.JSONDecodeError as err:
        return False, f"Invalid JSON format in definitions: {err}", 0
    except Exception as err:
        return False, f"Failed to read definitions: {err}", 0

    if not isinstance(data, dict):
        return False, "Definitions root must be a JSON object", 0

    items = data.get("overrides", data.get("packages"))
    if items is None:
        return False, "Definitions must contain 'packages' or 'overrides' key", 0

    valid_entries: List[Dict[str, Any]] = []
    rejected_immutable = 0

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict) or "package_name" not in item:
                continue
            pkg = item["package_name"]
            cat_str = item.get("category", "")
            if pkg in IMMUTABLE_NEVER_PACKAGES and cat_str.lower() != SafetyCategory.NEVER.value:
                rejected_immutable += 1
                continue
            valid_entries.append(item)
    elif isinstance(items, dict):
        for pkg, info in items.items():
            if not isinstance(info, dict):
                continue
            cat_str = info.get("category", "")
            if pkg in IMMUTABLE_NEVER_PACKAGES and cat_str.lower() != SafetyCategory.NEVER.value:
                rejected_immutable += 1
                continue
            item = dict(info)
            item["package_name"] = pkg
            valid_entries.append(item)
    else:
        return False, "'packages' must be a list or dictionary", 0

    if not valid_entries:
        return False, "No valid package definitions found to update", 0

    output_data = {
        "version": data.get("version", "1.0.0"),
        "updated_at": data.get("updated_at", ""),
        "packages": valid_entries,
    }

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = cache_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(cache_path)
    except Exception as err:
        return False, f"Failed to write cache file {cache_path}: {err}", 0

    msg = f"Updated {len(valid_entries)} package definitions"
    if rejected_immutable > 0:
        msg += f" ({rejected_immutable} dangerous overrides blocked by immutable guardrails)"
    return True, msg, len(valid_entries)


class PackageSafetyDB:
    """
    Curated catalog query engine and debloat candidate evaluator.
    Supports brand-scoped queries and user custom JSON overrides.
    """

    def __init__(
        self,
        catalog: Optional[Dict[str, PackageEntry]] = None,
        custom_overrides_path: Optional[Union[str, Path]] = None,
        auto_load_cache: bool = True,
    ):
        if catalog is not None:
            self._catalog: Dict[str, PackageEntry] = dict(catalog)
        else:
            self._catalog = copy.deepcopy(CURATED_PACKAGES)

        if custom_overrides_path:
            self.load_custom_overrides(custom_overrides_path)
        elif auto_load_cache and catalog is None:
            cache_p = get_definitions_cache_path()
            if cache_p.is_file():
                self.load_custom_overrides(cache_p)

    def classify(self, package_name: str, brand_id: str = "generic") -> PackageEntry:
        """
        Classifies a package, returning a PackageEntry.
        If unrecognized, returns a synthetic PackageEntry with category REVIEW.
        """
        if package_name in self._catalog:
            return self._catalog[package_name]
        return PackageEntry(
            package_name=package_name,
            category=SafetyCategory.REVIEW,
            human_name=package_name,
            description="Unrecognized / third-party application",
            brand=brand_id,
        )

    def categorize(self, package_name: str, brand: str = "generic") -> SafetyCategory:
        """Returns the SafetyCategory enum for the given package."""
        return self.classify(package_name, brand).category

    def get_entry(self, package_name: str) -> Optional[PackageEntry]:
        """Returns the raw PackageEntry if cataloged, or None."""
        return self._catalog.get(package_name)

    def is_safe_to_disable(self, package_name: str, brand_id: str = "generic") -> bool:
        """Returns True if package is explicitly categorized as SAFE."""
        return self.classify(package_name, brand_id).category == SafetyCategory.SAFE

    def get_safe_candidates(
        self, installed_packages: List[str], brand_id: str = "generic"
    ) -> List[str]:
        """Filters installed packages, returning only those safe to disable."""
        return [pkg for pkg in installed_packages if self.is_safe_to_disable(pkg, brand_id)]

    def get_safe_debloat_candidates(
        self, installed_packages: List[str], brand: str = "generic"
    ) -> List[str]:
        """Backward-compatible alias for get_safe_candidates()."""
        return self.get_safe_candidates(installed_packages, brand)

    def add_custom_entry(self, entry: PackageEntry, enforce_immutable: bool = True) -> bool:
        """
        Adds or updates a package entry in the catalog.
        Returns False if rejected by immutable NEVER guardrails.
        """
        if enforce_immutable and entry.package_name in IMMUTABLE_NEVER_PACKAGES:
            if entry.category != SafetyCategory.NEVER:
                return False
        self._catalog[entry.package_name] = entry
        return True

    def load_custom_overrides(
        self,
        source: Union[str, Path, Dict[str, Any]],
        enforce_immutable: bool = True,
    ) -> int:
        """
        Loads custom package rules from a JSON file or dictionary.
        Returns the count of entries added/overridden.
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                return 0
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif isinstance(source, dict):
            data = source
        else:
            raise TypeError(f"Expected path or dict, got {type(source).__name__}")

        count = 0
        items = data.get("overrides", data.get("packages", []))
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and "package_name" in item:
                    entry = PackageEntry.from_dict(item)
                    if self.add_custom_entry(entry, enforce_immutable=enforce_immutable):
                        count += 1
        elif isinstance(items, dict):
            for pkg, info in items.items():
                if isinstance(info, dict):
                    info_copy = dict(info)
                    info_copy["package_name"] = pkg
                    entry = PackageEntry.from_dict(info_copy)
                    if self.add_custom_entry(entry, enforce_immutable=enforce_immutable):
                        count += 1
        return count

    def get_packages_by_category(
        self, category: SafetyCategory, brand_id: Optional[str] = None
    ) -> List[PackageEntry]:
        """Returns all entries matching a safety category, optionally filtered by brand."""
        return [
            entry
            for entry in self._catalog.values()
            if entry.category == category
            and (brand_id is None or entry.brand in (brand_id, "generic"))
        ]

    def get_catalog_stats(self) -> Dict[str, Any]:
        """Returns summary counts of catalog entries."""
        stats: Dict[str, int] = {cat.value: 0 for cat in SafetyCategory}
        brands: Dict[str, int] = {}
        for entry in self._catalog.values():
            stats[entry.category.value] += 1
            brands[entry.brand] = brands.get(entry.brand, 0) + 1
        return {"total": len(self._catalog), "by_category": stats, "by_brand": brands}
