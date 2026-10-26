package org.opentv.launcher;

import android.app.Activity;
import android.app.Dialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.Typeface;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.LayerDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.Uri;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.BaseAdapter;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextClock;
import android.widget.TextView;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.TreeMap;

/**
 * OpenTV Core Home Activity.
 * Displays a clean 6-column TV grid, D-pad navigation, Leanback banners,
 * HDMI passthrough tiles, clock indicator, and quick settings shortcuts.
 */
public class MainActivity extends Activity implements FocusController.FocusCallback, FocusController.Listener {

    public static final int PER_ROW = 6;
    public static final int MARGIN = 96, GAP = 36, RADIUS = 22;
    public static final int ROW1_TOP = 604, ROW_STEP = 224, GRID_MIN_TOP = 400;
    public static final int ICON_TOP = 76, ICON_BUTTON = 72, ICON_SIZE = 40, ICON_GAP = 12;

    public static final String PLAY_STORE = "com.android.vending";
    public static final String ADD = "opentv.action.ADD";
    public static final String SETTINGS_ACTION = "opentv.action.SETTINGS";
    public static final String NETWORK = "opentv.action.NETWORK";
    public static final String QUICK_PREFIX = "opentv.quick.";

    private static final String[] EDIT_ITEMS_USER = {"Move", "Replace", "Remove from home", "Uninstall"};
    private static final String[] EDIT_ITEMS_SYSTEM = {"Move", "Replace", "Remove from home", "App info"};

    private static final int OFFLINE = 0;
    private static final int ETHERNET = 4;

    private float scale = 1.0f;
    private FrameLayout root;
    private ScrollView scroller;
    private TextView moveHint;
    private FocusController focusController;
    private OledProtectionService oledProtection;
    private ConfigManager.LauncherConfig config;
    private List<String> initialAppsBeforeMove;

    private final List<String> rowApps = new ArrayList<>();
    private final List<View> appCards = new ArrayList<>();
    private final List<View> allTiles = new ArrayList<>();

    private int tileW, tileH, gridTop;
    private ImageView netIcon;
    private int netState = -1;
    private ConnectivityManager.NetworkCallback networkCallback;

    private static Typeface regular;
    private static Typeface semibold;

    interface Pick {
        void at(int which);
    }

    interface IconLoader {
        Drawable at(int which) throws Exception;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        loadFonts();

        scale = getResources().getDisplayMetrics().widthPixels / 1920.0f;
        focusController = new FocusController(this);
        focusController.setColumnsPerRow(PER_ROW);

        oledProtection = new OledProtectionService();

        scroller = new ScrollView(this);
        scroller.setFillViewport(true);
        scroller.setVerticalScrollBarEnabled(false);
        scroller.setOverScrollMode(View.OVER_SCROLL_NEVER);
        scroller.setClipChildren(false);

        root = new FrameLayout(this);
        root.setClipChildren(false);
        scroller.addView(root, new FrameLayout.LayoutParams(-1, -2));

        setupHeaderClock();
        setupMoveHint();

        // Ingest configuration
        ConfigManager.applyFromIntent(this, getIntent());
        config = ConfigManager.loadConfig(this);

        applyTheme();

        ConfigReloadReceiver.setListener(cfg -> runOnUiThread(() -> {
            this.config = cfg;
            applyTheme();
            buildTiles();
        }));

        setContentView(scroller);

        registerNetworkMonitor();
        buildTiles();

        oledProtection.attach(this, root);
        if (config.oledProtection != null) {
            oledProtection.configure(config.oledProtection.screensaverIdleSeconds, config.oledProtection.pixelShiftEnabled);
        }
    }

    private void applyTheme() {
        if (config == null) return;
        boolean isOled = config.theme != null && (config.theme.equalsIgnoreCase(ConfigManager.THEME_OLED_BLACK) || config.theme.toLowerCase().contains("oled"));
        int bgColor = isOled ? OledProtectionService.PURE_BLACK_COLOR : 0xFF120E10;
        root.setBackgroundColor(bgColor);
        scroller.setBackgroundColor(bgColor);
        getWindow().setBackgroundDrawable(new ColorDrawable(bgColor));
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (ConfigManager.applyFromIntent(this, intent)) {
            config = ConfigManager.loadConfig(this);
            applyTheme();
            buildTiles();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshNetwork();
        if (focusController.getFocusedKey() == null && !appCards.isEmpty()) {
            appCards.get(0).requestFocus();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        oledProtection.detach();
        ConfigReloadReceiver.setListener(null);
        unregisterNetworkMonitor();
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        oledProtection.onUserInteraction();
        return super.dispatchKeyEvent(event);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        focusController.onWindowFocusChanged(hasFocus);
    }

    @Override
    public void onBackPressed() {
        // TV launcher home screen: consume back without exiting
    }

    private void setupHeaderClock() {
        LinearLayout clock = new LinearLayout(this);
        clock.setOrientation(LinearLayout.VERTICAL);
        String day = Strings.datePattern();
        TextClock date = createClock(day, day, px(30), 0xA8FFFFFF, regular);
        TextClock time = createClock("h:mm", "H:mm", px(176), Color.WHITE, semibold);
        time.setLetterSpacing(-0.028f);
        time.setFontFeatureSettings("tnum");
        time.setIncludeFontPadding(false);

        clock.addView(date, new LinearLayout.LayoutParams(-2, -2));
        LinearLayout.LayoutParams tp = new LinearLayout.LayoutParams(-2, -2);
        tp.topMargin = px(-20);
        clock.addView(time, tp);
        root.addView(clock, createLayoutParams(px(MARGIN), px(92), -2, -2));
    }

    private void setupMoveHint() {
        moveHint = createTextView(px(24), 0xA8FFFFFF, regular);
        moveHint.setText(Strings.t("Use the arrows to move it, then press OK"));
        moveHint.setVisibility(View.GONE);
        root.addView(moveHint, createLayoutParams(px(MARGIN), px(ROW1_TOP - 64), -2, -2));
    }

    public void buildTiles() {
        String lastFocus = focusController.getFocusedKey();
        int lastIndex = rowApps.indexOf(lastFocus);

        root.setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);

        for (View card : allTiles) {
            View parent = (View) card.getParent();
            if (parent != null && parent.getParent() instanceof ViewGroup) {
                ((ViewGroup) parent.getParent()).removeView(parent);
            }
        }
        allTiles.clear();
        appCards.clear();
        rowApps.clear();
        focusController.clearAllZones();

        int m = px(MARGIN), g = px(GAP);
        tileW = (getResources().getDisplayMetrics().widthPixels - 2 * m - g * (PER_ROW - 1)) / PER_ROW;
        tileH = Math.round(tileW * 9.0f / 16.0f);

        PackageManager pm = getPackageManager();
        List<String> rawApps = (config != null && config.apps != null && !config.apps.isEmpty())
                ? config.apps : ConfigManager.DEFAULT_APPS;

        List<String> launchableApps = new ArrayList<>();
        for (String pkg : rawApps) {
            Intent li = getLaunchIntent(pm, pkg);
            if (li != null) {
                launchableApps.add(pkg);
            }
        }

        int rows = Math.max(1, (launchableApps.size() + PER_ROW - 1) / PER_ROW);
        gridTop = Math.max(px(GRID_MIN_TOP), px(ROW1_TOP) - (rows - 1) * px(ROW_STEP));
        int bottomTop = gridTop + rows * px(ROW_STEP);

        ((FrameLayout.LayoutParams) moveHint.getLayoutParams()).topMargin = gridTop - px(64);
        root.setMinimumHeight(bottomTop + tileH + px(MARGIN));

        // 1. App Tiles
        for (int i = 0; i < launchableApps.size(); i++) {
            String pkg = launchableApps.get(i);
            rowApps.add(pkg);
            Intent li = getLaunchIntent(pm, pkg);
            Drawable banner = null;
            try {
                banner = pm.getActivityBanner(li);
                if (banner == null) banner = pm.getApplicationBanner(pkg);
            } catch (Exception ignored) {}

            String label = pkg;
            try {
                label = pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString();
            } catch (Exception ignored) {}

            Drawable icon = null;
            if (banner == null) {
                try {
                    icon = pm.getApplicationIcon(pkg);
                } catch (Exception ignored) {}
            }

            // Sideloaded app banner generator: synthesize 16:9 banner canvas from app icon
            if (banner == null && icon != null) {
                try {
                    banner = BannerGenerator.getInstance().getOrCreateBannerDrawable(
                            getResources(), pkg, label, icon, tileW, tileH);
                } catch (Exception ignored) {}
            }

            View card = addTile(root, pkg, label, banner, null, icon, gridX(i), gridY(i), tileW, tileH, true);
            appCards.add(card);
        }

        // 2. Footer Row: Play Store, HDMI inputs, Settings, Add App
        int col = 0;
        boolean showStore = !rowApps.contains(PLAY_STORE) && getLaunchIntent(pm, PLAY_STORE) != null;
        List<TvInputHelper.HdmiInput> inputs = TvInputHelper.queryHdmiInputs(this, 4);
        int maxInputs = PER_ROW - 2 - (showStore ? 1 : 0);
        if (inputs.size() > maxInputs) {
            inputs = inputs.subList(0, maxInputs);
        }

        if (showStore) {
            addTile(root, PLAY_STORE, "Play Store", null, LineIcon.PLAY, null,
                    m + col++ * (tileW + g), bottomTop, tileW, tileH, false);
        }

        for (TvInputHelper.HdmiInput in : inputs) {
            addTile(root, in.id, in.label, null, LineIcon.HDMI, null,
                    m + col++ * (tileW + g), bottomTop, tileW, tileH, false);
        }

        addTile(root, SETTINGS_ACTION, Strings.t("Settings"), null, LineIcon.SETTINGS, null,
                m + col++ * (tileW + g), bottomTop, tileW, tileH, false);

        addTile(root, ADD, Strings.t("Add app"), null, LineIcon.PLUS, null,
                m + col * (tileW + g), bottomTop, tileW, tileH, false);

        // 3. Header Zone: Quick Settings shortcuts & Network Tile
        buildHeaderIcons(m);

        root.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        focusController.restoreFocus(lastFocus, lastIndex);
    }

    private void buildHeaderIcons(int margin) {
        List<String> quickShortcuts = (config != null && config.quickSettings != null)
                ? config.quickSettings : new ArrayList<>();

        int ib = px(ICON_BUTTON), ig = px(ICON_GAP);
        int totalHeaderIcons = quickShortcuts.size() + 1; // plus network icon
        int qx = getResources().getDisplayMetrics().widthPixels - margin + (ib - px(ICON_SIZE)) / 2
                - totalHeaderIcons * ib - (totalHeaderIcons - 1) * ig;

        for (String name : quickShortcuts) {
            int[] iconOps = getIconForShortcut(name);
            if (iconOps != null) {
                addHeaderIcon(QUICK_PREFIX + name, Strings.t(capitalize(name)), new LineIcon(iconOps, px(ICON_SIZE)), qx);
                qx += ib + ig;
            }
        }

        netIcon = addHeaderIcon(NETWORK, Strings.t("Network"), null, qx);
        netState = -1;
        refreshNetwork();
    }

    private int[] getIconForShortcut(String name) {
        switch (name.toLowerCase()) {
            case "bluetooth": return LineIcon.BLUETOOTH;
            case "sound": return LineIcon.SOUND;
            case "picture": return LineIcon.PICTURE;
            case "settings": return LineIcon.SETTINGS;
            case "wifi": return LineIcon.WIFI;
            default: return LineIcon.SETTINGS;
        }
    }

    private String capitalize(String s) {
        if (s == null || s.isEmpty()) return "";
        return Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }

    private View addTile(ViewGroup parent, final String key, String label, Drawable banner, int[] lineIcon,
                         Drawable appIcon, int x, int y, int w, int h, boolean isAppTile) {
        FrameLayout card = new FrameLayout(this);
        final GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(px(RADIUS));

        if (banner != null) {
            bg.setColor(0xFF1E1A1C);
            ImageView iv = new ImageView(this);
            iv.setImageDrawable(fit(banner, w, h));
            card.addView(iv, new FrameLayout.LayoutParams(-1, -1));
        } else {
            // Glass fallback card
            bg.setColor(0x13FFFFFF);
            bg.setStroke(Math.max(1, px(2)), 0x17FFFFFF);
            LinearLayout inner = new LinearLayout(this);
            inner.setOrientation(LinearLayout.VERTICAL);
            inner.setGravity(Gravity.CENTER);

            ImageView iv = new ImageView(this);
            int iconSize = lineIcon != null ? px(44) : px(64);
            if (lineIcon != null) {
                iv.setImageDrawable(new LineIcon(lineIcon, iconSize));
            } else if (appIcon != null) {
                iv.setImageDrawable(fit(appIcon, iconSize, iconSize));
            }
            inner.addView(iv, new LinearLayout.LayoutParams(iconSize, iconSize));

            TextView labelView = createTextView(px(24), 0xE0FFFFFF, regular);
            labelView.setText(label);
            labelView.setSingleLine(true);
            labelView.setEllipsize(android.text.TextUtils.TruncateAt.END);
            labelView.setGravity(Gravity.CENTER);
            labelView.setPadding(px(16), 0, px(16), 0);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-2, -2);
            lp.topMargin = px(12);
            inner.addView(labelView, lp);
            card.addView(inner, new FrameLayout.LayoutParams(-1, -1));
        }

        card.setBackground(bg);
        card.setClipToOutline(true);

        TextView caption = null;
        if (banner != null) {
            caption = createTextView(px(24), Color.WHITE, regular);
            caption.setText(label);
            caption.setGravity(Gravity.CENTER_HORIZONTAL);
            caption.setVisibility(View.INVISIBLE);
        }

        if (isAppTile) {
            focusController.registerAppTile(card, key, banner == null, caption);
        } else {
            focusController.registerFooterTile(card, key);
        }

        card.setOnClickListener(v -> onTileClick(key));
        if (isAppTile) {
            card.setOnLongClickListener(v -> {
                onTileLongClick(key);
                return true;
            });
        }

        FrameLayout wrap = new FrameLayout(this);
        wrap.setClipChildren(false);
        wrap.addView(card, new FrameLayout.LayoutParams(w, h));
        if (caption != null) {
            FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(w, -2);
            cp.topMargin = h + px(22);
            wrap.addView(caption, cp);
        }

        parent.addView(wrap, createLayoutParams(x, y, w, -2));
        allTiles.add(card);
        return card;
    }

    private ImageView addHeaderIcon(final String key, String label, Drawable icon, int x) {
        int b = px(ICON_BUTTON), size = px(ICON_SIZE);
        FrameLayout card = new FrameLayout(this);
        final GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.OVAL);
        bg.setColor(Color.TRANSPARENT);
        card.setBackground(bg);

        ImageView iv = new ImageView(this);
        if (icon != null) {
            iv.setImageDrawable(icon);
        }
        card.addView(iv, new FrameLayout.LayoutParams(size, size, Gravity.CENTER));
        card.setContentDescription(label);

        focusController.registerHeaderView(card, key);
        card.setOnClickListener(v -> onTileClick(key));

        FrameLayout wrap = new FrameLayout(this);
        wrap.setClipChildren(false);
        wrap.addView(card, new FrameLayout.LayoutParams(b, b));
        root.addView(wrap, createLayoutParams(x, px(ICON_TOP), b, b));
        allTiles.add(card);
        return iv;
    }

    @Override
    public void onTileClick(String key) {
        if (ADD.equals(key)) {
            showAddMenu(-1);
        } else if (SETTINGS_ACTION.equals(key)) {
            openSettingsMenu();
        } else if (NETWORK.equals(key)) {
            openNetworkSettings();
        } else if (key.startsWith(QUICK_PREFIX)) {
            String shortcut = key.substring(QUICK_PREFIX.length());
            VendorAdapter.dispatchQuickSetting(this, shortcut);
        } else if (isInputKey(key)) {
            TvInputHelper.launchInput(this, key);
        } else {
            launchApp(key);
        }
    }

    @Override
    public void onTileLongClick(String key) {
        showEditMenu(key);
    }

    private boolean isInputKey(String key) {
        return key.contains("/") || key.startsWith("HW") || key.toLowerCase().contains("hdmi");
    }

    private void launchApp(String pkg) {
        Intent li = getLaunchIntent(getPackageManager(), pkg);
        if (li != null) {
            li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            try {
                startActivity(li);
            } catch (Exception ignored) {}
        }
    }

    private void openSettingsMenu() {
        String[] items = {Strings.t("TV settings"), Strings.t("Picture"), Strings.t("Sound")};
        dropdown(findTile(SETTINGS_ACTION), items, which -> {
            if (which == 0) {
                VendorAdapter.dispatchQuickSetting(this, "settings");
            } else if (which == 1) {
                VendorAdapter.dispatchQuickSetting(this, "picture");
            } else {
                VendorAdapter.dispatchQuickSetting(this, "sound");
            }
        });
    }

    private void openNetworkSettings() {
        for (String a : new String[]{Settings.ACTION_WIFI_SETTINGS, Settings.ACTION_WIRELESS_SETTINGS, Settings.ACTION_SETTINGS}) {
            try {
                startActivity(new Intent(a).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                return;
            } catch (Exception ignored) {}
        }
    }

    private void showEditMenu(final String key) {
        final int index = rowApps.indexOf(key);
        if (index < 0) return;
        boolean userApp = isUserInstalled(key);
        String[] items = userApp ? EDIT_ITEMS_USER : EDIT_ITEMS_SYSTEM;

        View card = findTile(key);
        if (card == null) return;

        dropdown(card, items, which -> {
            if (which == 0) {
                // Move Mode
                initialAppsBeforeMove = new ArrayList<>(rowApps);
                moveHint.setVisibility(View.VISIBLE);
                focusController.startMove(key, card);
            } else if (which == 1) {
                // Replace
                showAddMenu(index);
            } else if (which == 2) {
                // Remove from home
                rowApps.remove(index);
                persistApps();
                buildTiles();
            } else if (which == 3) {
                // Uninstall or App info
                Uri packageUri = Uri.parse("package:" + key);
                try {
                    Intent intent = userApp ? new Intent(Intent.ACTION_DELETE, packageUri)
                            : new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, packageUri);
                    startActivity(intent);
                } catch (Exception ignored) {}
            }
        });
    }

    private void showAddMenu(final int replaceIndex) {
        PackageManager pm = getPackageManager();
        TreeMap<String, String> byLabel = new TreeMap<>(String.CASE_INSENSITIVE_ORDER);

        for (String category : new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER}) {
            Intent q = new Intent(Intent.ACTION_MAIN).addCategory(category);
            List<ResolveInfo> list = pm.queryIntentActivities(q, 0);
            for (ResolveInfo ri : list) {
                if (ri.activityInfo == null) continue;
                String pkg = ri.activityInfo.packageName;
                if (rowApps.contains(pkg) || byLabel.containsValue(pkg) || pkg.equals(getPackageName())) {
                    continue;
                }
                String label = labelOf(pkg);
                if (!byLabel.containsKey(label)) {
                    byLabel.put(label, pkg);
                }
            }
        }

        if (byLabel.isEmpty()) {
            panel(Strings.t("Every app is already here"), Collections.singletonList("OK"), which -> {});
            return;
        }

        final List<String> pkgs = new ArrayList<>(byLabel.values());
        String title = replaceIndex < 0 ? Strings.t("Add an app")
                : String.format(Strings.t("Replace %s"), labelOf(rowApps.get(replaceIndex)));

        panel(title, new ArrayList<>(byLabel.keySet()), pos -> fit(pm.getApplicationIcon(pkgs.get(pos)), px(48), px(48)),
                px(48), -1, null, which -> {
                    if (replaceIndex < 0) {
                        rowApps.add(pkgs.get(which));
                    } else {
                        rowApps.set(replaceIndex, pkgs.get(which));
                    }
                    persistApps();
                    buildTiles();
                });
    }

    private void persistApps() {
        if (config == null) config = new ConfigManager.LauncherConfig();
        config.apps = new ArrayList<>(rowApps);
        ConfigManager.saveToPreferences(this, config);
    }

    @Override
    public void onMoveStep(String key, int fromIndex, int toIndex) {
        if (fromIndex < 0 || fromIndex >= rowApps.size() || toIndex < 0 || toIndex >= rowApps.size()) {
            return;
        }
        rowApps.add(toIndex, rowApps.remove(fromIndex));
        View card = appCards.remove(fromIndex);
        appCards.add(toIndex, card);

        int min = Math.min(fromIndex, toIndex);
        int max = Math.max(fromIndex, toIndex);
        for (int i = min; i <= max; i++) {
            View wrap = (View) appCards.get(i).getParent();
            FrameLayout.LayoutParams lp = (FrameLayout.LayoutParams) wrap.getLayoutParams();
            lp.leftMargin = gridX(i);
            lp.topMargin = gridY(i);
            wrap.setLayoutParams(lp);
        }
        card.post(() -> card.requestRectangleOnScreen(new Rect(0, 0, card.getWidth(), card.getHeight())));
    }

    @Override
    public void onMoveCommit(String key) {
        moveHint.setVisibility(View.GONE);
        initialAppsBeforeMove = null;
        persistApps();
    }

    @Override
    public void onMoveCancel(String key) {
        moveHint.setVisibility(View.GONE);
        if (initialAppsBeforeMove != null) {
            rowApps.clear();
            rowApps.addAll(initialAppsBeforeMove);
            if (config != null) {
                config.apps = new ArrayList<>(initialAppsBeforeMove);
            }
            initialAppsBeforeMove = null;
        }
        buildTiles();
    }

    private void dropdown(View anchor, String[] items, final Pick pick) {
        final Dialog d = new Dialog(this, android.R.style.Theme_Material_Dialog_NoActionBar);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = px(10), rowH = px(64);
        box.setPadding(pad, pad, pad, pad);

        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(px(RADIUS));
        bg.setColor(0xFF231D1F);
        bg.setStroke(Math.max(1, px(2)), 0x17FFFFFF);
        box.setBackground(bg);

        float widest = 0;
        for (int i = 0; i < items.length; i++) {
            final int which = i;
            final TextView t = createTextView(px(26), 0xD9FFFFFF, regular);
            t.setText(Strings.t(items[i]));
            t.setSingleLine(true);
            t.setGravity(Gravity.CENTER_VERTICAL);
            t.setPadding(px(22), 0, px(22), 0);
            widest = Math.max(widest, t.getPaint().measureText(t.getText().toString()) + 2 * px(22) + 2 * pad);

            final GradientDrawable focus = new GradientDrawable();
            focus.setCornerRadius(px(RADIUS - pad));
            focus.setColor(Color.TRANSPARENT);
            t.setBackground(focus);
            t.setFocusable(true);
            t.setOnFocusChangeListener((v, has) -> {
                focus.setColor(has ? 0x38FFFFFF : Color.TRANSPARENT);
                t.setTextColor(has ? Color.WHITE : 0xD9FFFFFF);
            });
            t.setOnClickListener(v -> {
                d.dismiss();
                pick.at(which);
            });
            box.addView(t, new LinearLayout.LayoutParams(-1, rowH));
        }
        d.setContentView(box);

        int h = items.length * rowH + 2 * pad;
        int w;
        int x = 0;
        int y = 0;
        int gravity;

        if (anchor != null) {
            int[] at = new int[2];
            anchor.getLocationOnScreen(at);
            int tileBottom = at[1] + Math.round(anchor.getHeight() * anchor.getScaleY());
            w = Math.max(Math.max(Math.round(anchor.getWidth() * anchor.getScaleX()), px(320)), (int) Math.ceil(widest));
            y = tileBottom + px(64);
            if (y + h > getResources().getDisplayMetrics().heightPixels - px(24)) {
                y = at[1] - h - px(16);
            }
            x = at[0];
            gravity = Gravity.TOP | Gravity.START;
        } else {
            // Anchor view is null: fallback to center-screen placement
            w = Math.max(px(320), (int) Math.ceil(widest));
            x = 0;
            y = 0;
            gravity = Gravity.CENTER;
        }

        Window win = d.getWindow();
        if (win != null) {
            win.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            win.clearFlags(android.view.WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            win.setGravity(gravity);
            android.view.WindowManager.LayoutParams lp = win.getAttributes();
            lp.x = x;
            lp.y = y;
            lp.width = w;
            lp.height = h;
            win.setAttributes(lp);
        }
        d.show();
    }

    private void panel(String title, List<String> labels, Pick pick) {
        panel(title, labels, null, 0, -1, null, pick);
    }

    private void panel(String title, final List<String> labels, final IconLoader icon, final int size,
                      final int selected, final Pick preview, final Pick pick) {
        final Dialog d = new Dialog(this, android.R.style.Theme_Material_Dialog_NoActionBar);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(px(48), px(92), px(48), px(48));

        TextView head = createTextView(px(40), Color.WHITE, semibold);
        head.setText(title);
        head.setSingleLine(true);
        head.setEllipsize(android.text.TextUtils.TruncateAt.END);
        head.setPadding(px(24), 0, px(24), 0);
        box.addView(head);

        ListView list = new ListView(this);
        list.setDivider(null);
        list.setVerticalScrollBarEnabled(false);
        list.setOverScrollMode(View.OVER_SCROLL_NEVER);

        GradientDrawable focus = new GradientDrawable();
        focus.setCornerRadius(px(RADIUS));
        focus.setColor(0x38FFFFFF);
        list.setSelector(focus);

        final Drawable[] icons = new Drawable[labels.size()];
        list.setAdapter(new BaseAdapter() {
            @Override public int getCount() { return labels.size(); }
            @Override public Object getItem(int pos) { return labels.get(pos); }
            @Override public long getItemId(int pos) { return pos; }
            @Override public View getView(int pos, View convert, ViewGroup parent) {
                TextView t = convert != null ? (TextView) convert : createTextView(px(30), 0xE6FFFFFF, regular);
                t.setText(labels.get(pos));
                t.setSingleLine(true);
                t.setEllipsize(android.text.TextUtils.TruncateAt.END);
                t.setGravity(Gravity.CENTER_VERTICAL);
                t.setMinHeight(px(88));
                t.setPadding(px(24), 0, px(24), 0);
                if (icon != null && icons[pos] == null) {
                    try {
                        icons[pos] = icon.at(pos);
                    } catch (Exception e) {
                        icons[pos] = new ColorDrawable(Color.TRANSPARENT);
                    }
                    icons[pos].setBounds(0, 0, size, size);
                }
                t.setCompoundDrawablesRelative(icons[pos], null, null, null);
                t.setCompoundDrawablePadding(px(24));
                return t;
            }
        });

        list.setOnItemClickListener((parent, v, pos, id) -> {
            d.dismiss();
            pick.at(pos);
        });

        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, 0, 1f);
        lp.topMargin = px(36);
        box.addView(list, lp);

        d.setContentView(box);
        Window w = d.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new ColorDrawable(0xF7161113));
            w.setLayout(px(640), -1);
            w.setGravity(Gravity.END);
            w.setDimAmount(0.5f);
        }
        d.show();
    }

    private void registerNetworkMonitor() {
        if (Build.VERSION.SDK_INT >= 23) {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) return;
            networkCallback = new ConnectivityManager.NetworkCallback() {
                @Override
                public void onAvailable(Network network) {
                    runOnUiThread(MainActivity.this::refreshNetwork);
                }
                @Override
                public void onLost(Network network) {
                    runOnUiThread(MainActivity.this::refreshNetwork);
                }
                @Override
                public void onCapabilitiesChanged(Network network, NetworkCapabilities networkCapabilities) {
                    runOnUiThread(MainActivity.this::refreshNetwork);
                }
            };
            try {
                cm.registerNetworkCallback(new NetworkRequest.Builder().build(), networkCallback);
            } catch (Exception ignored) {}
        }
    }

    private void unregisterNetworkMonitor() {
        if (networkCallback != null && Build.VERSION.SDK_INT >= 23) {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm != null) {
                try {
                    cm.unregisterNetworkCallback(networkCallback);
                } catch (Exception ignored) {}
            }
        }
    }

    private int networkState() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return OFFLINE;
        try {
            int rssi = Integer.MIN_VALUE;
            if (Build.VERSION.SDK_INT >= 23) {
                NetworkCapabilities c = cm.getNetworkCapabilities(cm.getActiveNetwork());
                if (c == null) return OFFLINE;
                if (!c.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return ETHERNET;
                if (Build.VERSION.SDK_INT >= 29) rssi = c.getSignalStrength();
            } else {
                android.net.NetworkInfo ni = cm.getActiveNetworkInfo();
                if (ni == null || !ni.isConnected()) return OFFLINE;
                if (ni.getType() != ConnectivityManager.TYPE_WIFI) return ETHERNET;
            }
            if (rssi == Integer.MIN_VALUE) {
                WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                if (wm != null && wm.getConnectionInfo() != null) rssi = wm.getConnectionInfo().getRssi();
            }
            return 1 + WifiManager.calculateSignalLevel(rssi, 3);
        } catch (Exception e) {
            return OFFLINE;
        }
    }

    private void refreshNetwork() {
        if (netIcon == null) return;
        int state = networkState();
        if (state == netState) return;
        netState = state;
        if (state == ETHERNET) {
            netIcon.setImageDrawable(new LineIcon(LineIcon.ETHERNET, px(ICON_SIZE)));
        } else {
            LineIcon fan = new LineIcon(LineIcon.WIFI, px(ICON_SIZE));
            fan.setAlpha(0x47);
            int[] top = state == OFFLINE ? LineIcon.SLASH : state == 1 ? LineIcon.WIFI_1
                    : state == 2 ? LineIcon.WIFI_2 : LineIcon.WIFI;
            netIcon.setImageDrawable(new LayerDrawable(new Drawable[]{fan, new LineIcon(top, px(ICON_SIZE))}));
        }
        View parent = (View) netIcon.getParent();
        if (parent != null) {
            parent.setContentDescription(state == OFFLINE ? Strings.t("Offline") : state == ETHERNET ? "Ethernet" : "Wi-Fi");
        }
    }

    private Drawable fit(Drawable d, int w, int h) {
        try {
            Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
            int iw = d.getIntrinsicWidth(), ih = d.getIntrinsicHeight();
            if (iw <= 0 || ih <= 0) {
                iw = w;
                ih = h;
            }
            float s = Math.max((float) w / iw, (float) h / ih);
            int dw = Math.round(iw * s), dh = Math.round(ih * s);
            d.setBounds((w - dw) / 2, (h - dh) / 2, (w - dw) / 2 + dw, (h - dh) / 2 + dh);
            d.draw(new Canvas(b));
            return new BitmapDrawable(getResources(), b);
        } catch (Throwable t) {
            return d;
        }
    }

    private View findTile(String key) {
        for (View t : allTiles) {
            if (key != null && key.equals(t.getTag())) return t;
        }
        return null;
    }

    private boolean isUserInstalled(String pkg) {
        try {
            return (getPackageManager().getApplicationInfo(pkg, 0).flags & ApplicationInfo.FLAG_SYSTEM) == 0;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private String labelOf(String pkg) {
        PackageManager pm = getPackageManager();
        try {
            return pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString();
        } catch (Exception e) {
            return pkg;
        }
    }

    private static Intent getLaunchIntent(PackageManager pm, String pkg) {
        Intent i = pm.getLeanbackLaunchIntentForPackage(pkg);
        return i != null ? i : pm.getLaunchIntentForPackage(pkg);
    }

    private static void loadFonts() {
        if (regular != null) return;
        regular = fromFile("/system/fonts/MILanPro_Normal.ttf", Typeface.create("sans-serif", Typeface.NORMAL));
        semibold = fromFile("/system/fonts/MILanPro_SemiBold.ttf", Typeface.create("sans-serif-medium", Typeface.NORMAL));
    }

    private static Typeface fromFile(String path, Typeface fallback) {
        try {
            return new File(path).exists() ? Typeface.createFromFile(path) : fallback;
        } catch (Exception e) {
            return fallback;
        }
    }

    @Override
    public int px(int dp) {
        return Math.round(dp * scale);
    }

    private int gridX(int i) {
        return px(MARGIN) + (i % PER_ROW) * (tileW + px(GAP));
    }

    private int gridY(int i) {
        return gridTop + (i / PER_ROW) * px(ROW_STEP);
    }

    private TextClock createClock(String f12, String f24, int px, int color, Typeface tf) {
        TextClock c = new TextClock(this);
        c.setFormat12Hour(f12);
        c.setFormat24Hour(f24);
        c.setTextSize(TypedValue.COMPLEX_UNIT_PX, px);
        c.setTextColor(color);
        c.setTypeface(tf);
        return c;
    }

    private TextView createTextView(int px, int color, Typeface tf) {
        TextView t = new TextView(this);
        t.setTextSize(TypedValue.COMPLEX_UNIT_PX, px);
        t.setTextColor(color);
        if (tf != null) t.setTypeface(tf);
        return t;
    }

    private static FrameLayout.LayoutParams createLayoutParams(int x, int y, int w, int h) {
        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(w, h);
        lp.leftMargin = x;
        lp.topMargin = y;
        return lp;
    }
}
