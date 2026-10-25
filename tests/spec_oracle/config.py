"""
Canonical LauncherConfig schema, validator, and serializer according to PROJECT.md Contract 1.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

SUPPORTED_SCHEMA_VERSION = 1
DEFAULT_THEME = "OLED_Black"
DEFAULT_APPS = [
    "com.google.android.youtube.tv",
    "com.netflix.ninja",
    "com.plexapp.android"
]
DEFAULT_QUICK_SETTINGS = ["wifi", "bluetooth", "sound", "picture", "settings"]

@dataclass
class HdmiInputConfig:
    id: str
    title: str
    visible: bool = True
    intent_action: Optional[str] = None
    intent_uri: Optional[str] = None

@dataclass
class OledProtectionConfig:
    screensaver_idle_seconds: int = 180
    pixel_shift_enabled: bool = True

@dataclass
class LauncherConfig:
    version: int = SUPPORTED_SCHEMA_VERSION
    apps: List[str] = field(default_factory=lambda: list(DEFAULT_APPS))
    hdmi: List[HdmiInputConfig] = field(default_factory=list)
    quick_settings: List[str] = field(default_factory=lambda: list(DEFAULT_QUICK_SETTINGS))
    theme: str = DEFAULT_THEME
    oled_protection: OledProtectionConfig = field(default_factory=OledProtectionConfig)

    def __post_init__(self):
        # Normalize hdmi list if dicts were passed
        normalized_hdmi = []
        for item in self.hdmi:
            if isinstance(item, dict):
                normalized_hdmi.append(HdmiInputConfig(
                    id=str(item.get("id", "")),
                    title=str(item.get("title", item.get("label", item.get("id", "")))),
                    visible=bool(item.get("visible", True)),
                    intent_action=item.get("intent_action"),
                    intent_uri=item.get("intent_uri"),
                ))
            else:
                normalized_hdmi.append(item)
        self.hdmi = normalized_hdmi

        # Normalize oled_protection if dict was passed
        if isinstance(self.oled_protection, dict):
            self.oled_protection = OledProtectionConfig(
                screensaver_idle_seconds=int(self.oled_protection.get("screensaver_idle_seconds", 180)),
                pixel_shift_enabled=bool(self.oled_protection.get("pixel_shift_enabled", True)),
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "apps": list(self.apps),
            "hdmi": [
                {
                    "id": item.id,
                    "title": item.title,
                    "visible": item.visible,
                    **({"intent_action": item.intent_action} if item.intent_action else {}),
                    **({"intent_uri": item.intent_uri} if item.intent_uri else {}),
                }
                for item in self.hdmi
            ],
            "quick_settings": list(self.quick_settings),
            "theme": self.theme,
            "oled_protection": {
                "screensaver_idle_seconds": self.oled_protection.screensaver_idle_seconds,
                "pixel_shift_enabled": self.oled_protection.pixel_shift_enabled,
            }
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LauncherConfig:
        if not isinstance(data, dict):
            raise ValueError(f"Config must be a JSON object, got {type(data).__name__}")
        
        # Handle empty dict gracefully with defaults
        if not data:
            return cls()

        # Schema version check
        version = data.get("version", data.get("schema_version", SUPPORTED_SCHEMA_VERSION))
        if not isinstance(version, int):
            raise ValueError(f"version must be an integer, got {type(version).__name__}")
        if version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"Unsupported config schema version: {version}. Expected: {SUPPORTED_SCHEMA_VERSION}")

        # Apps check
        apps_raw = data.get("apps", DEFAULT_APPS)
        if not isinstance(apps_raw, list):
            raise ValueError(f"apps must be a list of package strings, got {type(apps_raw).__name__}")
        apps: List[str] = []
        for app in apps_raw:
            if isinstance(app, dict):
                # Handle extended app object: {"package_name": ..., "visible": ...}
                pkg = app.get("package_name") or app.get("id") or ""
                if app.get("visible", True) and pkg:
                    apps.append(str(pkg))
            elif isinstance(app, str):
                apps.append(app)
            else:
                raise ValueError(f"Invalid app item type: {type(app).__name__}")

        # HDMI check
        hdmi_raw = data.get("hdmi", data.get("hdmi_inputs", []))
        if not isinstance(hdmi_raw, list):
            raise ValueError(f"hdmi must be a list, got {type(hdmi_raw).__name__}")
        hdmi: List[HdmiInputConfig] = []
        for item in hdmi_raw:
            if not isinstance(item, dict):
                raise ValueError("hdmi items must be objects")
            item_id = str(item.get("id", ""))
            title = str(item.get("title", item.get("label", item_id)))
            visible = bool(item.get("visible", True))
            intent_action = item.get("intent_action")
            intent_uri = item.get("intent_uri")
            hdmi.append(HdmiInputConfig(
                id=item_id,
                title=title,
                visible=visible,
                intent_action=intent_action,
                intent_uri=intent_uri,
            ))

        # Quick settings check
        qs_raw = data.get("quick_settings", DEFAULT_QUICK_SETTINGS)
        if not isinstance(qs_raw, list):
            raise ValueError(f"quick_settings must be a list, got {type(qs_raw).__name__}")
        quick_settings: List[str] = []
        for qs in qs_raw:
            if isinstance(qs, dict):
                if qs.get("visible", True):
                    quick_settings.append(str(qs.get("id", "")))
            elif isinstance(qs, str):
                quick_settings.append(qs)

        # Theme
        theme = str(data.get("theme", DEFAULT_THEME))

        # OLED protection
        oled_raw = data.get("oled_protection", {})
        if not isinstance(oled_raw, dict):
            raise ValueError("oled_protection must be a dict")
        idle_sec = oled_raw.get("screensaver_idle_seconds", 180)
        if not isinstance(idle_sec, int) or idle_sec < 0:
            raise ValueError(f"screensaver_idle_seconds must be a positive integer, got {idle_sec}")
        pixel_shift = bool(oled_raw.get("pixel_shift_enabled", True))
        oled_protection = OledProtectionConfig(
            screensaver_idle_seconds=idle_sec,
            pixel_shift_enabled=pixel_shift,
        )

        return cls(
            version=version,
            apps=apps,
            hdmi=hdmi,
            quick_settings=quick_settings,
            theme=theme,
            oled_protection=oled_protection,
        )

    @classmethod
    def from_json(cls, json_str: str) -> LauncherConfig:
        if not json_str.strip():
            # Handle empty string
            return cls()
        data = json.loads(json_str)
        return cls.from_dict(data)


def create_default_config() -> LauncherConfig:
    return LauncherConfig(
        hdmi=[
            HdmiInputConfig(id="HW5", title="PlayStation 5", visible=True),
            HdmiInputConfig(id="HW6", title="Nintendo Switch", visible=True),
        ]
    )
