package org.opentv.launcher.test;

import org.opentv.launcher.ConfigManager;
import org.opentv.launcher.FocusController;
import org.opentv.launcher.OledProtectionService;
import org.opentv.launcher.VendorAdapter;

import java.util.ArrayList;
import java.util.List;

public class VerifyLauncherLogic {

    private static int testsRun = 0;
    private static int testsPassed = 0;
    private static int testsFailed = 0;

    private static void assertTrue(String msg, boolean condition) {
        testsRun++;
        if (condition) {
            testsPassed++;
            System.out.println("  [PASS] " + msg);
        } else {
            testsFailed++;
            System.err.println("  [FAIL] " + msg);
        }
    }

    private static void assertEquals(String msg, Object expected, Object actual) {
        testsRun++;
        boolean match = (expected == null && actual == null) || (expected != null && expected.equals(actual));
        if (match) {
            testsPassed++;
            System.out.println("  [PASS] " + msg + " (expected: " + expected + ", actual: " + actual + ")");
        } else {
            testsFailed++;
            System.err.println("  [FAIL] " + msg + " (expected: " + expected + ", actual: " + actual + ")");
        }
    }

    // Mock FocusCallback recording calls
    static class RecordingCallback implements FocusController.FocusCallback {
        final List<String> clicks = new ArrayList<>();
        final List<String> longClicks = new ArrayList<>();
        final List<String> moveCommits = new ArrayList<>();
        final List<String> moveCancels = new ArrayList<>();

        @Override
        public void onTileClick(String key) {
            clicks.add(key);
        }

        @Override
        public void onTileLongClick(String key) {
            longClicks.add(key);
        }

        @Override
        public void onMoveStep(String key, int fromIndex, int toIndex) {}

        @Override
        public void onMoveCommit(String key) {
            moveCommits.add(key);
        }

        @Override
        public void onMoveCancel(String key) {
            moveCancels.add(key);
        }

        @Override
        public int px(int dp) {
            return dp;
        }
    }

    // Custom Mock KeyEvent for testing FocusController handleKeyEvent
    public static class TestKeyEvent extends android.view.KeyEvent {
        public TestKeyEvent(int action, int keyCode) {
            super(action, keyCode);
        }

        public TestKeyEvent(int action, int keyCode, int repeatCount, boolean canceled, boolean longPress, long downTime, long eventTime) {
            super(action, keyCode, repeatCount, canceled, longPress, downTime, eventTime);
        }
    }

    public static void testBug30OkDownKeyLogic() {
        System.out.println("\n--- Testing Bug #30 okDownKey Logic ---");
        RecordingCallback cb = new RecordingCallback();
        FocusController fc = new FocusController(cb);

        int KEY_OK = android.view.KeyEvent.KEYCODE_DPAD_CENTER;
        int ACTION_DOWN = android.view.KeyEvent.ACTION_DOWN;
        int ACTION_UP = android.view.KeyEvent.ACTION_UP;

        // Scenario 1: Legitimate click on Tile A
        cb.clicks.clear();
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK));
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK));
        assertEquals("Scenario 1: Legitimate click fires on tile_a", 1, cb.clicks.size());
        if (!cb.clicks.isEmpty()) {
            assertEquals("Scenario 1: Correct tile key clicked", "tile_a", cb.clicks.get(0));
        }

        // Scenario 2: ACTION_DOWN on tile_a, then ACTION_UP delivered to tile_b (originates elsewhere)
        cb.clicks.clear();
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK));
        fc.handleKeyEvent("tile_b", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK));
        assertEquals("Scenario 2: ACTION_UP on tile_b without DOWN on tile_b does not fire", 0, cb.clicks.size());

        // Subsequent ACTION_UP on tile_a should also NOT fire because okDownKey was reset to null
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK));
        assertEquals("Scenario 2: Subsequent ACTION_UP on tile_a after reset does not fire", 0, cb.clicks.size());

        // Scenario 3: Window focus loss between ACTION_DOWN and ACTION_UP
        cb.clicks.clear();
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK));
        fc.onWindowFocusChanged(false); // Window lost focus (e.g. dialog opened or external app launched)
        fc.onWindowFocusChanged(true);  // Focus returned
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK));
        assertEquals("Scenario 3: Window focus loss clears okDownKey, preventing spurious launch", 0, cb.clicks.size());

        // Scenario 4: Spurious / Phantom ACTION_UP with no prior ACTION_DOWN
        cb.clicks.clear();
        fc.handleKeyEvent("tile_c", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK));
        assertEquals("Scenario 4: Phantom ACTION_UP without DOWN does not fire click", 0, cb.clicks.size());

        // Scenario 5: Canceled ACTION_UP event
        cb.clicks.clear();
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK));
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK, 0, true, false, 0, 0));
        assertEquals("Scenario 5: Canceled ACTION_UP event does not fire click", 0, cb.clicks.size());

        // Scenario 6: Long press disambiguation
        cb.clicks.clear();
        cb.longClicks.clear();
        // Down repeat 0
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK, 0, false, false, 100, 100));
        // Down repeat 1 with long press triggered (e.g. eventTime - downTime >= 500ms)
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_DOWN, KEY_OK, 1, false, true, 100, 700));
        assertEquals("Scenario 6: Long click triggered once", 1, cb.longClicks.size());
        assertEquals("Scenario 6: Long click key", "tile_a", cb.longClicks.get(0));
        // Action up after long press
        fc.handleKeyEvent("tile_a", true, KEY_OK, new TestKeyEvent(ACTION_UP, KEY_OK, 0, false, false, 100, 750));
        assertEquals("Scenario 6: Click does not fire after long press release", 0, cb.clicks.size());

        // Scenario 7: Alternative OK keys (KEYCODE_ENTER, KEYCODE_NUMPAD_ENTER, KEYCODE_BUTTON_A)
        int[] okCodes = {
            android.view.KeyEvent.KEYCODE_ENTER,
            android.view.KeyEvent.KEYCODE_NUMPAD_ENTER,
            android.view.KeyEvent.KEYCODE_BUTTON_A
        };
        for (int code : okCodes) {
            cb.clicks.clear();
            fc.handleKeyEvent("tile_x", true, code, new TestKeyEvent(ACTION_DOWN, code));
            fc.handleKeyEvent("tile_x", true, code, new TestKeyEvent(ACTION_UP, code));
            assertEquals("Scenario 7: KeyCode " + code + " triggers click properly", 1, cb.clicks.size());
        }
    }

    public static void testSymmetricalGridScaling() {
        System.out.println("\n--- Testing Symmetrical Grid Scaling at 1080p and 4K ---");
        int margin = 96, gap = 36, perRow = 6;

        // 1080p (1920x1080)
        int width1080 = 1920;
        float scale1080 = width1080 / 1920.0f;
        int m1080 = Math.round(margin * scale1080);
        int g1080 = Math.round(gap * scale1080);
        int tileW1080 = (width1080 - 2 * m1080 - g1080 * (perRow - 1)) / perRow;
        int tileH1080 = Math.round(tileW1080 * 9.0f / 16.0f);

        assertEquals("1080p scale", 1.0f, scale1080);
        assertEquals("1080p margin", 96, m1080);
        assertEquals("1080p gap", 36, g1080);
        assertEquals("1080p tile width", 258, tileW1080);
        assertEquals("1080p tile height", 145, tileH1080);

        int occupied1080 = 2 * m1080 + perRow * tileW1080 + (perRow - 1) * g1080;
        int leftMargin1080 = m1080;
        int rightMargin1080 = width1080 - (leftMargin1080 + perRow * tileW1080 + (perRow - 1) * g1080);
        assertEquals("1080p occupied width equals canvas width", 1920, occupied1080);
        assertEquals("1080p symmetrical left and right margins", leftMargin1080, rightMargin1080);

        // 4K (3840x2160)
        int width4k = 3840;
        float scale4k = width4k / 1920.0f;
        int m4k = Math.round(margin * scale4k);
        int g4k = Math.round(gap * scale4k);
        int tileW4k = (width4k - 2 * m4k - g4k * (perRow - 1)) / perRow;
        int tileH4k = Math.round(tileW4k * 9.0f / 16.0f);

        assertEquals("4K scale", 2.0f, scale4k);
        assertEquals("4K margin", 192, m4k);
        assertEquals("4K gap", 72, g4k);
        assertEquals("4K tile width", 516, tileW4k);
        assertEquals("4K tile height", 290, tileH4k);

        int occupied4k = 2 * m4k + perRow * tileW4k + (perRow - 1) * g4k;
        int leftMargin4k = m4k;
        int rightMargin4k = width4k - (leftMargin4k + perRow * tileW4k + (perRow - 1) * g4k);
        assertEquals("4K occupied width equals canvas width", 3840, occupied4k);
        assertEquals("4K symmetrical left and right margins", leftMargin4k, rightMargin4k);

        // Scaling ratios
        assertEquals("Tile width scales exactly 2x", tileW1080 * 2, tileW4k);
        assertEquals("Tile height scales exactly 2x", tileH1080 * 2, tileH4k);
        assertEquals("Margin scales exactly 2x", m1080 * 2, m4k);
        assertEquals("Gap scales exactly 2x", g1080 * 2, g4k);
    }

    public static void testPhilipsLabelStripper() {
        System.out.println("\n--- Testing Philips Label Regex Suffix Stripping ---");
        assertEquals("PlayStation 5 stripped", "PlayStation 5", VendorAdapter.stripDeviceType("PlayStation 5&GAME"));
        assertEquals("Nintendo Switch stripped", "Nintendo Switch", VendorAdapter.stripDeviceType("Nintendo Switch&GAME"));
        assertEquals("Computer stripped", "Computer", VendorAdapter.stripDeviceType("Computer&COMPUTER"));
        assertEquals("Blu-ray Player stripped", "Blu-ray Player", VendorAdapter.stripDeviceType("Blu-ray Player&BLURAY"));
        assertEquals("Apple TV 4K stripped", "Apple TV 4K", VendorAdapter.stripDeviceType("Apple TV 4K&APPLE_TV"));
        assertEquals("AUDIO stripped", "AUDIO", VendorAdapter.stripDeviceType("AUDIO&VIDEO"));
        assertEquals("Set Top Box stripped", "Set Top Box", VendorAdapter.stripDeviceType("Set Top Box&STB"));

        // No suffix unchanged
        assertEquals("HDMI 1 unchanged", "HDMI 1", VendorAdapter.stripDeviceType("HDMI 1"));
        assertEquals("Live TV unchanged", "Live TV", VendorAdapter.stripDeviceType("Live TV"));

        // Boundary cases
        assertEquals("null input defaults to HDMI", "HDMI", VendorAdapter.stripDeviceType(null));
        assertEquals("empty input remains empty", "", VendorAdapter.stripDeviceType(""));
        assertEquals("trimmed whitespace before &", "Console", VendorAdapter.stripDeviceType("Console &GAME"));
        assertEquals("short suffix not stripped", "TV&TV", VendorAdapter.stripDeviceType("TV&TV"));
        assertEquals("lowercase suffix not stripped", "Console&game", VendorAdapter.stripDeviceType("Console&game"));
        assertEquals("ampersand at start not stripped", "&GAME", VendorAdapter.stripDeviceType("&GAME"));
    }

    public static void testConfigJsonParsing() {
        System.out.println("\n--- Testing Config JSON Parsing with Missing and Partial Fields ---");

        // 1. Full canonical config
        String fullJson = "{\n" +
                "  \"version\": 1,\n" +
                "  \"apps\": [\"com.youtube\", \"com.netflix\"],\n" +
                "  \"hdmi\": [{\"id\": \"HW1\", \"title\": \"PS5\", \"visible\": true}],\n" +
                "  \"quick_settings\": [\"wifi\", \"bluetooth\"],\n" +
                "  \"theme\": \"OLED_Black\",\n" +
                "  \"oled_protection\": {\"screensaver_idle_seconds\": 180, \"pixel_shift_enabled\": true}\n" +
                "}";
        ConfigManager.LauncherConfig fullCfg = ConfigManager.parseConfigJson(fullJson);
        assertTrue("Full config not null", fullCfg != null);
        assertEquals("Full config version", 1, fullCfg.version);
        assertEquals("Full config apps count", 2, fullCfg.apps.size());
        assertEquals("Full config hdmi count", 1, fullCfg.hdmi.size());
        assertEquals("Full config quick settings", 2, fullCfg.quickSettings.size());
        assertEquals("Full config theme", "OLED_Black", fullCfg.theme);
        assertEquals("Full config idle timeout", 180, fullCfg.oledProtection.screensaverIdleSeconds);
        assertTrue("Full config pixel shift", fullCfg.oledProtection.pixelShiftEnabled);

        // 2. Empty JSON object
        ConfigManager.LauncherConfig emptyCfg = ConfigManager.parseConfigJson("{}");
        assertTrue("Empty config not null", emptyCfg != null);
        assertEquals("Empty config default version", 1, emptyCfg.version);
        assertTrue("Empty config empty apps", emptyCfg.apps.isEmpty());
        assertTrue("Empty config empty hdmi", emptyCfg.hdmi.isEmpty());
        assertEquals("Empty config default quick settings count", 5, emptyCfg.quickSettings.size());
        assertEquals("Empty config default theme", "OLED_Black", emptyCfg.theme);
        assertEquals("Empty config default idle timeout", 180, emptyCfg.oledProtection.screensaverIdleSeconds);
        assertTrue("Empty config default pixel shift", emptyCfg.oledProtection.pixelShiftEnabled);

        // 3. Partial JSON: apps only
        ConfigManager.LauncherConfig appsOnly = ConfigManager.parseConfigJson("{\"apps\": [\"app1\", \"app2\", \"app3\"]}");
        assertTrue("Apps-only config not null", appsOnly != null);
        assertEquals("Apps-only count", 3, appsOnly.apps.size());
        assertEquals("Apps-only default theme", "OLED_Black", appsOnly.theme);
        assertEquals("Apps-only default idle timeout", 180, appsOnly.oledProtection.screensaverIdleSeconds);

        // 4. Partial JSON: hdmi without title or visible
        ConfigManager.LauncherConfig hdmiPartial = ConfigManager.parseConfigJson("{\"hdmi\": [{\"id\": \"HW2\"}]}");
        assertTrue("HDMI partial config not null", hdmiPartial != null);
        assertEquals("HDMI partial size", 1, hdmiPartial.hdmi.size());
        assertEquals("HDMI partial id", "HW2", hdmiPartial.hdmi.get(0).id);

        // 5. Partial JSON: oled_protection with only idle seconds
        ConfigManager.LauncherConfig oledPartial = ConfigManager.parseConfigJson("{\"oled_protection\": {\"screensaver_idle_seconds\": 300}}");
        assertTrue("Oled partial config not null", oledPartial != null);
        assertEquals("Oled partial idle seconds", 300, oledPartial.oledProtection.screensaverIdleSeconds);
        assertTrue("Oled partial retains default pixel shift true", oledPartial.oledProtection.pixelShiftEnabled);

        // 6. Malformed JSON recovery
        ConfigManager.LauncherConfig malformed = ConfigManager.parseConfigJson("{broken json content: [123");
        assertTrue("Malformed JSON returns non-null fallback config without crashing", malformed != null);
    }

    public static void main(String[] args) {
        System.out.println("=================================================");
        System.out.println("   OpenTV Launcher Logic Verification Harness    ");
        System.out.println("=================================================");

        testBug30OkDownKeyLogic();
        testSymmetricalGridScaling();
        testPhilipsLabelStripper();
        testConfigJsonParsing();

        System.out.println("\n=================================================");
        System.out.println("              Verification Summary               ");
        System.out.println("=================================================");
        System.out.println("  Total Checks Run : " + testsRun);
        System.out.println("  Passed           : " + testsPassed);
        System.out.println("  Failed           : " + testsFailed);
        System.out.println("=================================================");

        if (testsFailed > 0) {
            System.err.println("VERDICT: FAIL");
            System.exit(1);
        } else {
            System.out.println("VERDICT: PASS (100% assertions verified)");
            System.exit(0);
        }
    }
}
