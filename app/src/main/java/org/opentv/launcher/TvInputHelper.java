package org.opentv.launcher;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.net.Uri;
import android.view.KeyEvent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;

/**
 * TV Input Framework (TIF) helper for discovering HDMI physical ports and dispatching
 * passthrough streams across a 5-tier fallback chain.
 */
public class TvInputHelper {

    public static final int MAX_INPUTS_DEFAULT = 4;
    private static final String INPUT_PLAYER = "com.google.android.tv.inputplayer";

    private static final String[][] LIVE_TV_HANDLERS = {
        {"com.android.tv", "com.android.tv.MainActivity"},
        {"com.droidlogic.android.tv", "com.android.tv.TvActivity"},
        {"com.mediatek.tv", "com.mediatek.tv.TvActivity"}
    };

    public static class HdmiInput {
        public final String id;
        public final String label;
        public final Uri passthroughUri;
        public final boolean isHidden;

        public HdmiInput(String id, String label, Uri passthroughUri, boolean isHidden) {
            this.id = id;
            this.label = label;
            this.passthroughUri = passthroughUri;
            this.isHidden = isHidden;
        }
    }

    /**
     * Queries physical HDMI TV inputs, filters hidden inputs, sanitizes labels, and sorts deterministically.
     */
    public static List<HdmiInput> queryHdmiInputs(Context context, int maxInputs) {
        List<HdmiInput> result = new ArrayList<>();
        if (context == null) return result;
        TvInputManager tim = (TvInputManager) context.getSystemService(Context.TV_INPUT_SERVICE);
        if (tim == null) return result;

        List<TvInputInfo> inputs;
        try {
            inputs = tim.getTvInputList();
        } catch (Exception e) {
            return result;
        }
        if (inputs == null) return result;

        List<TvInputInfo> filtered = new ArrayList<>();
        for (TvInputInfo in : inputs) {
            if (in == null) continue;
            boolean isHdmi = in.getType() == TvInputInfo.TYPE_HDMI;
            boolean isPhysicalPort = in.getParentId() == null;
            boolean isHidden = false;
            try {
                isHidden = in.isHidden(context);
            } catch (Throwable ignored) {}

            if (isHdmi && isPhysicalPort && !isHidden) {
                filtered.add(in);
            }
        }

        Collections.sort(filtered, new Comparator<TvInputInfo>() {
            @Override
            public int compare(TvInputInfo a, TvInputInfo b) {
                return a.getId().compareTo(b.getId());
            }
        });

        int count = Math.min(filtered.size(), maxInputs > 0 ? maxInputs : MAX_INPUTS_DEFAULT);
        for (int i = 0; i < count; i++) {
            TvInputInfo in = filtered.get(i);
            String rawLabel = resolveLabel(context, in, i + 1);
            String cleanLabel = VendorAdapter.sanitizeHdmiLabel(rawLabel);
            Uri uri = TvContract.buildChannelUriForPassthroughInput(in.getId());
            result.add(new HdmiInput(in.getId(), cleanLabel, uri, false));
        }

        return result;
    }

    private static String resolveLabel(Context context, TvInputInfo in, int indexFallback) {
        try {
            CharSequence custom = in.loadCustomLabel(context);
            if (custom != null && custom.length() > 0) {
                return custom.toString();
            }
        } catch (Exception ignored) {}

        try {
            CharSequence label = in.loadLabel(context);
            if (label != null && label.length() > 0) {
                return label.toString();
            }
        } catch (Exception ignored) {}

        return "HDMI " + indexFallback;
    }

    /**
     * Builds prioritized fallback dispatch chain for physical HDMI input:
     * 1. Google TV Input Player (if resolved default)
     * 2. Stock AOSP / OEM Live TV (com.android.tv, com.droidlogic.android.tv, com.mediatek.tv)
     * 3. Generic Action View on Passthrough URI
     */
    public static List<Intent> buildLaunchIntents(Context context, String inputId) {
        List<Intent> intents = new ArrayList<>();
        if (context == null || inputId == null || inputId.trim().isEmpty()) {
            return intents;
        }
        PackageManager pm = context.getPackageManager();
        Uri uri = TvContract.buildChannelUriForPassthroughInput(inputId);
        Intent baseView = new Intent(Intent.ACTION_VIEW, uri);

        // 1. Google TV Input Player
        try {
            ResolveInfo def = pm.resolveActivity(baseView, PackageManager.MATCH_DEFAULT_ONLY);
            if (def != null && def.activityInfo != null && INPUT_PLAYER.equals(def.activityInfo.packageName)) {
                intents.add(new Intent(baseView).setClassName(INPUT_PLAYER, def.activityInfo.name));
            }
        } catch (Exception ignored) {}

        // 2. Known OEM Live TV Handlers (AOSP Live TV, Droidlogic, MediaTek)
        for (String[] target : LIVE_TV_HANDLERS) {
            Intent t = new Intent(baseView).setClassName(target[0], target[1]);
            try {
                if (t.resolveActivity(pm) != null) {
                    intents.add(t);
                }
            } catch (Exception ignored) {}
        }

        // 3. Generic Action View on Passthrough URI
        intents.add(baseView);
        return intents;
    }

    /**
     * Executes the launch sequence across the 5-tier fallback chain.
     */
    public static boolean launchInput(Context context, String inputId) {
        if (context == null) return false;
        if (inputId != null && !inputId.trim().isEmpty()) {
            List<Intent> tries = buildLaunchIntents(context, inputId);
            for (Intent intent : tries) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                try {
                    context.startActivity(intent);
                    return true;
                } catch (Exception ignored) {}
            }
        }

        // Fallback: hardware KEYCODE_TV_INPUT broadcast
        try {
            Intent keyIntent = new Intent(Intent.ACTION_MAIN);
            keyIntent.addCategory(Intent.CATEGORY_DEFAULT);
            keyIntent.putExtra(Intent.EXTRA_KEY_EVENT, new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_TV_INPUT));
            keyIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.sendBroadcast(keyIntent);
            return true;
        } catch (Exception ignored) {}

        return false;
    }
}
