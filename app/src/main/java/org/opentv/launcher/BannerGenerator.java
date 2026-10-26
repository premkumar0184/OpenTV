package org.opentv.launcher;

import android.content.res.Resources;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Dynamic Sideload Banner Generator & In-Memory LRU Cache.
 * Feature F7 / Milestone 7:
 * When a sideloaded Android TV or mobile APK does not declare a Leanback landscape banner,
 * BannerGenerator synthesizes a 16:9 landscape banner canvas (320x180 dp equivalent)
 * featuring:
 * 1. Palette color extraction from the high-res square application icon.
 * 2. Tone-clamped OLED-safe subtle background gradient.
 * 3. High-resolution centered app icon and crisp sans-serif typography.
 * 4. High-performance LRU cache ensuring 60fps smooth D-pad grid scrolling.
 */
public class BannerGenerator {

    public static final int DEFAULT_BG_TOP = 0xFF242028;
    public static final int DEFAULT_BG_BOTTOM = 0xFF100E12;
    public static final int DEFAULT_CACHE_SIZE = 64;

    private static volatile BannerGenerator sInstance;
    private final BannerLruCache mCache;

    /**
     * Thread-safe LRU cache for synthesized launcher banners.
     */
    public static class BannerLruCache {
        private final int maxEntries;
        private final LinkedHashMap<String, Bitmap> map;
        private int hitCount = 0;
        private int missCount = 0;
        private int evictionCount = 0;

        public BannerLruCache(final int maxEntries) {
            this.maxEntries = Math.max(1, maxEntries);
            this.map = new LinkedHashMap<String, Bitmap>(maxEntries, 0.75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, Bitmap> eldest) {
                    boolean shouldEvict = size() > BannerLruCache.this.maxEntries;
                    if (shouldEvict) {
                        evictionCount++;
                    }
                    return shouldEvict;
                }
            };
        }

        public synchronized Bitmap get(String key) {
            if (key == null) return null;
            Bitmap b = map.get(key);
            if (b != null) {
                hitCount++;
                return b;
            }
            missCount++;
            return null;
        }

        public synchronized void put(String key, Bitmap bitmap) {
            if (key != null && bitmap != null) {
                map.put(key, bitmap);
            }
        }

        public synchronized void clear() {
            map.clear();
        }

        public synchronized int size() {
            return map.size();
        }

        public synchronized int getMaxEntries() {
            return maxEntries;
        }

        public synchronized int getHitCount() {
            return hitCount;
        }

        public synchronized int getMissCount() {
            return missCount;
        }

        public synchronized int getEvictionCount() {
            return evictionCount;
        }
    }

    public static BannerGenerator getInstance() {
        if (sInstance == null) {
            synchronized (BannerGenerator.class) {
                if (sInstance == null) {
                    sInstance = new BannerGenerator(DEFAULT_CACHE_SIZE);
                }
            }
        }
        return sInstance;
    }

    public BannerGenerator(int cacheCapacity) {
        this.mCache = new BannerLruCache(cacheCapacity);
    }

    public BannerLruCache getCache() {
        return mCache;
    }

    /**
     * Checks if given dimensions match a 16:9 aspect ratio within a 5% tolerance.
     */
    public static boolean is16to9(int width, int height) {
        if (height <= 0 || width <= 0) return false;
        float ratio = (float) width / (float) height;
        return Math.abs(ratio - (16.0f / 9.0f)) <= 0.05f;
    }

    /**
     * Extracts a dominant representative color from an array of ARGB pixels.
     * Filters out transparency and near-black/near-white extremes.
     */
    public static int extractDominantColor(int[] pixels) {
        if (pixels == null || pixels.length == 0) {
            return DEFAULT_BG_TOP;
        }

        long rSum = 0, gSum = 0, bSum = 0;
        int validCount = 0;

        for (int pixel : pixels) {
            int a = (pixel >> 24) & 0xFF;
            if (a < 128) continue; // Skip transparent background

            int r = (pixel >> 16) & 0xFF;
            int g = (pixel >> 8) & 0xFF;
            int b = pixel & 0xFF;

            // Compute perceived luminance (Rec. 601)
            double lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0;
            if (lum < 0.08 || lum > 0.92) continue; // Ignore extreme highlights & shadows

            rSum += r;
            gSum += g;
            bSum += b;
            validCount++;
        }

        if (validCount == 0) {
            return DEFAULT_BG_TOP;
        }

        int avgR = (int) (rSum / validCount);
        int avgG = (int) (gSum / validCount);
        int avgB = (int) (bSum / validCount);

        return 0xFF000000 | (avgR << 16) | (avgG << 8) | avgB;
    }

    /**
     * Clamps a raw color to a dark, comfortable OLED/TV background tone
     * (~18% to 28% luminance) in pure Java.
     */
    public static int clampDarkTone(int color) {
        int r = (color >> 16) & 0xFF;
        int g = (color >> 8) & 0xFF;
        int b = color & 0xFF;

        double lum = (0.299 * r + 0.587 * g + 0.114 * b);
        if (lum <= 0) return DEFAULT_BG_TOP;

        // Target luminance ~50 on 0-255 scale
        double scale = 50.0 / Math.max(1.0, lum);
        scale = Math.min(scale, 1.2);
        scale = Math.max(scale, 0.18);

        int cr = Math.min(255, Math.max(16, (int) (r * scale)));
        int cg = Math.min(255, Math.max(16, (int) (g * scale)));
        int cb = Math.min(255, Math.max(16, (int) (b * scale)));

        return 0xFF000000 | (cr << 16) | (cg << 8) | cb;
    }

    /**
     * Generates a 2-stop gradient array [topColor, bottomColor] for the banner.
     */
    public static int[] generateGradientColors(int dominantColor) {
        int top = clampDarkTone(dominantColor);
        int bottom = DEFAULT_BG_BOTTOM;
        return new int[]{top, bottom};
    }

    /**
     * Synthesizes a 16:9 banner canvas from an app's square icon and label.
     */
    public static Bitmap createSynthesizedBanner(String label, Drawable appIcon, int width, int height) {
        if (width <= 0 || height <= 0) {
            width = 320;
            height = 180;
        }

        Bitmap bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(bitmap);

        // 1. Extract dominant color from icon
        int dominant = DEFAULT_BG_TOP;
        if (appIcon != null) {
            try {
                int iconW = Math.max(1, appIcon.getIntrinsicWidth() > 0 ? appIcon.getIntrinsicWidth() : 64);
                int iconH = Math.max(1, appIcon.getIntrinsicHeight() > 0 ? appIcon.getIntrinsicHeight() : 64);
                int sampleW = Math.min(iconW, 32);
                int sampleH = Math.min(iconH, 32);

                Bitmap sampleBmp = Bitmap.createBitmap(sampleW, sampleH, Bitmap.Config.ARGB_8888);
                Canvas sampleCanvas = new Canvas(sampleBmp);
                appIcon.setBounds(0, 0, sampleW, sampleH);
                appIcon.draw(sampleCanvas);

                int[] pixels = new int[sampleW * sampleH];
                sampleBmp.getPixels(pixels, 0, sampleW, 0, 0, sampleW, sampleH);
                dominant = extractDominantColor(pixels);
                sampleBmp.recycle();
            } catch (Exception ignored) {
                dominant = DEFAULT_BG_TOP;
            }
        }

        int[] gradient = generateGradientColors(dominant);

        // 2. Draw subtle linear gradient background
        Paint bgPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        Shader shader = new LinearGradient(
                0, 0, width, height,
                gradient[0], gradient[1],
                Shader.TileMode.CLAMP
        );
        bgPaint.setShader(shader);
        RectF bounds = new RectF(0, 0, width, height);
        canvas.drawRoundRect(bounds, 16f, 16f, bgPaint);

        // 3. Subtle inner border highlight
        Paint borderPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        borderPaint.setStyle(Paint.Style.STROKE);
        borderPaint.setStrokeWidth(2f);
        borderPaint.setColor(0x1AFFFFFF);
        canvas.drawRoundRect(bounds, 16f, 16f, borderPaint);

        // 4. Draw centered square app icon
        if (appIcon != null) {
            int iconSize = (int) (height * 0.48f);
            int iconLeft = (width - iconSize) / 2;
            int iconTop = (int) (height * 0.16f);
            appIcon.setBounds(iconLeft, iconTop, iconLeft + iconSize, iconTop + iconSize);
            appIcon.draw(canvas);

            // 5. Draw clean typography for app label below icon
            if (label != null && !label.isEmpty()) {
                Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
                textPaint.setColor(0xE6FFFFFF);
                textPaint.setTextSize(height * 0.13f);
                textPaint.setTypeface(Typeface.create(Typeface.SANS_SERIF, Typeface.NORMAL));
                textPaint.setTextAlign(Paint.Align.CENTER);

                float maxTextW = width * 0.85f;
                String displayLabel = label;
                if (textPaint.measureText(displayLabel) > maxTextW) {
                    while (displayLabel.length() > 3 && textPaint.measureText(displayLabel + "...") > maxTextW) {
                        displayLabel = displayLabel.substring(0, displayLabel.length() - 1);
                    }
                    displayLabel = displayLabel + "...";
                }

                float textY = iconTop + iconSize + (height * 0.20f);
                canvas.drawText(displayLabel, width / 2.0f, textY, textPaint);
            }
        }

        return bitmap;
    }

    /**
     * Retrieves or generates a cached 16:9 banner bitmap for the specified package.
     */
    public Bitmap getOrCreateBanner(String pkg, String label, Drawable appIcon, int width, int height) {
        if (pkg == null) {
            return createSynthesizedBanner(label, appIcon, width, height);
        }
        Bitmap cached = mCache.get(pkg);
        if (cached != null && !cached.isRecycled()) {
            return cached;
        }
        Bitmap generated = createSynthesizedBanner(label, appIcon, width, height);
        mCache.put(pkg, generated);
        return generated;
    }

    /**
     * Retrieves or generates a cached 16:9 banner BitmapDrawable for the specified package.
     */
    public Drawable getOrCreateBannerDrawable(Resources res, String pkg, String label, Drawable appIcon, int width, int height) {
        Bitmap b = getOrCreateBanner(pkg, label, appIcon, width, height);
        return new BitmapDrawable(res, b);
    }
}
