package org.opentv.launcher;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * BroadcastReceiver triggered by `adb shell am broadcast -a org.opentv.launcher.RELOAD_CONFIG`.
 * Reloads configuration and notifies the active launcher activity without process restart.
 */
public class ConfigReloadReceiver extends BroadcastReceiver {

    private static ConfigManager.OnConfigReloadListener listener;

    public static void setListener(ConfigManager.OnConfigReloadListener l) {
        listener = l;
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) return;
        if (ConfigManager.ACTION_RELOAD_CONFIG.equals(intent.getAction())) {
            ConfigManager.LauncherConfig config = ConfigManager.loadConfig(context);
            if (listener != null) {
                listener.onConfigReloaded(config);
            }
        }
    }
}
