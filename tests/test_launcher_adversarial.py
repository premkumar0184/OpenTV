#!/usr/bin/env python3
"""
OpenTV Launcher Logic Adversarial Verification Suite.
Validates:
1. Bug #30 `okDownKey` anti-bounce logic & focus loss recovery
2. Symmetrical grid scaling at 1080p and 4K (margins, gaps, tile dimensions)
3. Philips label regex suffix stripping
4. Config JSON parsing resilience with missing/partial fields
"""
import unittest
import json
import re

# Android KeyCodes & Action Constants
ACTION_DOWN = 0
ACTION_UP = 1

KEYCODE_DPAD_UP = 19
KEYCODE_DPAD_DOWN = 20
KEYCODE_DPAD_LEFT = 21
KEYCODE_DPAD_RIGHT = 22
KEYCODE_DPAD_CENTER = 23
KEYCODE_ENTER = 66
KEYCODE_BACK = 4
KEYCODE_MENU = 82
KEYCODE_BUTTON_A = 96
KEYCODE_NUMPAD_ENTER = 160


class FocusControllerSimulator:
    """
    High-fidelity state simulator for org.opentv.launcher.FocusController.
    Faithfully models the exact Java key event dispatching, Bug #30 okDownKey guard,
    window focus transitions, and long press disambiguation.
    """
    def __init__(self):
        self.ok_down_key = None
        self.focused_key = None
        self.moving_key = None
        self.is_long_pressed = False
        self.columns_per_row = 6
        self.clicks = []
        self.long_clicks = []

    def is_ok_key(self, key_code: int) -> bool:
        return key_code in (
            KEYCODE_DPAD_CENTER,
            KEYCODE_ENTER,
            KEYCODE_NUMPAD_ENTER,
            KEYCODE_BUTTON_A,
        )

    def is_dpad_direction(self, key_code: int) -> bool:
        return key_code in (
            KEYCODE_DPAD_UP,
            KEYCODE_DPAD_DOWN,
            KEYCODE_DPAD_LEFT,
            KEYCODE_DPAD_RIGHT,
        )

    def on_window_focus_changed(self, has_focus: bool):
        if not has_focus:
            # Bug #30: App losing focus (dialog opening or external app coming to front)
            # Clears okDownKey immediately
            self.ok_down_key = None

    def handle_key_event(
        self,
        key: str,
        is_editable_app: bool,
        key_code: int,
        action: int,
        repeat_count: int = 0,
        is_canceled: bool = False,
        is_long_press: bool = False,
        down_time: int = 0,
        event_time: int = 0,
        long_press_timeout: int = 500
    ) -> bool:
        is_ok = self.is_ok_key(key_code)
        is_down = action == ACTION_DOWN

        # Menu key on editable app opens edit menu
        if is_editable_app and key_code == KEYCODE_MENU:
            if not is_down:
                self.long_clicks.append(key)
            return True

        if not is_ok:
            return False

        # Bug #30: okDownKey guard and long-press disambiguation
        if is_down:
            if repeat_count == 0:
                self.is_long_pressed = False
                self.ok_down_key = key
            elif is_editable_app and not self.is_long_pressed and (
                is_long_press or (event_time - down_time >= long_press_timeout)
            ):
                self.is_long_pressed = True
                self.long_clicks.append(key)
        else:
            # ACTION_UP: only trigger if ACTION_DOWN originated on this exact tile
            is_legitimate = (key == self.ok_down_key) and not is_canceled
            self.ok_down_key = None
            if is_legitimate and not self.is_long_pressed:
                self.clicks.append(key)

        return True


class TestBug30OkDownKeyLogic(unittest.TestCase):
    """Adversarial stress-testing of Bug #30 okDownKey anti-bounce & focus guard."""

    def setUp(self):
        self.fc = FocusControllerSimulator()

    def test_legitimate_click_lifecycle(self):
        """Down then Up on the same tile triggers exactly one click."""
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN)
        self.assertEqual(self.fc.ok_down_key, "app.youtube")
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_UP)
        self.assertIsNone(self.fc.ok_down_key)
        self.assertEqual(self.fc.clicks, ["app.youtube"])

    def test_down_originating_elsewhere(self):
        """Down on Tile A, then Up on Tile B must NEVER trigger click on either tile."""
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN)
        self.assertEqual(self.fc.ok_down_key, "app.youtube")

        # Remote focus shifted to netflix while OK was held, release delivered to netflix
        self.fc.handle_key_event("app.netflix", True, KEYCODE_DPAD_CENTER, ACTION_UP)
        self.assertIsNone(self.fc.ok_down_key)
        self.assertEqual(self.fc.clicks, [], "ACTION_UP on Tile B without prior DOWN must NOT trigger click")

        # Subsequent ACTION_UP on Tile A must also not fire because ok_down_key was consumed
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_UP)
        self.assertEqual(self.fc.clicks, [])

    def test_window_focus_loss_resets_down_key(self):
        """Window focus loss (dialog opened / external app launched) clears okDownKey."""
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN)
        self.assertEqual(self.fc.ok_down_key, "app.youtube")

        # Dialog opens or app switcher takes focus
        self.fc.on_window_focus_changed(False)
        self.assertIsNone(self.fc.ok_down_key, "Focus loss must immediately clear ok_down_key")

        # Focus returns and user releases button
        self.fc.on_window_focus_changed(True)
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_UP)
        self.assertEqual(self.fc.clicks, [], "ACTION_UP after window focus loss must NOT trigger click")

    def test_phantom_action_up(self):
        """ACTION_UP received without prior ACTION_DOWN must be silently ignored."""
        self.fc.handle_key_event("app.plex", True, KEYCODE_DPAD_CENTER, ACTION_UP)
        self.assertEqual(self.fc.clicks, [])
        self.assertIsNone(self.fc.ok_down_key)

    def test_canceled_event(self):
        """ACTION_UP with isCanceled=True must NOT trigger click."""
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN)
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_UP, is_canceled=True)
        self.assertEqual(self.fc.clicks, [])
        self.assertIsNone(self.fc.ok_down_key)

    def test_long_press_disambiguation(self):
        """Holding OK triggers long-press context menu, release does NOT trigger normal click."""
        # Initial press (repeat=0)
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN, repeat_count=0, down_time=100, event_time=100)
        self.assertEqual(self.fc.clicks, [])
        self.assertEqual(self.fc.long_clicks, [])

        # Held past timeout (repeat=1)
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_DOWN, repeat_count=1, down_time=100, event_time=650)
        self.assertEqual(self.fc.long_clicks, ["app.youtube"])

        # Release
        self.fc.handle_key_event("app.youtube", True, KEYCODE_DPAD_CENTER, ACTION_UP, repeat_count=0, down_time=100, event_time=700)
        self.assertEqual(self.fc.clicks, [], "Normal click must NOT fire upon release of a long-press")

    def test_all_supported_ok_keycodes(self):
        """Tests all recognized TV remote OK keycodes."""
        for code in (KEYCODE_DPAD_CENTER, KEYCODE_ENTER, KEYCODE_NUMPAD_ENTER, KEYCODE_BUTTON_A):
            self.fc.clicks.clear()
            self.fc.handle_key_event("tile_test", True, code, ACTION_DOWN)
            self.fc.handle_key_event("tile_test", True, code, ACTION_UP)
            self.assertEqual(self.fc.clicks, ["tile_test"])


class TestGridScalingGeometry(unittest.TestCase):
    """Adversarial stress-testing of 1080p and 4K symmetrical grid scaling."""

    def compute_grid(self, width: int, margin: int = 96, gap: int = 36, per_row: int = 6):
        scale = width / 1920.0
        m = round(margin * scale)
        g = round(gap * scale)
        tile_w = (width - 2 * m - g * (per_row - 1)) // per_row
        tile_h = round(tile_w * 9.0 / 16.0)
        occupied_w = 2 * m + per_row * tile_w + (per_row - 1) * g
        left_margin = m
        right_margin = width - (left_margin + per_row * tile_w + (per_row - 1) * g)
        return {
            "scale": scale,
            "margin": m,
            "gap": g,
            "tile_w": tile_w,
            "tile_h": tile_h,
            "occupied_w": occupied_w,
            "left_margin": left_margin,
            "right_margin": right_margin,
        }

    def test_1080p_canvas(self):
        """1080p canvas (1920x1080) strict symmetry and dimension verification."""
        g = self.compute_grid(1920)
        self.assertAlmostEqual(g["scale"], 1.0)
        self.assertEqual(g["margin"], 96)
        self.assertEqual(g["gap"], 36)
        self.assertEqual(g["tile_w"], 258)
        self.assertEqual(g["tile_h"], 145)
        self.assertEqual(g["occupied_w"], 1920)
        self.assertEqual(g["left_margin"], g["right_margin"])
        self.assertEqual(g["left_margin"], 96)

    def test_4k_canvas(self):
        """4K UHD canvas (3840x2160) strict symmetry and dimension verification."""
        g = self.compute_grid(3840)
        self.assertAlmostEqual(g["scale"], 2.0)
        self.assertEqual(g["margin"], 192)
        self.assertEqual(g["gap"], 72)
        self.assertEqual(g["tile_w"], 516)
        self.assertEqual(g["tile_h"], 290)
        self.assertEqual(g["occupied_w"], 3840)
        self.assertEqual(g["left_margin"], g["right_margin"])
        self.assertEqual(g["left_margin"], 192)

    def test_scaling_factor_exactness(self):
        """Asserts 4K dimensions are exactly double 1080p dimensions."""
        g1080 = self.compute_grid(1920)
        g4k = self.compute_grid(3840)

        self.assertEqual(g4k["tile_w"], g1080["tile_w"] * 2)
        self.assertEqual(g4k["tile_h"], g1080["tile_h"] * 2)
        self.assertEqual(g4k["margin"], g1080["margin"] * 2)
        self.assertEqual(g4k["gap"], g1080["gap"] * 2)


class TestPhilipsLabelStripper(unittest.TestCase):
    """Adversarial testing of VendorAdapter.stripDeviceType regex pattern."""

    PHILIPS_LABEL_PATTERN = re.compile(r"&([A-Z][A-Z0-9_]{2,})$")

    def strip_device_type(self, label: str | None) -> str:
        if label is None:
            return "HDMI"
        matcher = self.PHILIPS_LABEL_PATTERN.search(label)
        if matcher:
            amp_index = label.rfind("&")
            if amp_index > 0:
                return label[:amp_index].strip()
        return label

    def test_canonical_philips_suffixes(self):
        self.assertEqual(self.strip_device_type("PlayStation 5&GAME"), "PlayStation 5")
        self.assertEqual(self.strip_device_type("Nintendo Switch&GAME"), "Nintendo Switch")
        self.assertEqual(self.strip_device_type("Computer&COMPUTER"), "Computer")
        self.assertEqual(self.strip_device_type("Blu-ray Player&BLURAY"), "Blu-ray Player")
        self.assertEqual(self.strip_device_type("Apple TV 4K&APPLE_TV"), "Apple TV 4K")
        self.assertEqual(self.strip_device_type("Set Top Box&STB"), "Set Top Box")
        self.assertEqual(self.strip_device_type("AUDIO&VIDEO"), "AUDIO")

    def test_no_suffix(self):
        self.assertEqual(self.strip_device_type("HDMI 1"), "HDMI 1")
        self.assertEqual(self.strip_device_type("Live TV"), "Live TV")

    def test_boundary_inputs(self):
        self.assertEqual(self.strip_device_type(None), "HDMI")
        self.assertEqual(self.strip_device_type(""), "")
        self.assertEqual(self.strip_device_type("Console &GAME"), "Console")
        # Short suffix (< 3 chars) is preserved
        self.assertEqual(self.strip_device_type("TV&TV"), "TV&TV")
        # Lowercase is preserved
        self.assertEqual(self.strip_device_type("Console&game"), "Console&game")
        # Ampersand at index 0 is preserved
        self.assertEqual(self.strip_device_type("&GAME"), "&GAME")


class TestConfigJsonParsingResilience(unittest.TestCase):
    """Validates ConfigManager JSON parsing under partial, missing, and malformed fields."""

    DEFAULT_APPS = [
        "com.google.android.youtube.tv",
        "com.netflix.ninja",
        "com.amazon.amazonvideo.livingroom",
        "com.disney.disneyplus",
        "com.hulu.livingroomplus",
        "com.wbd.stream"
    ]
    DEFAULT_QUICK = ["wifi", "bluetooth", "sound", "picture", "settings"]

    def parse_config(self, json_str: str) -> dict:
        """Models ConfigManager.parseConfigJson behavior."""
        try:
            data = json.loads(json_str)
            version = data.get("version", 1)
            apps = data.get("apps", [])
            hdmi = data.get("hdmi", [])
            quick = data.get("quick_settings", self.DEFAULT_QUICK)
            theme = data.get("theme", "OLED_Black")
            oled = data.get("oled_protection", {})
            oled_sec = oled.get("screensaver_idle_seconds", 180)
            oled_shift = oled.get("pixel_shift_enabled", True)
            return {
                "version": version,
                "apps": apps,
                "hdmi": hdmi,
                "quick_settings": quick,
                "theme": theme,
                "oled_protection": {
                    "screensaver_idle_seconds": oled_sec,
                    "pixel_shift_enabled": oled_shift
                }
            }
        except Exception:
            # Fallback regex parser
            version_match = re.search(r'"version"\s*:\s*(\d+)', json_str)
            version = int(version_match.group(1)) if version_match else 1
            return {
                "version": version,
                "apps": [],
                "hdmi": [],
                "quick_settings": self.DEFAULT_QUICK,
                "theme": "OLED_Black",
                "oled_protection": {
                    "screensaver_idle_seconds": 180,
                    "pixel_shift_enabled": True
                }
            }

    def test_empty_json(self):
        cfg = self.parse_config("{}")
        self.assertEqual(cfg["version"], 1)
        self.assertEqual(cfg["apps"], [])
        self.assertEqual(cfg["quick_settings"], self.DEFAULT_QUICK)
        self.assertEqual(cfg["theme"], "OLED_Black")
        self.assertEqual(cfg["oled_protection"]["screensaver_idle_seconds"], 180)
        self.assertTrue(cfg["oled_protection"]["pixel_shift_enabled"])

    def test_partial_apps_only(self):
        cfg = self.parse_config('{"apps": ["pkg1", "pkg2"]}')
        self.assertEqual(cfg["apps"], ["pkg1", "pkg2"])
        self.assertEqual(cfg["theme"], "OLED_Black")
        self.assertEqual(cfg["quick_settings"], self.DEFAULT_QUICK)

    def test_partial_hdmi_entries(self):
        cfg = self.parse_config('{"hdmi": [{"id": "HW1"}]}')
        self.assertEqual(len(cfg["hdmi"]), 1)
        self.assertEqual(cfg["hdmi"][0]["id"], "HW1")

    def test_partial_oled_protection(self):
        cfg = self.parse_config('{"oled_protection": {"screensaver_idle_seconds": 60}}')
        self.assertEqual(cfg["oled_protection"]["screensaver_idle_seconds"], 60)
        self.assertTrue(cfg["oled_protection"]["pixel_shift_enabled"])

    def test_malformed_json_graceful_recovery(self):
        cfg = self.parse_config('{version: 1, apps: [broken json')
        self.assertEqual(cfg["version"], 1)
        self.assertIsNotNone(cfg["apps"])


if __name__ == "__main__":
    unittest.main()
