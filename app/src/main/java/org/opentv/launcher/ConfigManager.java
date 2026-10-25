package org.opentv.launcher;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Environment;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Multi-tier configuration manager:
 * 1. Intent extras with timestamp anti-replay stamp verification
 * 2. External JSON configuration files (primary scoped, secondary legacy)
 * 3. SharedPreferences persistence
 * 4. Default apps.txt and built-in fallbacks
 */
public class ConfigManager {

    public static final String PREFS_NAME = "opentv_config";
    public static final String ACTION_RELOAD_CONFIG = "org.opentv.launcher.RELOAD_CONFIG";

    public static final String KEY_STAMP = "stamp";
    public static final String KEY_APPS = "apps";
    public static final String KEY_QUICK = "quick";
    public static final String KEY_THEME = "theme";
    public static final String KEY_OLED_TIMEOUT = "oled_idle_seconds";
    public static final String KEY_OLED_PIXEL_SHIFT = "oled_pixel_shift";

    public static final String THEME_OLED_BLACK = "OLED_Black";
    public static final String THEME_DUSK = "Dusk";

    public static final List<String> DEFAULT_APPS = Arrays.asList(
        "com.google.android.youtube.tv",
        "com.netflix.ninja",
        "com.amazon.amazonvideo.livingroom",
        "com.disney.disneyplus",
        "com.hulu.livingroomplus",
        "com.wbd.stream"
    );

    public interface OnConfigReloadListener {
        void onConfigReloaded(LauncherConfig config);
    }

    public static class HdmiConfig {
        public String id;
        public String title;
        public boolean visible;

        public HdmiConfig(String id, String title, boolean visible) {
            this.id = id;
            this.title = title;
            this.visible = visible;
        }
    }

    public static class OledConfig {
        public int screensaverIdleSeconds = 180;
        public boolean pixelShiftEnabled = true;
    }

    public static class LauncherConfig {
        public int version = 1;
        public List<String> apps = new ArrayList<>();
        public List<HdmiConfig> hdmi = new ArrayList<>();
        public List<String> quickSettings = new ArrayList<>(Arrays.asList("wifi", "bluetooth", "sound", "picture", "settings"));
        public String theme = THEME_OLED_BLACK;
        public OledConfig oledProtection = new OledConfig();
    }

    /**
     * Primary external push file: /sdcard/Android/data/org.opentv.launcher/files/config.json
     * (Accessible without runtime permissions on Android 11+ scoped storage)
     */
    public static File getPrimaryConfigFile(Context context) {
        File dir = context.getExternalFilesDir(null);
        if (dir != null) {
            return new File(dir, "config.json");
        }
        return new File("/sdcard/Android/data/" + context.getPackageName() + "/files/config.json");
    }

    /**
     * Secondary external push file: /sdcard/OpenTV/config.json
     */
    public static File getSecondaryConfigFile() {
        return new File(Environment.getExternalStorageDirectory(), "OpenTV/config.json");
    }

    /**
     * External apps.txt file: /sdcard/OpenTV/apps.txt
     */
    public static File getAppsTxtFile() {
        return new File(Environment.getExternalStorageDirectory(), "OpenTV/apps.txt");
    }

    /**
     * Loads unified active configuration following fallback precedence.
     */
    public static LauncherConfig loadConfig(Context context) {
        // 1. Try Primary external file
        File primary = getPrimaryConfigFile(context);
        if (primary != null && primary.exists() && primary.canRead()) {
            LauncherConfig config = parseConfigFile(primary);
            if (config != null) return config;
        }

        // 2. Try Secondary external file
        File secondary = getSecondaryConfigFile();
        if (secondary != null && secondary.exists() && secondary.canRead()) {
            LauncherConfig config = parseConfigFile(secondary);
            if (config != null) return config;
        }

        // 3. Try SharedPreferences
        LauncherConfig prefConfig = loadFromPreferences(context);
        if (prefConfig != null && !prefConfig.apps.isEmpty()) {
            return prefConfig;
        }

        // 4. Try apps.txt file
        File appsTxt = getAppsTxtFile();
        if (appsTxt != null && appsTxt.exists() && appsTxt.canRead()) {
            List<String> apps = parseAppsTxt(appsTxt);
            if (!apps.isEmpty()) {
                if (prefConfig == null) prefConfig = new LauncherConfig();
                prefConfig.apps = apps;
                return prefConfig;
            }
        }

        // 5. Default built-in apps
        if (prefConfig == null) prefConfig = new LauncherConfig();
        if (prefConfig.apps.isEmpty()) {
            prefConfig.apps = new ArrayList<>(DEFAULT_APPS);
        }
        return prefConfig;
    }

    /**
     * Applies configuration from Intent extras if stamp verification passes.
     * Returns true if configuration was updated.
     */
    public static boolean applyFromIntent(Context context, Intent intent) {
        if (intent == null) return false;
        String apps = intent.getStringExtra("apps");
        String quick = intent.getStringExtra("quick");
        String theme = intent.getStringExtra("theme");
        String stamp = intent.getStringExtra("stamp");

        if (apps == null && quick == null && theme == null) return false;

        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        if (stamp != null && stamp.equals(prefs.getString(KEY_STAMP, null))) {
            return false; // Stale replay ignored
        }

        SharedPreferences.Editor editor = prefs.edit();
        if (stamp != null) editor.putString(KEY_STAMP, stamp);

        if (apps != null) {
            apps = apps.trim();
            if (apps.isEmpty() || apps.equalsIgnoreCase("auto")) {
                editor.remove(KEY_APPS);
            } else {
                editor.putString(KEY_APPS, apps);
            }
        }

        if (quick != null) {
            quick = quick.trim();
            if (quick.isEmpty() || quick.equalsIgnoreCase("none")) {
                editor.remove(KEY_QUICK);
            } else {
                editor.putString(KEY_QUICK, quick);
            }
        }

        if (theme != null && !theme.trim().isEmpty()) {
            editor.putString(KEY_THEME, theme.trim());
        }

        editor.apply();
        return true;
    }

    private static LauncherConfig parseConfigFile(File file) {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line).append('\n');
            return parseConfigJson(sb.toString());
        } catch (Exception e) {
            return null;
        }
    }

    public static List<String> parseAppsTxt(File file) {
        List<String> list = new ArrayList<>();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(file), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                list.add(line);
            }
        } catch (Exception ignored) {}
        return list;
    }

    public static LauncherConfig parseConfigJson(String jsonString) {
        try {
            JSONObject obj = new JSONObject(jsonString);
            LauncherConfig config = new LauncherConfig();
            config.version = obj.optInt("version", 1);

            JSONArray appsArr = obj.optJSONArray("apps");
            if (appsArr != null) {
                config.apps.clear();
                for (int i = 0; i < appsArr.length(); i++) {
                    config.apps.add(appsArr.getString(i));
                }
            }

            JSONArray hdmiArr = obj.optJSONArray("hdmi");
            if (hdmiArr != null) {
                config.hdmi.clear();
                for (int i = 0; i < hdmiArr.length(); i++) {
                    JSONObject h = hdmiArr.getJSONObject(i);
                    config.hdmi.add(new HdmiConfig(h.getString("id"), h.getString("title"), h.optBoolean("visible", true)));
                }
            }

            JSONArray quickArr = obj.optJSONArray("quick_settings");
            if (quickArr != null) {
                config.quickSettings.clear();
                for (int i = 0; i < quickArr.length(); i++) {
                    config.quickSettings.add(quickArr.getString(i));
                }
            }

            config.theme = obj.optString("theme", THEME_OLED_BLACK);

            JSONObject oled = obj.optJSONObject("oled_protection");
            if (oled != null) {
                config.oledProtection.screensaverIdleSeconds = oled.optInt("screensaver_idle_seconds", 180);
                config.oledProtection.pixelShiftEnabled = oled.optBoolean("pixel_shift_enabled", true);
            }

            return config;
        } catch (Throwable t) {
            return parseConfigJsonFallback(jsonString);
        }
    }

    private static LauncherConfig parseConfigJsonFallback(String json) {
        try {
            LauncherConfig config = new LauncherConfig();
            java.util.regex.Pattern vPat = java.util.regex.Pattern.compile("\"version\"\\s*:\\s*(\\d+)");
            java.util.regex.Matcher vm = vPat.matcher(json);
            if (vm.find()) config.version = Integer.parseInt(vm.group(1));

            java.util.regex.Pattern appsPat = java.util.regex.Pattern.compile("\"apps\"\\s*:\\s*\\[([^\\]]*)\\]");
            java.util.regex.Matcher am = appsPat.matcher(json);
            if (am.find()) {
                config.apps.clear();
                java.util.regex.Matcher sm = java.util.regex.Pattern.compile("\"([^\"]+)\"").matcher(am.group(1));
                while (sm.find()) config.apps.add(sm.group(1));
            }

            java.util.regex.Pattern hdmiPat = java.util.regex.Pattern.compile("\"hdmi\"\\s*:\\s*\\[([^\\]]*)\\]");
            java.util.regex.Matcher hm = hdmiPat.matcher(json);
            if (hm.find()) {
                config.hdmi.clear();
                java.util.regex.Pattern objPat = java.util.regex.Pattern.compile("\\{([^\\}]+)\\}");
                java.util.regex.Matcher om = objPat.matcher(hm.group(1));
                while (om.find()) {
                    String block = om.group(1);
                    String id = extractString(block, "id");
                    String title = extractString(block, "title");
                    boolean vis = !block.contains("\"visible\"") || block.contains("\"visible\": true") || block.contains("\"visible\":true");
                    if (id != null) config.hdmi.add(new HdmiConfig(id, title != null ? title : id, vis));
                }
            }

            java.util.regex.Pattern qPat = java.util.regex.Pattern.compile("\"quick_settings\"\\s*:\\s*\\[([^\\]]*)\\]");
            java.util.regex.Matcher qm = qPat.matcher(json);
            if (qm.find()) {
                config.quickSettings.clear();
                java.util.regex.Matcher sm = java.util.regex.Pattern.compile("\"([^\"]+)\"").matcher(qm.group(1));
                while (sm.find()) config.quickSettings.add(sm.group(1));
            }

            String theme = extractString(json, "theme");
            if (theme != null) config.theme = theme;

            java.util.regex.Pattern oledPat = java.util.regex.Pattern.compile("\"oled_protection\"\\s*:\\s*\\{([^\\}]*)\\}");
            java.util.regex.Matcher olm = oledPat.matcher(json);
            if (olm.find()) {
                String oblock = olm.group(1);
                java.util.regex.Matcher idleM = java.util.regex.Pattern.compile("\"screensaver_idle_seconds\"\\s*:\\s*(\\d+)").matcher(oblock);
                if (idleM.find()) config.oledProtection.screensaverIdleSeconds = Integer.parseInt(idleM.group(1));
                if (oblock.contains("\"pixel_shift_enabled\"")) {
                    config.oledProtection.pixelShiftEnabled = oblock.contains("\"pixel_shift_enabled\": true") || oblock.contains("\"pixel_shift_enabled\":true");
                }
            }

            return config;
        } catch (Exception e) {
            return null;
        }
    }

    private static String extractString(String block, String key) {
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\"" + key + "\"\\s*:\\s*\"([^\"]+)\"").matcher(block);
        return m.find() ? m.group(1) : null;
    }

    public static LauncherConfig loadFromPreferences(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        LauncherConfig config = new LauncherConfig();

        String appsStr = prefs.getString(KEY_APPS, null);
        if (appsStr != null && !appsStr.trim().isEmpty()) {
            config.apps = new ArrayList<>(Arrays.asList(appsStr.split("[,\\s]+")));
        }

        String quickStr = prefs.getString(KEY_QUICK, null);
        if (quickStr != null && !quickStr.trim().isEmpty()) {
            config.quickSettings = new ArrayList<>(Arrays.asList(quickStr.split("[,\\s]+")));
        }

        config.theme = prefs.getString(KEY_THEME, THEME_OLED_BLACK);
        config.oledProtection.screensaverIdleSeconds = prefs.getInt(KEY_OLED_TIMEOUT, 180);
        config.oledProtection.pixelShiftEnabled = prefs.getBoolean(KEY_OLED_PIXEL_SHIFT, true);

        return config;
    }

    public static void saveToPreferences(Context context, LauncherConfig config) {
        if (config == null) return;
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();

        if (config.apps != null && !config.apps.isEmpty()) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < config.apps.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(config.apps.get(i));
            }
            editor.putString(KEY_APPS, sb.toString());
        }

        if (config.quickSettings != null && !config.quickSettings.isEmpty()) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < config.quickSettings.size(); i++) {
                if (i > 0) sb.append(',');
                sb.append(config.quickSettings.get(i));
            }
            editor.putString(KEY_QUICK, sb.toString());
        }

        editor.putString(KEY_THEME, config.theme != null ? config.theme : THEME_OLED_BLACK);
        if (config.oledProtection != null) {
            editor.putInt(KEY_OLED_TIMEOUT, config.oledProtection.screensaverIdleSeconds);
            editor.putBoolean(KEY_OLED_PIXEL_SHIFT, config.oledProtection.pixelShiftEnabled);
        }

        editor.apply();
    }
}
