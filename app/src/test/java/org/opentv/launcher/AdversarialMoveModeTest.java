package org.opentv.launcher;

import org.junit.Test;
import static org.junit.Assert.*;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import android.view.KeyEvent;
import android.view.View;
import org.opentv.launcher.LauncherUnitTest.FocusTestKeyEvent;
import org.opentv.launcher.LauncherUnitTest.FocusTestView;

/**
 * Adversarial stress test suite for Move Mode state synchronization,
 * boundary/out-of-bounds resilience, and KEYCODE_BACK cancel reversion.
 */
public class AdversarialMoveModeTest {

    // -------------------------------------------------------------------------
    // Reflection Helpers to directly inspect FocusController internal state
    // -------------------------------------------------------------------------

    @SuppressWarnings("unchecked")
    private static List<View> getInternalAppViews(FocusController fc) {
        try {
            Field f = FocusController.class.getDeclaredField("appViews");
            f.setAccessible(true);
            return (List<View>) f.get(fc);
        } catch (Exception e) {
            throw new RuntimeException("Failed to access FocusController.appViews via reflection", e);
        }
    }

    @SuppressWarnings("unchecked")
    private static List<View> getInternalInitialAppViews(FocusController fc) {
        try {
            Field f = FocusController.class.getDeclaredField("initialAppViews");
            f.setAccessible(true);
            return (List<View>) f.get(fc);
        } catch (Exception e) {
            throw new RuntimeException("Failed to access FocusController.initialAppViews via reflection", e);
        }
    }

    private static List<String> extractTags(List<View> views) {
        List<String> tags = new ArrayList<>();
        for (View v : views) {
            tags.add(v.getTag() != null ? v.getTag().toString() : null);
        }
        return tags;
    }

    // -------------------------------------------------------------------------
    // State Tracker Mirroring MainActivity Move Mode Behavior
    // -------------------------------------------------------------------------

    public static class MainActivityMirror implements FocusController.Listener {
        public final List<String> rowApps = new ArrayList<>();
        public final List<FocusTestView> appCards = new ArrayList<>();
        public List<String> initialAppsBeforeMove;

        public final List<String> recordedSteps = new ArrayList<>();
        public final List<String> commits = new ArrayList<>();
        public final List<String> cancels = new ArrayList<>();

        public void init(List<String> initial) {
            rowApps.clear();
            rowApps.addAll(initial);
            appCards.clear();
            for (String key : initial) {
                appCards.add(new FocusTestView(key));
            }
            initialAppsBeforeMove = null;
            recordedSteps.clear();
            commits.clear();
            cancels.clear();
        }

        public void startMove(FocusController fc, String key) {
            initialAppsBeforeMove = new ArrayList<>(rowApps);
            int idx = rowApps.indexOf(key);
            FocusTestView card = idx >= 0 ? appCards.get(idx) : null;
            fc.startMove(key, card);
        }

        @Override
        public void onTileClick(String key) {}

        @Override
        public void onTileLongClick(String key) {}

        @Override
        public void onMoveStep(String key, int fromIndex, int toIndex) {
            if (fromIndex < 0 || fromIndex >= rowApps.size() || toIndex < 0 || toIndex >= rowApps.size()) {
                return;
            }
            rowApps.add(toIndex, rowApps.remove(fromIndex));
            FocusTestView card = appCards.remove(fromIndex);
            appCards.add(toIndex, card);
            recordedSteps.add(key + ":" + fromIndex + "->" + toIndex);
        }

        @Override
        public void onMoveCommit(String key) {
            commits.add(key);
            initialAppsBeforeMove = null;
        }

        @Override
        public void onMoveCancel(String key) {
            cancels.add(key);
            if (initialAppsBeforeMove != null) {
                rowApps.clear();
                rowApps.addAll(initialAppsBeforeMove);
                appCards.clear();
                for (String k : initialAppsBeforeMove) {
                    appCards.add(new FocusTestView(k));
                }
                initialAppsBeforeMove = null;
            }
        }

        @Override
        public int px(int dp) {
            return dp;
        }

        public List<String> getCardTags() {
            List<String> tags = new ArrayList<>();
            for (FocusTestView c : appCards) {
                tags.add(c.getTag().toString());
            }
            return tags;
        }
    }

    private static FocusController createController(MainActivityMirror mirror, int count, int cols) {
        FocusController fc = new FocusController(mirror);
        fc.setColumnsPerRow(cols);
        List<String> initial = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            initial.add("app_" + i);
        }
        mirror.init(initial);
        for (FocusTestView card : mirror.appCards) {
            fc.registerAppTile(card, card.getTag().toString(), false, null);
        }
        return fc;
    }

    // -------------------------------------------------------------------------
    // 1. CONSECUTIVE MULTI-STEP MOVES & DRIFT ELIMINATION
    // -------------------------------------------------------------------------

    @Test
    public void testConsecutiveMultiStepMovesWithoutDrift() {
        MainActivityMirror mirror = new MainActivityMirror();
        FocusController fc = createController(mirror, 12, 6);

        // Start move on app_0 (initially index 0)
        mirror.startMove(fc, "app_0");
        assertTrue(fc.isMoveMode());
        assertEquals("app_0", fc.getMovingKey());

        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        FocusTestKeyEvent rightUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_RIGHT);

        // Move app_0 right consecutively: 0 -> 1 -> 2 -> 3 -> 4 -> 5
        for (int expectedStep = 1; expectedStep <= 5; expectedStep++) {
            boolean downHandled = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
            boolean upHandled = fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightUp);
            assertTrue("ACTION_DOWN should be consumed", downHandled);
            assertTrue("ACTION_UP should be consumed", upHandled);

            int from = expectedStep - 1;
            int to = expectedStep;
            assertEquals(expectedStep, mirror.recordedSteps.size());
            assertEquals("app_0:" + from + "->" + to, mirror.recordedSteps.get(expectedStep - 1));

            // Verify 100% sync across FocusController.appViews, mirror.rowApps, and mirror.appCards
            List<String> fcTags = extractTags(getInternalAppViews(fc));
            assertEquals("FocusController.appViews must match mirror.rowApps at step " + expectedStep,
                    mirror.rowApps, fcTags);
            assertEquals("FocusController.appViews must match mirror.appCards at step " + expectedStep,
                    mirror.getCardTags(), fcTags);
            assertEquals("app_0 must be at index " + to, "app_0", fcTags.get(to));
        }

        // Now move app_0 vertically down: from 5 -> 11 (step = +6)
        FocusTestKeyEvent downDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_DOWN);
        FocusTestKeyEvent downUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_DOWN);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, downDown);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, downUp);

        assertEquals(6, mirror.recordedSteps.size());
        assertEquals("app_0:5->11", mirror.recordedSteps.get(5));
        List<String> fcTagsAfterDown = extractTags(getInternalAppViews(fc));
        assertEquals(mirror.rowApps, fcTagsAfterDown);
        assertEquals("app_0", fcTagsAfterDown.get(11));

        // Now move app_0 back vertically up: from 11 -> 5 (step = -6)
        FocusTestKeyEvent upDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_UP);
        FocusTestKeyEvent upUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_UP);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, upDown);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, upUp);

        assertEquals(7, mirror.recordedSteps.size());
        assertEquals("app_0:11->5", mirror.recordedSteps.get(6));
        List<String> fcTagsAfterUp = extractTags(getInternalAppViews(fc));
        assertEquals(mirror.rowApps, fcTagsAfterUp);
        assertEquals("app_0", fcTagsAfterUp.get(5));

        // Now move app_0 left all the way back: 5 -> 4 -> 3 -> 2 -> 1 -> 0
        FocusTestKeyEvent leftDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_LEFT);
        FocusTestKeyEvent leftUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_LEFT);
        for (int i = 5; i >= 1; i--) {
            fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_LEFT, leftDown);
            fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_LEFT, leftUp);

            List<String> currentTags = extractTags(getInternalAppViews(fc));
            assertEquals(mirror.rowApps, currentTags);
            assertEquals("app_0", currentTags.get(i - 1));
        }

        // Layout returned 100% to initial state!
        List<String> finalTags = extractTags(getInternalAppViews(fc));
        List<String> expectedInitial = Arrays.asList(
                "app_0", "app_1", "app_2", "app_3", "app_4", "app_5",
                "app_6", "app_7", "app_8", "app_9", "app_10", "app_11"
        );
        assertEquals(expectedInitial, finalTags);
        assertEquals(expectedInitial, mirror.rowApps);
    }

    // -------------------------------------------------------------------------
    // 2. OUT-OF-BOUNDS MOVE ATTEMPTS & MISSING KEY RESILIENCE
    // -------------------------------------------------------------------------

    @Test
    public void testOutOfBoundsMoveAttemptsDoNotCrashOrDrift() {
        MainActivityMirror mirror = new MainActivityMirror();
        FocusController fc = createController(mirror, 6, 6); // 1 row of 6 apps

        List<String> baseline = Arrays.asList("app_0", "app_1", "app_2", "app_3", "app_4", "app_5");

        // --- Case A: Out-of-bounds at Left (index 0, step -1) ---
        mirror.startMove(fc, "app_0");
        FocusTestKeyEvent leftDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_LEFT);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_LEFT, leftDown);

        assertTrue("No move steps must be recorded for OOB left", mirror.recordedSteps.isEmpty());
        assertEquals("appViews must remain unchanged", baseline, extractTags(getInternalAppViews(fc)));
        assertEquals("rowApps must remain unchanged", baseline, mirror.rowApps);

        // --- Case B: Out-of-bounds at Top (index 0, step -6) ---
        FocusTestKeyEvent upDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_UP);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, upDown);

        assertTrue("No move steps must be recorded for OOB up", mirror.recordedSteps.isEmpty());
        assertEquals(baseline, extractTags(getInternalAppViews(fc)));

        // --- Case C: Out-of-bounds at Bottom (index 0, step +6 in single-row grid) ---
        FocusTestKeyEvent downDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_DOWN);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, downDown);

        assertTrue("No move steps must be recorded for OOB down", mirror.recordedSteps.isEmpty());
        assertEquals(baseline, extractTags(getInternalAppViews(fc)));

        // Commit app_0
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_CENTER,
                new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER));

        // --- Case D: Out-of-bounds at Right (index 5, step +1) ---
        mirror.startMove(fc, "app_5");
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        fc.handleKeyEvent("app_5", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);

        assertTrue("No move steps must be recorded for OOB right", mirror.recordedSteps.isEmpty());
        assertEquals(baseline, extractTags(getInternalAppViews(fc)));
        assertEquals(baseline, mirror.rowApps);

        fc.handleKeyEvent("app_5", true, KeyEvent.KEYCODE_DPAD_CENTER,
                new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER));

        // --- Case E: Adversarial Key Not Found (Regression test for Bug #30 / from == -1) ---
        // Manually simulate a move key dispatched when movingKey is not in appViews.
        // Old code evaluated (from=-1, to = -1 + 1 = 0), passing (to >= 0 && to < size),
        // and called appViews.remove(-1) -> IndexOutOfBoundsException crash!
        fc.startMove("ghost_key", null);
        assertEquals("ghost_key", fc.getMovingKey());

        // This must NOT crash with IndexOutOfBoundsException!
        boolean handledGhost = fc.handleKeyEvent("ghost_key", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertTrue("KeyEvent should still be consumed", handledGhost);
        assertTrue("Ghost key must not record any steps", mirror.recordedSteps.isEmpty());
        assertEquals("appViews must remain strictly intact", baseline, extractTags(getInternalAppViews(fc)));

        fc.stopMove("ghost_key", false);
        assertFalse(fc.isMoveMode());
    }

    @Test
    public void testEmptyAndSingleElementMoveModeResilience() {
        MainActivityMirror mirror = new MainActivityMirror();

        // 1. Completely empty controller
        FocusController fcEmpty = new FocusController(mirror);
        fcEmpty.startMove("empty_key", null);
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        boolean handled = fcEmpty.handleKeyEvent("empty_key", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertTrue(handled);
        assertTrue(mirror.recordedSteps.isEmpty());
        fcEmpty.stopMove("empty_key", false);

        // 2. Single-element list
        FocusController fcSingle = createController(mirror, 1, 6);
        mirror.startMove(fcSingle, "app_0");

        fcSingle.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_LEFT, rightDown);
        fcSingle.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        fcSingle.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_UP, rightDown);
        fcSingle.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_DOWN, rightDown);

        assertTrue("Single item cannot be moved in any direction", mirror.recordedSteps.isEmpty());
        assertEquals(Collections.singletonList("app_0"), extractTags(getInternalAppViews(fcSingle)));
    }

    // -------------------------------------------------------------------------
    // 3. KEYCODE_BACK CANCEL REVERSION (EXACT INITIAL ORDER RESTORATION)
    // -------------------------------------------------------------------------

    @Test
    public void testBackCancelRevertingToExactInitialTileOrder() {
        MainActivityMirror mirror = new MainActivityMirror();
        FocusController fc = createController(mirror, 6, 6);

        List<String> initialOrder = Arrays.asList("app_0", "app_1", "app_2", "app_3", "app_4", "app_5");
        assertEquals(initialOrder, extractTags(getInternalAppViews(fc)));

        // Start move on app_1 (index 1)
        mirror.startMove(fc, "app_1");
        assertTrue(fc.isMoveMode());
        assertEquals("app_1", fc.getMovingKey());

        // Verify initialAppViews snapshot was taken
        assertEquals(initialOrder, extractTags(getInternalInitialAppViews(fc)));

        // Move app_1 right 3 times: 1 -> 2 -> 3 -> 4
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        for (int i = 0; i < 3; i++) {
            fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        }

        // Verify intermediate perturbed state
        List<String> perturbedOrder = Arrays.asList("app_0", "app_2", "app_3", "app_4", "app_1", "app_5");
        assertEquals(perturbedOrder, extractTags(getInternalAppViews(fc)));
        assertEquals(perturbedOrder, mirror.rowApps);
        assertEquals(perturbedOrder, mirror.getCardTags());

        // Now cancel via KEYCODE_BACK
        FocusTestKeyEvent backDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_BACK);
        FocusTestKeyEvent backUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_BACK);

        // ACTION_DOWN consumes but does NOT stop move yet
        boolean downHandled = fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_BACK, backDown);
        assertTrue("BACK ACTION_DOWN must be consumed", downHandled);
        assertTrue("Move mode must still be active on ACTION_DOWN", fc.isMoveMode());
        assertTrue("No cancels triggered yet", mirror.cancels.isEmpty());

        // ACTION_UP triggers stopMove(key, false)
        boolean upHandled = fc.handleKeyEvent("app_1", true, KeyEvent.KEYCODE_BACK, backUp);
        assertTrue("BACK ACTION_UP must be consumed", upHandled);

        // State assertions after cancel:
        assertFalse("Move mode must be inactive after BACK", fc.isMoveMode());
        assertNull("movingKey must be null after BACK", fc.getMovingKey());

        // 1. FocusController.appViews reverted 100% to exact initial order
        assertEquals("FocusController.appViews must be restored to initial order",
                initialOrder, extractTags(getInternalAppViews(fc)));

        // 2. Mirror rowApps reverted 100% to exact initial order
        assertEquals("mirror.rowApps must be restored to initial order",
                initialOrder, mirror.rowApps);

        // 3. Mirror appCards reverted 100% to exact initial order
        assertEquals("mirror.appCards must be restored to initial order",
                initialOrder, mirror.getCardTags());

        // 4. Initial snapshot in FocusController is cleared
        assertTrue("initialAppViews must be cleared after cancel",
                getInternalInitialAppViews(fc).isEmpty());

        // 5. Callbacks verified: 1 cancel, 0 commits
        assertEquals(1, mirror.cancels.size());
        assertEquals("app_1", mirror.cancels.get(0));
        assertTrue("onMoveCommit must never be called on cancel", mirror.commits.isEmpty());
    }

    @Test
    public void testSequentialMoveCancelFollowedByMoveCommit() {
        MainActivityMirror mirror = new MainActivityMirror();
        FocusController fc = createController(mirror, 4, 6);

        List<String> initial = Arrays.asList("app_0", "app_1", "app_2", "app_3");

        // Cycle 1: Start Move on app_0 -> Move right to 1 -> Cancel with BACK
        mirror.startMove(fc, "app_0");
        FocusTestKeyEvent rightDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_RIGHT);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_DPAD_RIGHT, rightDown);
        assertEquals(Arrays.asList("app_1", "app_0", "app_2", "app_3"), mirror.rowApps);

        FocusTestKeyEvent backUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_BACK);
        fc.handleKeyEvent("app_0", true, KeyEvent.KEYCODE_BACK, backUp);

        // Verify cancelled and restored
        assertEquals(initial, extractTags(getInternalAppViews(fc)));
        assertEquals(initial, mirror.rowApps);

        // Cycle 2: Start Move on app_2 -> Move left to 1 -> Commit with DPAD_CENTER
        mirror.startMove(fc, "app_2");
        FocusTestKeyEvent leftDown = new FocusTestKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_DPAD_LEFT);
        fc.handleKeyEvent("app_2", true, KeyEvent.KEYCODE_DPAD_LEFT, leftDown);

        List<String> expectedCommitted = Arrays.asList("app_0", "app_2", "app_1", "app_3");
        assertEquals(expectedCommitted, extractTags(getInternalAppViews(fc)));
        assertEquals(expectedCommitted, mirror.rowApps);

        FocusTestKeyEvent okUp = new FocusTestKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_DPAD_CENTER);
        fc.handleKeyEvent("app_2", true, KeyEvent.KEYCODE_DPAD_CENTER, okUp);

        // Verify committed
        assertFalse(fc.isMoveMode());
        assertEquals(1, mirror.commits.size());
        assertEquals("app_2", mirror.commits.get(0));
        assertEquals(expectedCommitted, extractTags(getInternalAppViews(fc)));
        assertEquals(expectedCommitted, mirror.rowApps);
    }
}
