package org.opentv.launcher;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.provider.Settings;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Hardware and vendor adaptations for TCL, Philips, Sony, and generic TV platforms.
 */
public class VendorAdapter {

    public enum Brand {
        TCL, PHILIPS, SONY, GENERIC
    }

    public static final String TCL_SHOW_WINDOW = "com.tcl.settings.SHOW_WINDOW";
    public static final String TCL_PACKAGE = "com.tcl.settings";
    public static final String TCL_SERVICE = "com.tcl.settings.ShowWindowService";

    public static final String SONY_QUICKLAUNCHER_PACKAGE = "com.sony.dtv.systemui.quicklauncher";
    public static final String SONY_QUICKLAUNCHER_ACTIVITY = "com.sony.dtv.systemui.quicklauncher.LaunchActivity";

    private static final Pattern PHILIPS_LABEL_PATTERN = Pattern.compile("&([A-Z][A-Z0-9_]{2,})$");

    public static Brand detectBrand() {
        String mfg = Build.MANUFACTURER != null ? Build.MANUFACTURER.toLowerCase() : "";
        String brand = Build.BRAND != null ? Build.BRAND.toLowerCase() : "";

        if (mfg.contains("tcl") || brand.contains("tcl") || brand.contains("ffalcon") || mfg.contains("tte")) {
            return Brand.TCL;
        }
        if (mfg.contains("philips") || brand.contains("philips") || brand.contains("tpv")) {
            return Brand.PHILIPS;
        }
        if (mfg.contains("sony") || brand.contains("sony")) {
            return Brand.SONY;
        }
        return Brand.GENERIC;
    }

    public static boolean isTcl() {
        return detectBrand() == Brand.TCL;
    }

    public static boolean isPhilips() {
        return detectBrand() == Brand.PHILIPS;
    }

    public static boolean isSony() {
        return detectBrand() == Brand.SONY;
    }

    /**
     * Strips vendor suffixes (e.g. Philips '&COMPUTER', '&BLURAY', '&GAME').
     */
    public static String sanitizeHdmiLabel(String label) {
        if (!isPhilips()) {
            return label;
        }
        return stripDeviceType(label);
    }

    public static String stripDeviceType(String label) {
        if (label == null) return "HDMI";
        Matcher matcher = PHILIPS_LABEL_PATTERN.matcher(label);
        if (matcher.find()) {
            int ampIndex = label.lastIndexOf('&');
            if (ampIndex > 0) {
                return label.substring(0, ampIndex).trim();
            }
        }
        return label;
    }

    /**
     * Opens TCL proprietary ShowWindowService panel ("SoundPreset" or "picture").
     */
    public static boolean openTclPanel(Context context, String panelType) {
        Intent serviceIntent = new Intent(TCL_SHOW_WINDOW)
                .setClassName(TCL_PACKAGE, TCL_SERVICE)
                .putExtra("Type", panelType);

        PackageManager pm = context.getPackageManager();
        if (pm.resolveService(serviceIntent, 0) != null) {
            try {
                context.startService(serviceIntent);
                return true;
            } catch (Exception ignored) {}
        }
        return false;
    }

    /**
     * Generates candidate Intents for a given Quick Settings key ("sound", "picture", "bluetooth", "settings").
     */
    public static List<Intent> getQuickSettingIntents(Context context, String shortcutName) {
        List<Intent> candidates = new ArrayList<>();
        PackageManager pm = context.getPackageManager();

        switch (shortcutName.toLowerCase()) {
            case "sound":
                if (isTcl()) {
                    Intent tclIntent = new Intent(TCL_SHOW_WINDOW)
                            .setClassName(TCL_PACKAGE, TCL_SERVICE)
                            .putExtra("Type", "SoundPreset");
                    if (pm.resolveService(tclIntent, 0) != null) candidates.add(tclIntent);
                }
                candidates.add(new Intent(Settings.ACTION_SOUND_SETTINGS));
                break;

            case "picture":
                if (isTcl()) {
                    Intent tclIntent = new Intent(TCL_SHOW_WINDOW)
                            .setClassName(TCL_PACKAGE, TCL_SERVICE)
                            .putExtra("Type", "picture");
                    if (pm.resolveService(tclIntent, 0) != null) candidates.add(tclIntent);
                    candidates.add(new Intent().setClassName(TCL_PACKAGE, "com.tcl.settings.PictureActivity"));
                }
                candidates.add(new Intent("com.android.tv.settings.device.displaysound.DisplaySoundActivity")
                        .setPackage("com.android.tv.settings"));
                candidates.add(new Intent(Settings.ACTION_DISPLAY_SETTINGS));
                break;

            case "bluetooth":
                candidates.add(new Intent(Settings.ACTION_BLUETOOTH_SETTINGS));
                candidates.add(new Intent("com.google.android.intent.action.CONNECT_INPUT"));
                break;

            case "settings":
                if (isSony()) {
                    candidates.add(new Intent().setClassName(SONY_QUICKLAUNCHER_PACKAGE, SONY_QUICKLAUNCHER_ACTIVITY));
                }
                candidates.add(new Intent(Settings.ACTION_SETTINGS));
                break;
        }

        List<Intent> resolvable = new ArrayList<>();
        for (Intent intent : candidates) {
            boolean isService = TCL_SHOW_WINDOW.equals(intent.getAction());
            if (isService) {
                if (pm.resolveService(intent, 0) != null) resolvable.add(intent);
            } else {
                if (intent.resolveActivity(pm) != null) resolvable.add(intent);
            }
        }
        return resolvable;
    }

    /**
     * Dispatches the quickest resolvable setting screen.
     */
    public static boolean dispatchQuickSetting(Context context, String shortcutName) {
        List<Intent> intents = getQuickSettingIntents(context, shortcutName);
        for (Intent intent : intents) {
            try {
                if (TCL_SHOW_WINDOW.equals(intent.getAction())) {
                    context.startService(intent);
                } else {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(intent);
                }
                return true;
            } catch (Exception ignored) {}
        }
        return false;
    }

    /**
     * Checks if SetupWraith is active or device is unprovisioned, warning against disabling stock launcher.
     */
    public static boolean isSetupWraithRisk(Context context) {
        try {
            int provisioned = Settings.Global.getInt(context.getContentResolver(), "device_provisioned", 0);
            if (provisioned == 0) return true;
        } catch (Exception ignored) {}

        PackageManager pm = context.getPackageManager();
        try {
            pm.getPackageInfo("com.google.android.tungsten.setupwraith", 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }
}
