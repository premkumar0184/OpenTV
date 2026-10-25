"""
Canonical BrandProfile definitions and brand detection heuristics according to PROJECT.md Contract 2.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set

@dataclass
class IntentDefinition:
    action: Optional[str] = None
    component: Optional[str] = None
    category: Optional[str] = None
    data_uri: Optional[str] = None
    flags: int = 0x10000000  # FLAG_ACTIVITY_NEW_TASK
    extras: Dict[str, Any] = field(default_factory=dict)
    fallback_keycode: Optional[int] = None
    service_call: Optional[str] = None

@dataclass
class BrandProfile:
    brand_id: str
    display_name: str
    settings_intent: IntentDefinition
    picture_intent: IntentDefinition
    sound_intent: IntentDefinition
    inputs_intent: IntentDefinition
    screensaver_intent: IntentDefinition
    hdmi_inputs: Dict[int, IntentDefinition] = field(default_factory=dict)
    has_oled_protection: bool = False
    requires_home_focus_test: bool = False
    home_router_package: Optional[str] = None
    custom_guardrails: List[str] = field(default_factory=list)

    def get_quick_setting_intent(self, action: str) -> IntentDefinition:
        action_key = action.lower()
        if action_key in ("settings", "main_settings"):
            return self.settings_intent
        elif action_key in ("picture", "display"):
            return self.picture_intent
        elif action_key in ("sound", "audio"):
            return self.sound_intent
        elif action_key in ("inputs", "input", "hdmi"):
            return self.inputs_intent
        elif action_key in ("screensaver", "ambient"):
            return self.screensaver_intent
        return IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176)

    def get_hdmi_uri(self, port_index: int) -> str:
        intent = self.hdmi_inputs.get(port_index)
        if intent and intent.data_uri:
            return intent.data_uri
        return f"content://android.media.tv/passthrough/HW{port_index - 1}"

    def get_guardrails(self) -> List[str]:
        return list(self.custom_guardrails)


# Canonical Profile Instances
SONY_PROFILE = BrandProfile(
    brand_id="sony",
    display_name="Sony BRAVIA Android / Google TV",
    settings_intent=IntentDefinition(
        component="com.sony.dtv.settings/.SettingsMainActivity",
        fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        action="android.settings.DISPLAY_SETTINGS",
        component="com.sony.dtv.settings/.picture.PictureSettingsActivity",
        fallback_keycode=26
    ),
    sound_intent=IntentDefinition(
        action="android.settings.SOUND_SETTINGS",
        component="com.sony.dtv.settings/.sound.SoundSettingsActivity",
        fallback_keycode=26
    ),
    inputs_intent=IntentDefinition(
        component="com.sony.dtv.tvx/.MainActivity",
        fallback_keycode=178
    ),
    screensaver_intent=IntentDefinition(
        action="android.settings.DREAM_SETTINGS"
    ),
    hdmi_inputs={
        1: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW0"),
        2: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW1"),
        3: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW2"),
        4: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW3"),
    },
    custom_guardrails=["launcherx_shield", "sony_tvx_shield"]
)

TCL_PROFILE = BrandProfile(
    brand_id="tcl",
    display_name="TCL Android / Google TV",
    settings_intent=IntentDefinition(
        action="android.settings.SETTINGS",
        fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        service_call="com.tcl.settings.SHOW_WINDOW",
        extras={"Type": "picture"},
        fallback_keycode=26
    ),
    sound_intent=IntentDefinition(
        service_call="com.tcl.settings.SHOW_WINDOW",
        extras={"Type": "SoundPreset"},
        fallback_keycode=26
    ),
    inputs_intent=IntentDefinition(
        action="android.intent.action.VIEW",
        component="com.tcl.suspension/.SuspensionActivity",
        fallback_keycode=178
    ),
    screensaver_intent=IntentDefinition(
        action="android.settings.DREAM_SETTINGS"
    ),
    hdmi_inputs={
        1: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW1"),
        2: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW2"),
        3: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW3"),
    },
    custom_guardrails=["tcl_suspension_shield"]
)

PHILIPS_PROFILE = BrandProfile(
    brand_id="philips",
    display_name="Philips (TP Vision) Android TV",
    settings_intent=IntentDefinition(
        action="android.settings.SETTINGS",
        fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        action="android.settings.DISPLAY_SETTINGS",
        fallback_keycode=26
    ),
    sound_intent=IntentDefinition(
        action="android.settings.SOUND_SETTINGS",
        fallback_keycode=26
    ),
    inputs_intent=IntentDefinition(
        action="android.intent.action.VIEW",
        component="org.droidtv.playtv/.PlayTvActivity",
        fallback_keycode=178
    ),
    screensaver_intent=IntentDefinition(
        action="android.settings.DREAM_SETTINGS"
    ),
    hdmi_inputs={
        1: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW5"),
        2: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW6"),
        3: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW7"),
        4: IntentDefinition(action="android.intent.action.VIEW", data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW8"),
    },
    requires_home_focus_test=True,
    home_router_package="org.droidtv.homeintentresolver",
    custom_guardrails=["philips_homeintent_shield", "philips_xtv_shield"]
)

HISENSE_PROFILE = BrandProfile(
    brand_id="hisense",
    display_name="Hisense Android / Google TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.intent.action.VIEW", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["hisense_jamdeo_shield"]
)

XIAOMI_PROFILE = BrandProfile(
    brand_id="xiaomi",
    display_name="Xiaomi Mi TV / PatchWall",
    settings_intent=IntentDefinition(component="com.xiaomi.mitv.settings/.MainActivity", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.intent.action.VIEW", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["xiaomi_input_shield"]
)

CCWGTV_PROFILE = BrandProfile(
    brand_id="ccwgtv",
    display_name="Chromecast with Google TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["launcherx_shield", "setupwraith_shield"]
)

NVIDIA_PROFILE = BrandProfile(
    brand_id="nvidia",
    display_name="Nvidia SHIELD TV",
    settings_intent=IntentDefinition(component="com.nvidia.shield.settings/.MainActivity", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["nvidia_agent_shield"]
)

GENERIC_PROFILE = BrandProfile(
    brand_id="generic",
    display_name="Generic Android TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=[]
)

PROFILES: Dict[str, BrandProfile] = {
    "sony": SONY_PROFILE,
    "tcl": TCL_PROFILE,
    "philips": PHILIPS_PROFILE,
    "hisense": HISENSE_PROFILE,
    "xiaomi": XIAOMI_PROFILE,
    "ccwgtv": CCWGTV_PROFILE,
    "nvidia": NVIDIA_PROFILE,
    "generic": GENERIC_PROFILE,
}

def detect_brand_profile(props: Dict[str, str], installed_packages: Optional[Set[str] | List[str]] = None) -> BrandProfile:
    mfg = props.get("ro.product.manufacturer", "").lower()
    brand = props.get("ro.product.brand", "").lower()
    model = props.get("ro.product.model", "").lower()
    device = props.get("ro.product.device", "").lower()
    pkgs = set(installed_packages or [])

    # 1. Chromecast with Google TV
    if "google" in mfg and ("sabrina" in device or "boreal" in device or "chromecast" in model):
        return CCWGTV_PROFILE

    # 2. Nvidia Shield
    if "nvidia" in mfg or "nvidia" in brand or any(d in device for d in ["foster", "darcy", "mdarcy", "sif"]):
        return NVIDIA_PROFILE

    # 3. Sony Bravia
    if "sony" in mfg or "sony" in brand or any(p in model for p in ["bravia", "kd-", "xr-", "xbr-"]):
        return SONY_PROFILE
    if any(pkg.startswith("com.sony.dtv") for pkg in pkgs):
        return SONY_PROFILE

    # 4. Philips (TP Vision)
    if any(p in mfg for p in ["philips", "tpv", "tp vision"]) or "philips" in brand or "org.droidtv.homeintentresolver" in pkgs:
        return PHILIPS_PROFILE

    # 5. TCL
    if any(p in mfg for p in ["tcl", "tte"]) or any(p in brand for p in ["tcl", "ffalcon", "iffalcon"]):
        return TCL_PROFILE
    if "com.tcl.settings" in pkgs:
        return TCL_PROFILE

    # 6. Xiaomi
    if "xiaomi" in mfg or "xiaomi" in brand or "redmi" in brand or "com.mitv.tvhome" in pkgs:
        return XIAOMI_PROFILE

    # 7. Hisense
    if "hisense" in mfg or "jamdeo" in mfg or "hisense" in brand or "com.jamdeo.tv.common" in pkgs:
        return HISENSE_PROFILE

    # 8. Generic Fallback
    return GENERIC_PROFILE
