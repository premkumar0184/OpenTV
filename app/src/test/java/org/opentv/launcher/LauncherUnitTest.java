package org.opentv.launcher;

import org.junit.Test;
import static org.junit.Assert.*;

import java.io.File;
import java.io.FileWriter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

import android.content.Context;
import android.view.KeyEvent;
import android.view.View;

public class LauncherUnitTest {

    @Test
    public void testStringsLocalization() {
        assertNotNull(Strings.EN);
        assertTrue(Strings.EN.length > 0);

        // English baseline
        assertEquals("Settings", Strings.t("Settings"));
        assertEquals("HDMI", Strings.t("HDMI"));
        assertEquals("Add app", Strings.t("Add app"));

        // Fallback for missing key returns the key itself
        assertEquals("NonExistentStringKey", Strings.t("NonExistentStringKey"));

        // Date pattern not null/empty
        String datePattern = Strings.datePattern();
        assertNotNull(datePattern);
        assertFalse(datePattern.isEmpty());
    }

    @Test
    public void testConfigJsonParsing() {
        String json = "{\n" +
                "  \"version\": 1,\n" +
                "  \"apps\": [\n" +
                "    \"com.google.android.youtube.tv\",\n" +
                "    \"com.netflix.ninja\",\n" +
                "    \"com.plexapp.android\"\n" +
                "  ],\n" +
                "  \"hdmi\": [\n" +
                "    {\"id\": \"HW5\", \"title\": \"PlayStation 5\", \"visible\": true},\n" +
                "    {\"id\": \"HW6\", \"title\": \"Nintendo Switch\", \"visible\": true}\n" +
                "  ],\n" +
                "  \"quick_settings\": [\"wifi\", \"bluetooth\", \"sound\", \"picture\", \"settings\"],\n" +
                "  \"theme\": \"OLED_Black\",\n" +
                "  \"oled_protection\": {\n" +
                "    \"screensaver_idle_seconds\": 180,\n" +
                "    \"pixel_shift_enabled\": true\n" +
                "  }\n" +
                "}";

        ConfigManager.LauncherConfig config = ConfigManager.parseConfigJson(json);
        assertNotNull(config);
        assertEquals(1, config.version);
        assertEquals(3, config.apps.size());
        assertEquals("com.google.android.youtube.tv", config.apps.get(0));
        assertEquals("com.netflix.ninja", config.apps.get(1));
        assertEquals("com.plexapp.android", config.apps.get(2));

        assertEquals(2, config.hdmi.size());
        assertEquals("HW5", config.hdmi.get(0).id);
        assertEquals("PlayStation 5", config.hdmi.get(0).title);
        assertTrue(config.hdmi.get(0).visible);

        assertEquals(5, config.quickSettings.size());
        assertEquals("wifi", config.quickSettings.get(0));
        assertEquals("OLED_Black", config.theme);

        assertNotNull(config.oledProtection);
        assertEquals(180, config.oledProtection.screensaverIdleSeconds);
        assertTrue(config.oledProtection.pixelShiftEnabled);
    }

    @Test
    public void testAppsTxtParsing() throws Exception {
        File temp = File.createTempFile("apps_test", ".txt");
        temp.deleteOnExit();
        try (FileWriter fw = new FileWriter(temp)) {
            fw.write("# Comment line\n");
            fw.write("com.google.android.youtube.tv\n");
            fw.write("\n");
            fw.write("com.netflix.ninja\n");
            fw.write("# Another comment\n");
            fw.write("com.disney.disneyplus\n");
        }

        java.util.List<String> apps = ConfigManager.parseAppsTxt(temp);
        assertEquals(3, apps.size());
        assertEquals("com.google.android.youtube.tv", apps.get(0));
        assertEquals("com.netflix.ninja", apps.get(1));
        assertEquals("com.disney.disneyplus", apps.get(2));
    }

    @Test
    public void testLineIconOpcodeIntegrity() {
        int[][] allIcons = {
            LineIcon.PLAY, LineIcon.HDMI, LineIcon.SETTINGS, LineIcon.PLUS,
            LineIcon.WIFI, LineIcon.WIFI_1, LineIcon.WIFI_2, LineIcon.SLASH,
            LineIcon.BLUETOOTH, LineIcon.SOUND, LineIcon.PICTURE, LineIcon.ETHERNET
        };

        for (int[] ops : allIcons) {
            assertNotNull(ops);
            assertTrue(ops.length > 0);
            // Verify opcodes are in range 0..4
            int i = 0;
            while (i < ops.length) {
                int op = ops[i];
                assertTrue(op >= 0 && op <= 4);
                if (op == 0 || op == 1) i += 3;
                else if (op == 2) i += 1;
                else if (op == 3) i += 4;
                else if (op == 4) i += 6;
            }
        }
    }

    @Test
    public void testScalingGeometryCalculations() {
        // 1080p Canvas (1920x1080)
        int margin = 96, gap = 36, perRow = 6;
        int width1080 = 1920;
        float scale1080 = width1080 / 1920.0f;
        int m1080 = Math.round(margin * scale1080);
        int g1080 = Math.round(gap * scale1080);
        int tileW1080 = (width1080 - 2 * m1080 - g1080 * (perRow - 1)) / perRow;
        int tileH1080 = Math.round(tileW1080 * 9.0f / 16.0f);

        assertEquals(258, tileW1080);
        assertEquals(145, tileH1080);

        // 4K Canvas (3840x2160)
        int width4k = 3840;
        float scale4k = width4k / 1920.0f;
        int m4k = Math.round(margin * scale4k);
        int g4k = Math.round(gap * scale4k);
        int tileW4k = (width4k - 2 * m4k - g4k * (perRow - 1)) / perRow;
        int tileH4k = Math.round(tileW4k * 9.0f / 16.0f);

        assertEquals(516, tileW4k);
        assertEquals(290, tileH4k);

        // Scaling factor parity
        assertEquals(tileW1080 * 2, tileW4k);
        assertEquals(tileH1080 * 2, tileH4k);
    }

    @Test
    public void testPhilipsLabelStripper() {
        assertEquals("PlayStation", VendorAdapter.stripDeviceType("PlayStation&GAME"));
        assertEquals("Computer", VendorAdapter.stripDeviceType("Computer&COMPUTER"));
        assertEquals("Blu-ray Player", VendorAdapter.stripDeviceType("Blu-ray Player&BLURAY"));
        assertEquals("HDMI 1", VendorAdapter.stripDeviceType("HDMI 1"));
        assertEquals("AUDIO", VendorAdapter.stripDeviceType("AUDIO&VIDEO"));
    }

    @Test
    public void testOledConstants() {
        assertEquals(180_000L, OledProtectionService.DEFAULT_INACTIVITY_TIMEOUT_MS);
        assertEquals(60_000L, OledProtectionService.PIXEL_SHIFT_INTERVAL_MS);
        assertEquals(0xFF000000, OledProtectionService.PURE_BLACK_COLOR);
    }

    @Test
    public void testPhilipsLabelStripperAdversarial() {
        // Standard suffixes
        assertEquals("PlayStation 5", VendorAdapter.stripDeviceType("PlayStation 5&GAME"));
        assertEquals("Nintendo Switch", VendorAdapter.stripDeviceType("Nintendo Switch&GAME"));
        assertEquals("PC", VendorAdapter.stripDeviceType("PC&COMPUTER"));
        assertEquals("Blu-ray Player", VendorAdapter.stripDeviceType("Blu-ray Player&BLURAY"));
        assertEquals("Apple TV 4K", VendorAdapter.stripDeviceType("Apple TV 4K&APPLE_TV"));
        assertEquals("Set Top Box", VendorAdapter.stripDeviceType("Set Top Box&STB"));

        // Boundary: null returns "HDMI"
        assertEquals("HDMI", VendorAdapter.stripDeviceType(null));

        // Boundary: empty string
        assertEquals("", VendorAdapter.stripDeviceType(""));

        // No suffix
        assertEquals("HDMI 1", VendorAdapter.stripDeviceType("HDMI 1"));
        assertEquals("Live TV", VendorAdapter.stripDeviceType("Live TV"));

        // Suffix with whitespace before &
        assertEquals("Console", VendorAdapter.stripDeviceType("Console &GAME"));

        // Suffix too short (regex requires 3+ chars: [A-Z][A-Z0-9_]{2,})
        assertEquals("TV&TV", VendorAdapter.stripDeviceType("TV&TV"));

        // Lowercase suffix not stripped by uppercase regex
        assertEquals("Console&game", VendorAdapter.stripDeviceType("Console&game"));

        // Suffix at index 0 (&GAME): ampIndex is 0 so not stripped
        assertEquals("&GAME", VendorAdapter.stripDeviceType("&GAME"));
    }

    @Test
    public void testSymmetricalGridScaling1080pAnd4K() {
        int margin = 96, gap = 36, perRow = 6;

        // 1. 1080p Display (1920x1080)
        int width1080 = 1920;
        float scale1080 = width1080 / 1920.0f;
        assertEquals(1.0f, scale1080, 0.0001f);
        int m1080 = Math.round(margin * scale1080);
        int g1080 = Math.round(gap * scale1080);
        int tileW1080 = (width1080 - 2 * m1080 - g1080 * (perRow - 1)) / perRow;
        int tileH1080 = Math.round(tileW1080 * 9.0f / 16.0f);

        assertEquals(96, m1080);
        assertEquals(36, g1080);
        assertEquals(258, tileW1080);
        assertEquals(145, tileH1080);

        // Verify total row width and strict symmetry
        int rowSpan1080 = perRow * tileW1080 + (perRow - 1) * g1080;
        int leftMargin1080 = m1080;
        int rightMargin1080 = width1080 - (leftMargin1080 + rowSpan1080);
        assertEquals(leftMargin1080, rightMargin1080);
        assertEquals(96, rightMargin1080);

        // 2. 4K UHD Display (3840x2160)
        int width4k = 3840;
        float scale4k = width4k / 1920.0f;
        assertEquals(2.0f, scale4k, 0.0001f);
        int m4k = Math.round(margin * scale4k);
        int g4k = Math.round(gap * scale4k);
        int tileW4k = (width4k - 2 * m4k - g4k * (perRow - 1)) / perRow;
        int tileH4k = Math.round(tileW4k * 9.0f / 16.0f);

        assertEquals(192, m4k);
        assertEquals(72, g4k);
        assertEquals(516, tileW4k);
        assertEquals(290, tileH4k);

        // Verify total row width and strict symmetry
        int rowSpan4k = perRow * tileW4k + (perRow - 1) * g4k;
        int leftMargin4k = m4k;
        int rightMargin4k = width4k - (leftMargin4k + rowSpan4k);
        assertEquals(leftMargin4k, rightMargin4k);
        assertEquals(192, rightMargin4k);

        // Exact 2x scale proportionality
        assertEquals(m1080 * 2, m4k);
        assertEquals(g1080 * 2, g4k);
        assertEquals(tileW1080 * 2, tileW4k);
        assertEquals(tileH1080 * 2, tileH4k);
    }

    @Test
    public void testConfigJsonParsingWithMissingAndPartialFields() {
        // 1. Empty JSON object
        ConfigManager.LauncherConfig emptyConfig = ConfigManager.parseConfigJson("{}");
        assertNotNull(emptyConfig);
        assertEquals(1, emptyConfig.version);
        assertNotNull(emptyConfig.apps);
        assertTrue(emptyConfig.apps.isEmpty());
        assertNotNull(emptyConfig.hdmi);
        assertTrue(emptyConfig.hdmi.isEmpty());
        assertNotNull(emptyConfig.quickSettings);
        assertEquals(5, emptyConfig.quickSettings.size());
        assertEquals("OLED_Black", emptyConfig.theme);
        assertNotNull(emptyConfig.oledProtection);
        assertEquals(180, emptyConfig.oledProtection.screensaverIdleSeconds);
        assertTrue(emptyConfig.oledProtection.pixelShiftEnabled);

        // 2. Partial JSON with only apps
        String appsOnly = "{\"apps\": [\"com.foo.app1\", \"com.foo.app2\"]}";
        ConfigManager.LauncherConfig appsConfig = ConfigManager.parseConfigJson(appsOnly);
        assertNotNull(appsConfig);
        assertEquals(2, appsConfig.apps.size());
        assertEquals("com.foo.app1", appsConfig.apps.get(0));
        assertEquals("com.foo.app2", appsConfig.apps.get(1));
        assertEquals("OLED_Black", appsConfig.theme);
        assertEquals(180, appsConfig.oledProtection.screensaverIdleSeconds);

        // 3. Partial JSON with partial HDMI (missing title and visible)
        String hdmiPartial = "{\"hdmi\": [{\"id\": \"HW1\"}]}";
        ConfigManager.LauncherConfig hdmiConfig = ConfigManager.parseConfigJson(hdmiPartial);
        assertNotNull(hdmiConfig);
        assertEquals(1, hdmiConfig.hdmi.size());
        assertEquals("HW1", hdmiConfig.hdmi.get(0).id);

        // 4. Partial JSON with partial OLED protection (only idle seconds)
        String oledPartial = "{\"oled_protection\": {\"screensaver_idle_seconds\": 300}}";
        ConfigManager.LauncherConfig oledConfig = ConfigManager.parseConfigJson(oledPartial);
        assertNotNull(oledConfig);
        assertEquals(300, oledConfig.oledProtection.screensaverIdleSeconds);
        assertTrue(oledConfig.oledProtection.pixelShiftEnabled);

        // 5. Corrupted / malformed JSON - should not throw, should recover safely
        ConfigManager.LauncherConfig malformedConfig = ConfigManager.parseConfigJson("{version: 1, apps: [broken");
        assertNotNull(malformedConfig);
        assertEquals(1, malformedConfig.version);
    }

    // =========================================================================
    // FOCUS CONTROLLER TEST DOUBLES & FIXTURES
    // =========================================================================

    public static class FocusTestKeyEvent extends KeyEvent {
        public final int action;
        public final int code;
        public final int repeat;
        public final boolean canceled;
        public final boolean longPress;
        public final long downTime;
        public final long eventTime;

        public FocusTestKeyEvent(int action, int code) {
            this(action, code, 0, false, false);
        }

        public FocusTestKeyEvent(int action, int code, int repeat, boolean canceled, boolean longPress) {
            super(action, code);
            this.action = action;
            this.code = code;
            this.repeat = repeat;
            this.canceled = canceled;
            this.longPress = longPress;
            this.downTime = 0L;
            this.eventTime = 0L;
        }
    }

    public static class FocusTestView extends View {
        private Object tag;
        public boolean isFocused = false;

        public FocusTestView(String tag) {
            super((Context) null);
            this.tag = tag;
        }

        @Override public void setTag(Object tag) { this.tag = tag; }
        @Override public Object getTag() { return this.tag; }
        @Override public void setFocusable(boolean f) {}
        @Override public void setOnFocusChangeListener(OnFocusChangeListener l) {}
        @Override public void setOnKeyListener(OnKeyListener l) {}

        @Override
        public boolean requestFocus(int direction, android.graphics.Rect previouslyFocusedRect) {
            this.isFocused = true;
            return true;
        }
    }

    public static class RecordingFocusCallback implements FocusController.FocusCallback {
        public final List<String> clicks = new ArrayList<>();
        public final List<String> longClicks = new ArrayList<>();
        public final List<String> moveSteps = new ArrayList<>();
        public final List<String> commits = new ArrayList<>();
        public final List<String> cancels = new ArrayList<>();

        @Override public void onTileClick(String key) { clicks.add(key); }
        @Override public void onTileLongClick(String key) { longClicks.add(key); }
        @Override public void onMoveStep(String key, int from, int to) { moveSteps.add(key + ":" + from + "->" + to); }
        @Override public void onMoveCommit(String key) { commits.add(key); }
        @Override public void onMoveCancel(String key) { cancels.add(key); }
        @Override public int px(int dp) { return dp; }

        public void clear() {
            clicks.clear();
            longClicks.clear();
            moveSteps.clear();
            commits.clear();
            cancels.clear();
        }
    }

    // =========================================================================
    // 1. MOVE MODE STATE TRANSITIONS & BOUNDS
    // =========================================================================

    @Test
    public void testMoveModeStepBoundsChecking() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        // Register 4 apps: app_0, app_1, app_2, app_3
        for (int i = 0; i < 4; i++) {
            FocusTestView app = new FocusTestView("app_" + i);
            fc.registerAppTile(app, "app_" + i, false, null);
        }

        FocusTestView card0 = new FocusTestView("app_0");
        fc.startMove("app_0", card0);
        assertTrue("startMove should request focus on active card", card0.isFocused);

        // 1. Left boundary: move left from index 0 (step = -1, to = -1) -> rejected
        FocusTestKeyEvent leftDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_LEFT);
        boolean handled = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_LEFT, leftDown);
        assertTrue("Move key should be consumed in move mode", handled);
        assertTrue("Out of bounds step (to < 0) must not trigger callback", cb.moveSteps.isEmpty());

        // 2. Top boundary: move up from index 0 (step = -6, to = -6) -> rejected
        FocusTestKeyEvent upDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_UP);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, upDown);
        assertTrue("Out of bounds step (to < 0) must not trigger callback", cb.moveSteps.isEmpty());

        // 3. Bottom boundary: move down from index 0 in 4-item list (step = +6, to = 6 >= 4) -> rejected
        FocusTestKeyEvent downDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_DOWN);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, downDown);
        assertTrue("Out of bounds step (to >= size) must not trigger callback", cb.moveSteps.isEmpty());

        // 4. Right boundary: move right from index 3 (last item in list, to = 4 >= 4) -> rejected
        fc.stopMove("app_0", true);
        FocusTestView card3 = new FocusTestView("app_3");
        fc.startMove("app_3", card3);
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        fc.handleKeyEvent("app_3", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertTrue("Out of bounds step (to >= size) must not trigger callback", cb.moveSteps.isEmpty());
    }

    @Test
    public void testMoveModeConsecutiveStepsStateSynchronization() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        // Register 4 apps: app_0, app_1, app_2, app_3
        FocusTestView[] views = new FocusTestView[4];
        for (int i = 0; i < 4; i++) {
            views[i] = new FocusTestView("app_" + i);
            fc.registerAppTile(views[i], "app_" + i, false, null);
        }

        // Start moving app_1 (initially at index 1)
        fc.startMove("app_1", views[1]);

        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        FocusTestKeyEvent leftDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_LEFT);

        // Step 1: Move right (index 1 -> 2)
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertEquals(1, cb.moveSteps.size());
        assertEquals("app_1:1->2", cb.moveSteps.get(0));

        // Step 2: Move right again (MUST move from updated position 2 -> 3, NOT from stale 1!)
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertEquals(2, cb.moveSteps.size());
        assertEquals("app_1:2->3", cb.moveSteps.get(1));

        // Step 3: Move left (MUST move back from 3 -> 2)
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_LEFT, leftDown);
        assertEquals(3, cb.moveSteps.size());
        assertEquals("app_1:3->2", cb.moveSteps.get(2));
    }

    @Test
    public void testMoveModeCommitOnOkOrMenu() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        for (int i = 0; i < 4; i++) {
            fc.registerAppTile(new FocusTestView("app_" + i), "app_" + i, false, null);
        }

        // Case 1: Commit via KEYCODE_DPAD_CENTER
        fc.startMove("app_1", new FocusTestView("app_1"));
        FocusTestKeyEvent okUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_CENTER, okUp);

        assertEquals("onMoveCommit must be called on OK release", 1, cb.commits.size());
        assertEquals("app_1", cb.commits.get(0));
        assertTrue("onMoveCancel must not be called", cb.cancels.isEmpty());

        // Case 2: Commit via KEYCODE_MENU
        cb.clear();
        fc.startMove("app_2", new FocusTestView("app_2"));
        FocusTestKeyEvent menuUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MENU);
        fc.handleKeyEvent("app_2", true, KeyEvent.KEYCODE_MENU, menuUp);

        assertEquals("onMoveCommit must be called on MENU release", 1, cb.commits.size());
        assertEquals("app_2", cb.commits.get(0));
        assertTrue("onMoveCancel must not be called", cb.cancels.isEmpty());
    }

    @Test
    public void testMoveModeCancelOnBackRevertsLayout() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        for (int i = 0; i < 4; i++) {
            fc.registerAppTile(new FocusTestView("app_" + i), "app_" + i, false, null);
        }

        // Start move on app_1 (at index 1)
        fc.startMove("app_1", new FocusTestView("app_1"));

        // Step right: index 1 -> 2
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertEquals(1, cb.moveSteps.size());

        // Cancel via KEYCODE_BACK
        FocusTestKeyEvent backDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_BACK);
        FocusTestKeyEvent backUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_BACK);

        boolean handledDown = fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_BACK, backDown);
        assertTrue("BACK ACTION_DOWN must be consumed in move mode", handledDown);

        boolean handledUp = fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_BACK, backUp);
        assertTrue("BACK ACTION_UP must be consumed in move mode", handledUp);

        assertEquals("onMoveCancel must be called on BACK release", 1, cb.cancels.size());
        assertEquals("app_1", cb.cancels.get(0));
        assertTrue("onMoveCommit must not be called on cancel", cb.commits.isEmpty());
    }

    // =========================================================================
    // 2. BUG #30 OK_DOWN_KEY STATE MACHINE
    // =========================================================================

    @Test
    public void testBug30OkDownKeyUpOnSameTileTriggersClick() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView app0 = new FocusTestView("app_0");
        fc.registerAppTile(app0, "app_0", false, null);

        FocusTestKeyEvent down = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER);
        FocusTestKeyEvent up = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);

        boolean handledDown = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_CENTER, down);
        assertTrue("ACTION_DOWN on OK should be consumed", handledDown);
        assertTrue("DOWN alone must not trigger click", cb.clicks.isEmpty());

        boolean handledUp = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_CENTER, up);
        assertTrue("ACTION_UP on OK should be consumed", handledUp);
        assertEquals("Single click must be registered for app_0", 1, cb.clicks.size());
        assertEquals("app_0", cb.clicks.get(0));
    }

    @Test
    public void testBug30OkDownOnAUpOnBMismatchedKeyIgnored() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView appA = new FocusTestView("app_A");
        FocusTestView appB = new FocusTestView("app_B");
        fc.registerAppTile(appA, "app_A", false, null);
        fc.registerAppTile(appB, "app_B", false, null);

        FocusTestKeyEvent down = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER);
        FocusTestKeyEvent up = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);

        // DOWN on A
        fc.handleKeyEvent("app_A", true, KeyEvent.KEYCODE_DPAD_CENTER, down);
        // UP arrives on B (due to rapid focus change or bounce)
        fc.handleKeyEvent("app_B", true, KeyEvent.KEYCODE_DPAD_CENTER, up);

        assertTrue("Mismatched UP key must be ignored (no clicks fired)", cb.clicks.isEmpty());

        // Subsequent legitimate click on B to verify state was cleared cleanly
        fc.handleKeyEvent("app_B", true, KeyEvent.KEYCODE_DPAD_CENTER, down);
        fc.handleKeyEvent("app_B", true, KeyEvent.KEYCODE_DPAD_CENTER, up);
        assertEquals(1, cb.clicks.size());
        assertEquals("app_B", cb.clicks.get(0));
    }

    @Test
    public void testBug30OkDownFocusLossUpIgnored() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView appA = new FocusTestView("app_A");
        fc.registerAppTile(appA, "app_A", false, null);

        FocusTestKeyEvent down = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER);
        FocusTestKeyEvent up = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);

        // DOWN on A
        fc.handleKeyEvent("app_A", true, KeyEvent.KEYCODE_DPAD_CENTER, down);

        // Window loses focus (dialog open / notification overlay / backgrounded)
        fc.onWindowFocusChanged(false);

        // UP arrives on A after focus loss
        fc.handleKeyEvent("app_A", true, KeyEvent.KEYCODE_DPAD_CENTER, up);

        assertTrue("UP after window focus loss must be ignored", cb.clicks.isEmpty());
    }

    @Test
    public void testBug30CanceledKeyEventIgnored() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView appA = new FocusTestView("app_A");
        fc.registerAppTile(appA, "app_A", false, null);

        FocusTestKeyEvent down = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER);
        FocusTestKeyEvent upCanceled = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER, 0, true, false);

        fc.handleKeyEvent("app_A", true, KeyEvent.KEYCODE_DPAD_CENTER, down);
        fc.handleKeyEvent("app_A", true, KeyEvent.KEYCODE_DPAD_CENTER, upCanceled);

        assertTrue("Canceled UP event must not trigger click", cb.clicks.isEmpty());
    }

    @Test
    public void testBug30AllOkKeyCodesAccepted() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView app = new FocusTestView("app");
        fc.registerAppTile(app, "app", false, null);

        int[] okKeyCodes = {
            KeyEvent.KEYCODE_DPAD_CENTER,
            KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_NUMPAD_ENTER,
            KeyEvent.KEYCODE_BUTTON_A
        };

        for (int code : okKeyCodes) {
            cb.clear();
            FocusTestKeyEvent down = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, code);
            FocusTestKeyEvent up = new FocusTestKeyEvent(KeyEvent.ACTION_UP, code);
            fc.handleKeyEvent("app", true, code, down);
            fc.handleKeyEvent("app", true, code, up);
            assertEquals("KeyCode " + code + " must trigger click", 1, cb.clicks.size());
            assertEquals("app", cb.clicks.get(0));
        }
    }

    @Test
    public void testBug30LongPressSuppressesSubsequentClick() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView app = new FocusTestView("app_edit");
        fc.registerAppTile(app, "app_edit", false, null);

        FocusTestKeyEvent downInitial = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER, 0, false, false);
        FocusTestKeyEvent downLong = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_CENTER, 1, false, true);
        FocusTestKeyEvent up = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);

        // 1. Initial DOWN
        fc.handleKeyEvent("app_edit", true, KeyEvent.KEYCODE_DPAD_CENTER, downInitial);
        // 2. Repeat DOWN with long press
        fc.handleKeyEvent("app_edit", true, KeyEvent.KEYCODE_DPAD_CENTER, downLong);
        assertEquals("Long click callback should trigger", 1, cb.longClicks.size());
        assertEquals("app_edit", cb.longClicks.get(0));

        // 3. UP event following long press must NOT trigger click
        fc.handleKeyEvent("app_edit", true, KeyEvent.KEYCODE_DPAD_CENTER, up);
        assertTrue("Subsequent click must be suppressed after long press", cb.clicks.isEmpty());
    }

    // =========================================================================
    // 3. SPATIAL NAVIGATION COORDINATE CALCULATIONS
    // =========================================================================

    @Test
    public void testSpatialNavGridToHeaderBoundary() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        FocusTestView header0 = new FocusTestView("head_clock");
        FocusTestView header1 = new FocusTestView("head_wifi");
        FocusTestView header2 = new FocusTestView("head_settings");
        fc.registerHeaderView(header0, "head_clock");
        fc.registerHeaderView(header1, "head_wifi");
        fc.registerHeaderView(header2, "head_settings");

        for (int i = 0; i < 6; i++) {
            FocusTestView app = new FocusTestView("app_" + i);
            fc.registerAppTile(app, "app_" + i, false, null);
        }

        FocusTestKeyEvent upKey = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_UP);

        // app_0 (col 0) -> header target min(0, 2) = 0
        header0.isFocused = false;
        boolean handled = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue(handled);
        assertTrue("app_0 UP should focus header 0", header0.isFocused);

        // app_1 (col 1) -> header target min(1, 2) = 1
        header1.isFocused = false;
        fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue("app_1 UP should focus header 1", header1.isFocused);

        // app_4 (col 4) -> header target min(4, 2) = 2 (clamped to rightmost header)
        header2.isFocused = false;
        fc.handleKeyEvent("app_4", true, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue("app_4 UP should focus header 2", header2.isFocused);
    }

    @Test
    public void testSpatialNavGridToFooterBoundary() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        List<FocusTestView> apps = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            FocusTestView app = new FocusTestView("app_" + i);
            apps.add(app);
            fc.registerAppTile(app, "app_" + i, false, null);
        }

        FocusTestView foot0 = new FocusTestView("foot_hdmi1");
        FocusTestView foot1 = new FocusTestView("foot_hdmi2");
        fc.registerFooterTile(foot0, "foot_hdmi1");
        fc.registerFooterTile(foot1, "foot_hdmi2");

        FocusTestKeyEvent downKey = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_DOWN);

        // app_0 has an app below it (app_6 at nextRowIdx 0+6=6 < 8): should return false (intra-grid nav)
        boolean handled0 = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertFalse("app_0 has tile below, should not jump to footer", handled0);

        // app_3 has NO app below it (nextRowIdx 3+6=9 >= 8): jumps to footer min(3, 1) = 1
        foot1.isFocused = false;
        boolean handled3 = fc.handleKeyEvent("app_3", true, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue("app_3 at edge of row should jump to footer", handled3);
        assertTrue("app_3 DOWN should focus foot_hdmi2", foot1.isFocused);

        // app_6 (bottom row, col 0) -> foot0 min(0, 1) = 0
        foot0.isFocused = false;
        boolean handled6 = fc.handleKeyEvent("app_6", true, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue(handled6);
        assertTrue("app_6 DOWN should focus foot_hdmi1", foot0.isFocused);

        // app_7 (bottom row, col 1) -> foot1 min(1, 1) = 1
        foot1.isFocused = false;
        boolean handled7 = fc.handleKeyEvent("app_7", true, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue(handled7);
        assertTrue("app_7 DOWN should focus foot_hdmi2", foot1.isFocused);
    }

    @Test
    public void testSpatialNavFooterToGridCalculations() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        List<FocusTestView> apps = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            FocusTestView app = new FocusTestView("app_" + i);
            apps.add(app);
            fc.registerAppTile(app, "app_" + i, false, null);
        }

        FocusTestView foot0 = new FocusTestView("foot_0");
        FocusTestView foot1 = new FocusTestView("foot_1");
        FocusTestView foot2 = new FocusTestView("foot_2");
        fc.registerFooterTile(foot0, "foot_0");
        fc.registerFooterTile(foot1, "foot_1");
        fc.registerFooterTile(foot2, "foot_2");

        FocusTestKeyEvent upKey = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_UP);

        // footer 0 -> remainder = 2, footerIdx 0 < 2 -> target = (1-0)*6 + min(0, 1) = 6
        apps.get(6).isFocused = false;
        fc.handleKeyEvent("foot_0", false, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue("foot_0 UP should navigate to app_6", apps.get(6).isFocused);

        // footer 1 -> remainder = 2, footerIdx 1 < 2 -> target = 6 + 1 = 7
        apps.get(7).isFocused = false;
        fc.handleKeyEvent("foot_1", false, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue("foot_1 UP should navigate to app_7", apps.get(7).isFocused);

        // footer 2 -> remainder = 2, footerIdx 2 >= 2 -> target = totalApps - 1 = 7 (snaps to last app)
        apps.get(7).isFocused = false;
        fc.handleKeyEvent("foot_2", false, KeyEvent.KEYCODE_DPAD_UP, upKey);
        assertTrue("foot_2 UP should snap to app_7", apps.get(7).isFocused);
    }

    @Test
    public void testSpatialNavHeaderToGridCoordinates() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        fc.setColumnsPerRow(6);

        FocusTestView header0 = new FocusTestView("head_0");
        FocusTestView header2 = new FocusTestView("head_2");
        FocusTestView header5 = new FocusTestView("head_5");
        fc.registerHeaderView(header0, "head_0");
        fc.registerHeaderView(header2, "head_2");
        fc.registerHeaderView(header5, "head_5");

        List<FocusTestView> apps = new ArrayList<>();
        for (int i = 0; i < 4; i++) {
            FocusTestView app = new FocusTestView("app_" + i);
            apps.add(app);
            fc.registerAppTile(app, "app_" + i, false, null);
        }

        FocusTestKeyEvent downKey = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_DOWN);

        // header 0 -> target min(0, min(5, 3)) = 0
        apps.get(0).isFocused = false;
        fc.handleKeyEvent("head_0", false, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue("head_0 DOWN should focus app_0", apps.get(0).isFocused);

        // header 2 -> target min(1, min(5, 3)) = 1 (since header2 is index 1 in headerViews)
        apps.get(1).isFocused = false;
        fc.handleKeyEvent("head_2", false, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue("head_2 DOWN should focus app_1", apps.get(1).isFocused);

        // header 5 -> target min(2, min(5, 3)) = 2
        apps.get(2).isFocused = false;
        fc.handleKeyEvent("head_5", false, KeyEvent.KEYCODE_DPAD_DOWN, downKey);
        assertTrue("head_5 DOWN should focus app_2", apps.get(2).isFocused);
    }

    @Test
    public void testRestoreFocusPreferredAndFallback() {
        RecordingFocusCallback cb = new RecordingFocusCallback();
        FocusController fc = new FocusController(cb);
        FocusTestView app0 = new FocusTestView("app_0");
        FocusTestView app1 = new FocusTestView("app_1");
        FocusTestView foot = new FocusTestView("foot");
        fc.registerAppTile(app0, "app_0", false, null);
        fc.registerAppTile(app1, "app_1", false, null);
        fc.registerFooterTile(foot, "foot");

        // 1. Preferred key exists
        app0.isFocused = false;
        app1.isFocused = false;
        fc.restoreFocus("app_1", 0);
        assertTrue("app_1 should have received focus", app1.isFocused);

        // 2. Preferred key null -> fallback index clamped
        app0.isFocused = false;
        app1.isFocused = false;
        fc.restoreFocus(null, 0);
        assertTrue("app_0 should have received focus via fallback index 0", app0.isFocused);

        // 3. Fallback index out of bounds clamped to max
        app0.isFocused = false;
        app1.isFocused = false;
        fc.restoreFocus("non_existent", 99);
        assertTrue("app_1 should have received focus via clamped fallback index", app1.isFocused);

        // 4. Empty apps falls back to footer
        fc.clearAllZones();
        FocusTestView footOnly = new FocusTestView("foot_only");
        fc.registerFooterTile(footOnly, "foot_only");
        fc.restoreFocus("missing", 0);
        assertTrue("Footer should receive focus when apps grid is empty", footOnly.isFocused);
    }
}
