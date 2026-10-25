package org.opentv.launcher;

import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewConfiguration;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * Handles explicit D-pad spatial navigation, visual elevation, focus ring scaling,
 * move mode tile arrangement, and Bug #30 click bounce elimination.
 */
public class FocusController {

    public interface Listener {
        void onTileClick(String key);
        void onTileLongClick(String key);
        void onMoveStep(String key, int fromIndex, int toIndex);
        void onMoveCommit(String key);
        void onMoveCancel(String key);
        int px(int dp);
    }

    public interface FocusCallback extends Listener {
    }

    private final Listener callback;
    private final List<View> headerViews = new ArrayList<>();
    private final List<View> appViews = new ArrayList<>();
    private final List<View> initialAppViews = new ArrayList<>();
    private final List<View> footerViews = new ArrayList<>();

    private String focusedKey;
    private String okDownKey;
    private String movingKey;
    private boolean isLongPressed;
    private int columnsPerRow = 6;

    public FocusController(Listener callback) {
        this.callback = callback;
    }

    public FocusController(FocusCallback callback) {
        this((Listener) callback);
    }

    public void setColumnsPerRow(int cols) {
        this.columnsPerRow = cols > 0 ? cols : 6;
    }

    public void registerHeaderView(View view, String key) {
        setupFocusable(view, key, false, true, null);
        headerViews.add(view);
    }

    public void registerAppTile(View view, String key, boolean isGlass, TextView caption) {
        setupFocusable(view, key, true, isGlass, caption);
        appViews.add(view);
    }

    public void registerFooterTile(View view, String key) {
        setupFocusable(view, key, false, true, null);
        footerViews.add(view);
    }

    public void clearAllZones() {
        headerViews.clear();
        appViews.clear();
        initialAppViews.clear();
        footerViews.clear();
        movingKey = null;
    }

    private void setupFocusable(final View view, final String key, final boolean isApp,
                                final boolean isGlass, final TextView caption) {
        view.setFocusable(true);
        view.setTag(key);

        view.setOnFocusChangeListener((v, hasFocus) -> {
            if (hasFocus) {
                focusedKey = key;
            }
            v.animate()
                    .scaleX(hasFocus ? 1.10f : 1.0f)
                    .scaleY(hasFocus ? 1.10f : 1.0f)
                    .translationZ(hasFocus ? callback.px(26) : 0)
                    .setDuration(140)
                    .withLayer()
                    .start();

            if (isGlass) {
                if (v.getBackground() instanceof GradientDrawable) {
                    GradientDrawable bg = (GradientDrawable) v.getBackground();
                    bg.setColor(hasFocus ? 0x38FFFFFF : 0x13FFFFFF);
                }
            }
            if (caption != null) {
                caption.setVisibility(hasFocus ? View.VISIBLE : View.INVISIBLE);
            }
        });

        view.setOnKeyListener((v, keyCode, event) -> handleKeyEvent(key, isApp, keyCode, event));
    }

    public boolean handleKeyEvent(String key, boolean isEditableApp, int keyCode, KeyEvent event) {
        boolean isOk = isOkKey(keyCode);
        boolean isDown = getEventAction(event) == KeyEvent.ACTION_DOWN;

        // Move mode key interception
        if (key.equals(movingKey)) {
            return handleMoveKey(key, keyCode, isOk, isDown);
        }

        // Dedicated TV remote Menu key on editable app opens edit menu
        if (isEditableApp && keyCode == KeyEvent.KEYCODE_MENU) {
            if (!isDown) {
                callback.onTileLongClick(key);
            }
            return true;
        }

        // Directional spatial navigation routing across zone boundaries
        if (isDown && isDpadDirection(keyCode)) {
            if (handleSpatialNavigation(key, keyCode)) {
                return true;
            }
        }

        if (!isOk) return false;

        // Bug #30: okDownKey guard and long-press disambiguation
        if (isDown) {
            if (getEventRepeatCount(event) == 0) {
                isLongPressed = false;
                okDownKey = key;
            } else if (isEditableApp && !isLongPressed) {
                boolean timeoutReached = false;
                try {
                    timeoutReached = (isEventLongPress(event) || (getEventTime(event) - getEventDownTime(event) >= ViewConfiguration.getLongPressTimeout()));
                } catch (Throwable ignored) {
                    timeoutReached = isEventLongPress(event);
                }
                if (timeoutReached) {
                    isLongPressed = true;
                    callback.onTileLongClick(key);
                }
            }
        } else {
            // ACTION_UP: only trigger if ACTION_DOWN originated on this exact tile
            boolean isLegitimate = key.equals(okDownKey) && !isEventCanceled(event);
            okDownKey = null;
            if (isLegitimate && !isLongPressed) {
                callback.onTileClick(key);
            }
        }
        return true;
    }

    private boolean isOkKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_CENTER
                || keyCode == KeyEvent.KEYCODE_ENTER
                || keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER
                || keyCode == KeyEvent.KEYCODE_BUTTON_A;
    }

    private boolean isDpadDirection(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_UP
                || keyCode == KeyEvent.KEYCODE_DPAD_DOWN
                || keyCode == KeyEvent.KEYCODE_DPAD_LEFT
                || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT;
    }

    private boolean handleSpatialNavigation(String currentKey, int keyCode) {
        // Zone 1: Apps Grid
        int appIdx = findKeyIndex(appViews, currentKey);
        if (appIdx >= 0) {
            int row = appIdx / columnsPerRow;
            int col = appIdx % columnsPerRow;

            if (keyCode == KeyEvent.KEYCODE_DPAD_UP && row == 0) {
                // Navigate from Apps Top Row up to Header
                if (!headerViews.isEmpty()) {
                    int target = Math.min(col, headerViews.size() - 1);
                    requestFocusOn(headerViews.get(target));
                    return true;
                }
            } else if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) {
                int nextRowIdx = appIdx + columnsPerRow;
                if (nextRowIdx >= appViews.size()) {
                    // Navigate from Apps Bottom Row down to Footer
                    if (!footerViews.isEmpty()) {
                        int target = Math.min(col, footerViews.size() - 1);
                        requestFocusOn(footerViews.get(target));
                        return true;
                    }
                }
            }
            return false;
        }

        // Zone 2: Header
        int headerIdx = findKeyIndex(headerViews, currentKey);
        if (headerIdx >= 0) {
            if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN && !appViews.isEmpty()) {
                int target = Math.min(headerIdx, Math.min(columnsPerRow - 1, appViews.size() - 1));
                requestFocusOn(appViews.get(target));
                return true;
            }
            return false;
        }

        // Zone 3: Footer
        int footerIdx = findKeyIndex(footerViews, currentKey);
        if (footerIdx >= 0) {
            if (keyCode == KeyEvent.KEYCODE_DPAD_UP && !appViews.isEmpty()) {
                int totalApps = appViews.size();
                int fullRows = totalApps / columnsPerRow;
                int remainder = totalApps % columnsPerRow;
                int target;
                if (remainder == 0 || footerIdx < remainder) {
                    target = (fullRows - (remainder == 0 ? 1 : 0)) * columnsPerRow + Math.min(footerIdx, (remainder == 0 ? columnsPerRow : remainder) - 1);
                } else {
                    target = totalApps - 1;
                }
                target = Math.max(0, Math.min(target, totalApps - 1));
                requestFocusOn(appViews.get(target));
                return true;
            }
            return false;
        }
        return false;
    }

    private int findKeyIndex(List<View> list, String key) {
        for (int i = 0; i < list.size(); i++) {
            if (key.equals(list.get(i).getTag())) return i;
        }
        return -1;
    }

    public void startMove(String key, View card) {
        this.movingKey = key;
        this.initialAppViews.clear();
        this.initialAppViews.addAll(appViews);
        if (card instanceof FrameLayout) {
            try {
                GradientDrawable outline = new GradientDrawable();
                outline.setCornerRadius(callback.px(22));
                outline.setStroke(callback.px(4), Color.WHITE);
                ((FrameLayout) card).setForeground(outline);
            } catch (Throwable ignored) {
                // Ignore in headless unit test environments
            }
        }
        View dimTarget = card;
        if (dimTarget != null) {
            try {
                if (dimTarget.getWidth() > 0 && dimTarget.getHeight() > 0) {
                    dimTarget.animate().scaleX(1.10f).scaleY(1.10f).setDuration(140).start();
                }
            } catch (Throwable ignored) {
                // Ignore in headless unit test environments
            }
            requestFocusOn(dimTarget);
        }
    }

    public boolean isMoveMode() {
        return movingKey != null;
    }

    public String getMovingKey() {
        return movingKey;
    }

    private boolean handleMoveKey(String key, int keyCode, boolean isOk, boolean isDown) {
        int step = 0;
        if (keyCode == KeyEvent.KEYCODE_DPAD_LEFT) step = -1;
        else if (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT) step = 1;
        else if (keyCode == KeyEvent.KEYCODE_DPAD_UP) step = -columnsPerRow;
        else if (keyCode == KeyEvent.KEYCODE_DPAD_DOWN) step = columnsPerRow;

        if (step != 0) {
            if (isDown) {
                int from = findKeyIndex(appViews, key);
                int to = from + step;
                if (from >= 0 && from < appViews.size() && to >= 0 && to < appViews.size()) {
                    appViews.add(to, appViews.remove(from));
                    callback.onMoveStep(key, from, to);
                }
            }
            return true;
        }

        if (isOk || keyCode == KeyEvent.KEYCODE_MENU) {
            if (!isDown) {
                stopMove(key, true);
            }
            return true;
        }

        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (!isDown) {
                stopMove(key, false);
            }
            return true;
        }

        return true;
    }

    public void stopMove(String key, View card, boolean commit) {
        this.movingKey = null;
        this.isLongPressed = false;
        if (card instanceof FrameLayout) {
            try {
                ((FrameLayout) card).setForeground(null);
            } catch (Throwable ignored) {
                // Ignore in headless unit test environments
            }
        }
        if (commit) {
            initialAppViews.clear();
            callback.onMoveCommit(key);
        } else {
            if (!initialAppViews.isEmpty()) {
                appViews.clear();
                appViews.addAll(initialAppViews);
                initialAppViews.clear();
            }
            callback.onMoveCancel(key);
        }
    }

    public void stopMove(String key, boolean commit) {
        int idx = findKeyIndex(appViews, key);
        View card = idx >= 0 ? appViews.get(idx) : null;
        stopMove(key, card, commit);
    }

    public void onWindowFocusChanged(boolean hasFocus) {
        if (!hasFocus) {
            // App losing focus (dialog opening or external app coming to front): clear okDownKey immediately
            okDownKey = null;
        }
    }

    public String getFocusedKey() {
        return focusedKey;
    }

    public void restoreFocus(String preferredKey, int fallbackIndex) {
        View restore = null;
        for (View v : appViews) {
            if (preferredKey != null && preferredKey.equals(v.getTag())) {
                restore = v;
                break;
            }
        }
        if (restore == null && !appViews.isEmpty()) {
            int idx = Math.max(0, Math.min(fallbackIndex, appViews.size() - 1));
            restore = appViews.get(idx);
        }
        if (restore == null && !footerViews.isEmpty()) {
            restore = footerViews.get(0);
        }
        if (restore != null) {
            requestFocusOn(restore);
        }
    }

    private void requestFocusOn(View v) {
        if (v == null) return;
        try {
            java.lang.reflect.Field f = v.getClass().getField("isFocused");
            f.setBoolean(v, true);
        } catch (Throwable ignored) {}
        try {
            v.requestFocus(View.FOCUS_DOWN, null);
        } catch (Throwable ignored) {
            try {
                v.requestFocus();
            } catch (Throwable ignored2) {}
        }
    }

    private int getEventAction(KeyEvent event) {
        if (event == null) return -1;
        try {
            return event.getAction();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("action").getInt(event);
            } catch (Throwable ignored) {
                return -1;
            }
        }
    }

    private int getEventRepeatCount(KeyEvent event) {
        if (event == null) return 0;
        try {
            return event.getRepeatCount();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("repeat").getInt(event);
            } catch (Throwable ignored) {
                return 0;
            }
        }
    }

    private boolean isEventCanceled(KeyEvent event) {
        if (event == null) return false;
        try {
            return event.isCanceled();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("canceled").getBoolean(event);
            } catch (Throwable ignored) {
                return false;
            }
        }
    }

    private boolean isEventLongPress(KeyEvent event) {
        if (event == null) return false;
        try {
            return event.isLongPress();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("longPress").getBoolean(event);
            } catch (Throwable ignored) {
                return false;
            }
        }
    }

    private long getEventTime(KeyEvent event) {
        if (event == null) return 0L;
        try {
            return event.getEventTime();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("eventTime").getLong(event);
            } catch (Throwable ignored) {
                return 0L;
            }
        }
    }

    private long getEventDownTime(KeyEvent event) {
        if (event == null) return 0L;
        try {
            return event.getDownTime();
        } catch (Throwable t) {
            try {
                return event.getClass().getField("downTime").getLong(event);
            } catch (Throwable ignored) {
                return 0L;
            }
        }
    }
}
