package org.opentv.launcher;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;

/**
 * Service providing OLED burn-in protection:
 * - 180-second inactivity timer dispatching Daydream screensaver or screen dimming
 * - Periodic +/-2px subpixel micro-drift orbit
 * - Pure black #000000 color tokens
 */
public class OledProtectionService {

    public static final long DEFAULT_INACTIVITY_TIMEOUT_MS = 180_000L; // 180s
    public static final long PIXEL_SHIFT_INTERVAL_MS = 60_000L;        // 60s
    public static final int PURE_BLACK_COLOR = 0xFF000000;             // #000000

    // Orbital micro-shift coordinates within [-2, +2] px bounds
    private static final int[][] SHIFT_ORBIT = {
        {0, 0}, {1, 0}, {2, 1}, {1, 2}, {0, 2}, {-1, 1}, {-2, 0}, {-1, -1}, {0, -2}, {1, -1}
    };

    private final Handler handler;
    private Activity activity;
    private View[] shiftViews;
    private long inactivityTimeoutMs = DEFAULT_INACTIVITY_TIMEOUT_MS;
    private boolean pixelShiftEnabled = true;
    private int shiftIndex = 0;
    private boolean isDimmed = false;

    public OledProtectionService() {
        Handler h = null;
        try {
            Looper looper = Looper.getMainLooper();
            if (looper != null) {
                h = new Handler(looper);
            }
        } catch (Throwable ignored) {}
        this.handler = h;
    }

    private final Runnable inactivityRunnable = new Runnable() {
        @Override
        public void run() {
            triggerDaydreamOrDim();
        }
    };

    private final Runnable pixelShiftRunnable = new Runnable() {
        @Override
        public void run() {
            stepPixelShift();
            if (pixelShiftEnabled && handler != null) {
                handler.postDelayed(this, PIXEL_SHIFT_INTERVAL_MS);
            }
        }
    };

    public void attach(Activity activity, View... shiftViews) {
        this.activity = activity;
        this.shiftViews = shiftViews;
        resetInactivityTimer();
        if (pixelShiftEnabled) {
            startPixelShift();
        }
    }

    public void detach() {
        stopInactivityTimer();
        stopPixelShift();
        restoreNormalState();
        this.activity = null;
        this.shiftViews = null;
    }

    public void configure(long timeoutSeconds, boolean pixelShift) {
        this.inactivityTimeoutMs = timeoutSeconds > 0 ? timeoutSeconds * 1000L : DEFAULT_INACTIVITY_TIMEOUT_MS;
        this.pixelShiftEnabled = pixelShift;
        resetInactivityTimer();
        if (pixelShiftEnabled) {
            startPixelShift();
        } else {
            stopPixelShift();
            resetShiftPositions();
        }
    }

    /**
     * Invoked on any remote D-pad or key event in MainActivity.
     */
    public void onUserInteraction() {
        if (isDimmed) {
            restoreNormalState();
        }
        resetInactivityTimer();
    }

    public void resetInactivityTimer() {
        if (handler != null) {
            handler.removeCallbacks(inactivityRunnable);
            handler.postDelayed(inactivityRunnable, inactivityTimeoutMs);
        }
    }

    public void stopInactivityTimer() {
        if (handler != null) {
            handler.removeCallbacks(inactivityRunnable);
        }
    }

    private void startPixelShift() {
        if (handler != null) {
            handler.removeCallbacks(pixelShiftRunnable);
            handler.postDelayed(pixelShiftRunnable, PIXEL_SHIFT_INTERVAL_MS);
        }
    }

    private void stopPixelShift() {
        if (handler != null) {
            handler.removeCallbacks(pixelShiftRunnable);
        }
    }

    /**
     * Shifts registered static views by +/-1-2px along the orbital sequence.
     */
    public void stepPixelShift() {
        if (shiftViews == null || shiftViews.length == 0) return;
        shiftIndex = (shiftIndex + 1) % SHIFT_ORBIT.length;
        int dx = SHIFT_ORBIT[shiftIndex][0];
        int dy = SHIFT_ORBIT[shiftIndex][1];

        for (View view : shiftViews) {
            if (view != null) {
                view.setTranslationX(dx);
                view.setTranslationY(dy);
            }
        }
    }

    private void resetShiftPositions() {
        if (shiftViews == null) return;
        for (View view : shiftViews) {
            if (view != null) {
                view.setTranslationX(0f);
                view.setTranslationY(0f);
            }
        }
    }

    /**
     * Triggers Daydream screensaver via AOSP Somnambulator or dims window to 5%.
     */
    public void triggerDaydreamOrDim() {
        if (activity == null || activity.isFinishing()) return;

        // Try standard Daydream Somnambulator
        Intent dream = new Intent(Intent.ACTION_MAIN)
                .setClassName("com.android.systemui", "com.android.systemui.Somnambulator")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            activity.startActivity(dream);
            return;
        } catch (Exception ignored) {}

        // Fallback: Dim the window
        try {
            WindowManager.LayoutParams lp = activity.getWindow().getAttributes();
            lp.screenBrightness = 0.05f;
            activity.getWindow().setAttributes(lp);
            isDimmed = true;
        } catch (Exception ignored) {}
    }

    private void restoreNormalState() {
        if (activity == null || !isDimmed) return;
        try {
            WindowManager.LayoutParams lp = activity.getWindow().getAttributes();
            lp.screenBrightness = WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
            activity.getWindow().setAttributes(lp);
            isDimmed = false;
        } catch (Exception ignored) {}
    }

    public static boolean isOledDevice() {
        String model = "";
        String display = "";
        try {
            if (Build.MODEL != null) model = Build.MODEL.toUpperCase();
            if (Build.DISPLAY != null) display = Build.DISPLAY.toUpperCase();
        } catch (Throwable ignored) {}
        return model.contains("OLED") || display.contains("OLED")
                || model.contains("A80") || model.contains("A90") || model.contains("A95");
    }
}
