"""
OpenTV Device Profiles & Brand Detection Heuristics.
PROJECT.md Contract 2:
- IntentDefinition: Encapsulates Android Intents, extra bundles, and fallback keycodes.
- BrandProfile: Brand-specific settings shortcuts, HDMI direct passthrough URIs,
  OLED screensaver protection, and custom guardrails.
- detect_brand_profile: Multi-property getprop heuristics and package signature fallback.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class IntentDefinition:
    """Represents an Android Intent specification for launch or dispatch."""
    action: Optional[str] = None
    component: Optional[str] = None
    category: Optional[str] = None
    data_uri: Optional[str] = None
    flags: int = 0x10000000  # Intent.FLAG_ACTIVITY_NEW_TASK
    extras: Dict[str, Any] = field(default_factory=dict)
    fallback_keycode: Optional[int] = None
    service_call: Optional[str] = None

    def to_am_start_args(self) -> List[str]:
        """Builds an `am start` command argument list for ADB shell dispatch."""
        args: List[str] = ["am", "start"]
        if self.action:
            args.extend(["-a", self.action])
        if self.component:
            args.extend(["-n", self.component])
        if self.category:
            args.extend(["-c", self.category])
        if self.data_uri:
            args.extend(["-d", self.data_uri])
        if self.flags:
            args.extend(["-f", str(self.flags)])
        for k, v in self.extras.items():
            if isinstance(v, bool):
                args.extend(["--ez", k, "true" if v else "false"])
            elif isinstance(v, int):
                args.extend(["--ei", k, str(v)])
            else:
                args.extend(["--es", k, str(v)])
        return args


@dataclass
class BrandProfile:
    """Device profile containing brand settings shortcuts and hardware mappings."""
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

    @classmethod
    def detect(
        cls,
        device_properties: Dict[str, str],
        installed_packages: Optional[Union[Set[str], List[str]]] = None,
    ) -> BrandProfile:
        """Resolves the active BrandProfile matching device properties and packages."""
        return detect_brand_profile(device_properties, installed_packages)

    def get_quick_setting_intent(self, action: str) -> IntentDefinition:
        """Returns the appropriate IntentDefinition for a quick settings tile."""
        action_key = (action or "").lower().strip()
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
        """Returns the direct TV Input passthrough URI for a physical HDMI port."""
        intent = self.hdmi_inputs.get(port_index)
        if intent and intent.data_uri:
            return intent.data_uri
        return f"content://android.media.tv/passthrough/HW{port_index - 1}"

    def get_guardrails(self) -> List[str]:
        """Returns the list of custom guardrails associated with this profile."""
        return list(self.custom_guardrails)


# Canonical Profile Instances
SONY_PROFILE = BrandProfile(
    brand_id="sony",
    display_name="Sony BRAVIA Android / Google TV",
    settings_intent=IntentDefinition(
        component="com.sony.dtv.settings/.SettingsMainActivity", fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        action="android.settings.DISPLAY_SETTINGS",
        component="com.sony.dtv.settings/.picture.PictureSettingsActivity",
        fallback_keycode=26,
    ),
    sound_intent=IntentDefinition(
        action="android.settings.SOUND_SETTINGS",
        component="com.sony.dtv.settings/.sound.SoundSettingsActivity",
        fallback_keycode=26,
    ),
    inputs_intent=IntentDefinition(
        component="com.sony.dtv.tvx/.MainActivity", fallback_keycode=178
    ),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    hdmi_inputs={
        1: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW0",
        ),
        2: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW1",
        ),
        3: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW2",
        ),
        4: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.sony.dtv.tvinput.hdmi%2F.HDMIInputService%2FHW3",
        ),
    },
    custom_guardrails=["launcherx_shield", "sony_tvx_shield"],
)

TCL_PROFILE = BrandProfile(
    brand_id="tcl",
    display_name="TCL Android / Google TV",
    settings_intent=IntentDefinition(
        action="android.settings.SETTINGS", fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        service_call="com.tcl.settings.SHOW_WINDOW",
        extras={"Type": "picture"},
        fallback_keycode=26,
    ),
    sound_intent=IntentDefinition(
        service_call="com.tcl.settings.SHOW_WINDOW",
        extras={"Type": "SoundPreset"},
        fallback_keycode=26,
    ),
    inputs_intent=IntentDefinition(
        action="android.intent.action.VIEW",
        component="com.tcl.suspension/.SuspensionActivity",
        fallback_keycode=178,
    ),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    hdmi_inputs={
        1: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW1",
        ),
        2: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW2",
        ),
        3: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/com.tcl.tvinput%2F.TvInputService%2FHW3",
        ),
    },
    custom_guardrails=["tcl_suspension_shield"],
)

PHILIPS_PROFILE = BrandProfile(
    brand_id="philips",
    display_name="Philips (TP Vision) Android TV",
    settings_intent=IntentDefinition(
        action="android.settings.SETTINGS", fallback_keycode=176
    ),
    picture_intent=IntentDefinition(
        action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26
    ),
    sound_intent=IntentDefinition(
        action="android.settings.SOUND_SETTINGS", fallback_keycode=26
    ),
    inputs_intent=IntentDefinition(
        action="android.intent.action.VIEW",
        component="org.droidtv.playtv/.PlayTvActivity",
        fallback_keycode=178,
    ),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    hdmi_inputs={
        1: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW5",
        ),
        2: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW6",
        ),
        3: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW7",
        ),
        4: IntentDefinition(
            action="android.intent.action.VIEW",
            data_uri="content://android.media.tv/passthrough/org.droidtv.playtv%2F.TvInputService%2FHW8",
        ),
    },
    requires_home_focus_test=True,
    home_router_package="org.droidtv.homeintentresolver",
    custom_guardrails=["philips_homeintent_shield", "philips_xtv_shield"],
)

HISENSE_PROFILE = BrandProfile(
    brand_id="hisense",
    display_name="Hisense Android / Google TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.intent.action.VIEW", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["hisense_jamdeo_shield"],
)

XIAOMI_PROFILE = BrandProfile(
    brand_id="xiaomi",
    display_name="Xiaomi Mi TV / PatchWall",
    settings_intent=IntentDefinition(
        component="com.xiaomi.mitv.settings/.MainActivity", fallback_keycode=176
    ),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.intent.action.VIEW", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["xiaomi_input_shield"],
)

CCWGTV_PROFILE = BrandProfile(
    brand_id="ccwgtv",
    display_name="Chromecast with Google TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["launcherx_shield", "setupwraith_shield"],
)

NVIDIA_PROFILE = BrandProfile(
    brand_id="nvidia",
    display_name="Nvidia SHIELD TV",
    settings_intent=IntentDefinition(
        component="com.nvidia.shield.settings/.MainActivity", fallback_keycode=176
    ),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=["nvidia_agent_shield"],
)

GENERIC_PROFILE = BrandProfile(
    brand_id="generic",
    display_name="Generic Android TV",
    settings_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=176),
    picture_intent=IntentDefinition(action="android.settings.DISPLAY_SETTINGS", fallback_keycode=26),
    sound_intent=IntentDefinition(action="android.settings.SOUND_SETTINGS", fallback_keycode=26),
    inputs_intent=IntentDefinition(action="android.settings.SETTINGS", fallback_keycode=178),
    screensaver_intent=IntentDefinition(action="android.settings.DREAM_SETTINGS"),
    custom_guardrails=[],
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

OLED_REGEX = re.compile(r"(?i)(oled|a80|a84|a90|a95)")


def detect_brand_profile(
    props: Dict[str, str],
    installed_packages: Optional[Union[Set[str], List[str]]] = None,
) -> BrandProfile:
    """
    Evaluates Android getprop dictionary and package signatures to select BrandProfile.
    Also evaluates model strings for OLED hardware capabilities.
    """
    mfg = props.get("ro.product.manufacturer", "").lower()
    brand = props.get("ro.product.brand", "").lower()
    model = props.get("ro.product.model", "").lower()
    device = props.get("ro.product.device", "").lower()
    pkgs = set(installed_packages or [])

    selected_profile: BrandProfile

    # 1. Chromecast with Google TV
    if "google" in mfg and ("sabrina" in device or "boreal" in device or "chromecast" in model):
        selected_profile = CCWGTV_PROFILE

    # 2. Nvidia Shield
    elif (
        "nvidia" in mfg
        or "nvidia" in brand
        or any(d in device for d in ["foster", "darcy", "mdarcy", "sif"])
        or "com.nvidia.shield.agent" in pkgs
    ):
        selected_profile = NVIDIA_PROFILE

    # 3. Sony Bravia
    elif (
        "sony" in mfg
        or "sony" in brand
        or any(p in model for p in ["bravia", "kd-", "xr-", "xbr-"])
        or any(pkg.startswith("com.sony.dtv") for pkg in pkgs)
    ):
        selected_profile = SONY_PROFILE

    # 4. Philips (TP Vision)
    elif (
        any(p in mfg for p in ["philips", "tpv", "tp vision"])
        or "philips" in brand
        or "org.droidtv.homeintentresolver" in pkgs
    ):
        selected_profile = PHILIPS_PROFILE

    # 5. TCL
    elif (
        any(p in mfg for p in ["tcl", "tte"])
        or any(p in brand for p in ["tcl", "ffalcon", "iffalcon"])
        or "com.tcl.settings" in pkgs
    ):
        selected_profile = TCL_PROFILE

    # 6. Xiaomi
    elif (
        "xiaomi" in mfg
        or "xiaomi" in brand
        or "redmi" in brand
        or "com.mitv.tvhome" in pkgs
    ):
        selected_profile = XIAOMI_PROFILE

    # 7. Hisense
    elif (
        "hisense" in mfg
        or "jamdeo" in mfg
        or "hisense" in brand
        or "com.jamdeo.tv.common" in pkgs
    ):
        selected_profile = HISENSE_PROFILE

    # 8. Generic Fallback
    else:
        selected_profile = GENERIC_PROFILE

    # Check for OLED burn-in screensaver protection capability
    raw_model = props.get("ro.product.model", "")
    raw_device = props.get("ro.product.device", "")
    if OLED_REGEX.search(raw_model) or OLED_REGEX.search(raw_device) or "oled" in mfg:
        if not selected_profile.has_oled_protection:
            profile_copy = copy.copy(selected_profile)
            profile_copy.has_oled_protection = True
            return profile_copy

    return selected_profile
