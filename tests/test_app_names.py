"""
tests/test_app_names.py
Milestone 4: Friendly Package Name Resolution & Metadata Engine Test Suite.
Verifies:
- Exact catalog lookup across 350 curated packages in 8 categories.
- Fallback heuristic tokenization (camelCase, snake_case, kebab-case, acronyms, prefixes, compounds).
- Acronym and official brand casing preservation.
- Category inference across 9 priority tiers.
- Display formatting ([Friendly Name] (pkg.id) - [Category/Safety]).
- CLI integration (list-apps --raw, enriched JSON, debloat summaries).
- TUI integration (grid preview labels, device package metadata).
- Performance throughput (>10,000 lookups/sec).
"""
import io
import json
import sys
import time
import unittest
from pathlib import Path
from typing import Dict, List, Tuple
from unittest.mock import MagicMock

# Ensure companion is on sys.path for direct module test execution
REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANION_DIR = REPO_ROOT / "companion"
if COMPANION_DIR.exists() and str(COMPANION_DIR) not in sys.path:
    sys.path.insert(0, str(COMPANION_DIR))

from opentv import cli
from opentv.core.app_names import (
    ALL_CATEGORIES,
    APP_CATALOG,
    CATALOG,
    CATEGORY_APPLICATIONS,
    CATEGORY_AUDIO,
    CATEGORY_BROWSER,
    CATEGORY_GAMES,
    CATEGORY_GAMING,
    CATEGORY_LAUNCHER,
    CATEGORY_LIVE_TV,
    CATEGORY_MEDIA,
    CATEGORY_OEM,
    CATEGORY_STREAMING,
    CATEGORY_STREAMING_VIDEO,
    CATEGORY_SYSTEM,
    CATEGORY_SYSTEM_OEM,
    CATEGORY_TOOLS,
    CATEGORY_TOOLS_UTILITIES,
    AppInfo,
    AppMetadata,
    fallback_app_info,
    format_app_display,
    get_app_category,
    get_app_metadata,
    get_app_name,
    get_catalog_stats,
    infer_category,
    infer_fallback_category,
    is_known_app,
    list_catalog_apps,
    normalize_package_name,
    resolve_app,
    resolve_fallback_name,
    tokenize_package_name,
)
from opentv.core.device import DeviceManager
from opentv.tui.app import OpenTVApp


# ==============================================================================
# Suite 1: Curated Catalog Lookups & Architecture
# ==============================================================================

class TestCatalogLookup(unittest.TestCase):
    """Verifies curated catalog size, categorization, schema, and O(1) lookups."""

    def test_catalog_size_and_type(self):
        """Curated catalog must contain at least 350 verified packages."""
        self.assertGreaterEqual(len(CATALOG), 350)
        self.assertIs(CATALOG, APP_CATALOG)
        for pkg, val in CATALOG.items():
            self.assertIsInstance(pkg, str)
            self.assertTrue(len(pkg) > 0)
            self.assertIsInstance(val, tuple)
            self.assertGreaterEqual(len(val), 2)
            name, cat = val[0], val[1]
            self.assertIsInstance(name, str)
            self.assertIsInstance(cat, str)
            self.assertTrue(len(name) > 0)
            self.assertTrue(len(cat) > 0)

    def test_streaming_services_catalog(self):
        """Major streaming platforms resolve accurately with Category Streaming."""
        streaming_checks = [
            ("com.netflix.ninja", "Netflix"),
            ("com.google.android.youtube.tv", "YouTube"),
            ("com.google.android.youtube.tvkids", "YouTube Kids"),
            ("com.amazon.amazonvideo.livingroom", "Prime Video"),
            ("com.disney.disneyplus", "Disney+"),
            ("com.wbd.stream", "Max"),
            ("com.hulu.livingroomplus", "Hulu"),
            ("com.apple.atve.androidtv.appletv", "Apple TV"),
            ("com.peacocktv.peacockandroid", "Peacock"),
            ("com.cbs.ott", "Paramount+"),
            ("com.tubitv", "Tubi"),
            ("tv.pluto.android", "Pluto TV"),
            ("com.crunchyroll.crunchyroid", "Crunchyroll"),
        ]
        for pkg, expected_name in streaming_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_STREAMING)
            self.assertTrue(meta.is_known)
            self.assertEqual(meta.package_name, pkg)

    def test_media_players_catalog(self):
        """Media players and centers resolve accurately with Category Media Players."""
        media_checks = [
            ("org.xbmc.kodi", "Kodi"),
            ("org.videolan.vlc", "VLC"),
            ("org.videolan.vlc.betav7", "VLC Beta"),
            ("com.plexapp.android", "Plex"),
            ("org.jellyfin.androidtv", "Jellyfin"),
            ("com.teamsmart.videoplayer.tv", "SmartTube"),
            ("com.brouken.player", "Just Player"),
            ("com.mxtech.videoplayer.ad", "MX Player"),
            ("com.tvepi.player", "TiviMate IPTV Player"),
            ("com.stremio.one", "Stremio"),
        ]
        for pkg, expected_name in media_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_MEDIA)
            self.assertTrue(meta.is_known)

    def test_music_audio_catalog(self):
        """Music and audio services resolve with Category Music & Audio."""
        audio_checks = [
            ("com.spotify.tv.android", "Spotify TV"),
            ("com.spotify.music", "Spotify"),
            ("com.aspiro.tidal", "TIDAL"),
            ("deezer.android.tv", "Deezer TV"),
            ("tunein.player", "TuneIn Radio"),
            ("com.amazon.mp3", "Amazon Music"),
            ("com.google.android.apps.youtube.music", "YouTube Music"),
            ("com.apple.android.music", "Apple Music"),
            ("com.soundcloud.android", "SoundCloud"),
        ]
        for pkg, expected_name in audio_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_AUDIO)
            self.assertTrue(meta.is_known)

    def test_live_tv_sports_catalog(self):
        """Live TV and sports broadcast apps resolve with Category Live TV & Sports."""
        live_checks = [
            ("com.google.android.youtube.tvunplugged", "YouTube TV"),
            ("com.sling", "Sling TV"),
            ("tv.fubo.mobile", "Fubo TV"),
            ("com.espn.score_center", "ESPN"),
            ("uk.co.bbc.iplayer", "BBC iPlayer"),
            ("in.startv.hotstar", "Disney+ Hotstar"),
            ("com.jio.media.ondemand", "JioCinema"),
            ("de.zdf.android.mediathek", "ZDFmediathek"),
            ("fr.francetv.pluzz", "france.tv"),
        ]
        for pkg, expected_name in live_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_LIVE_TV)
            self.assertTrue(meta.is_known)

    def test_tools_utilities_catalog(self):
        """File managers, tools, and browsers resolve with Category Utilities & Tools."""
        tools_checks = [
            ("com.esotericsoftware.clouddrive", "Downloader by AFTVnews"),
            ("com.mobisystems.fileman", "File Commander"),
            ("com.lonelycatgames.Xplore", "X-plore File Manager"),
            ("com.google.android.apps.nbu.files", "Files by Google"),
            ("com.speedtest.android.tv", "Speedtest by Ookla"),
            ("com.browser.tv", "TV Bro Browser"),
            ("org.mozilla.tv.firefox", "Firefox for Android TV"),
            ("org.opentv.launcher", "OpenTV Launcher"),
            ("com.wireguard.android", "WireGuard"),
            ("com.topjohnwu.magisk", "Magisk"),
        ]
        for pkg, expected_name in tools_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_TOOLS)
            self.assertTrue(meta.is_known)

    def test_gaming_emulation_catalog(self):
        """Games and emulators resolve with Category Games & Emulators."""
        game_checks = [
            ("com.retroarch", "RetroArch"),
            ("com.retroarch.aarch64", "RetroArch Plus"),
            ("org.ppsspp.ppsspp", "PPSSPP"),
            ("com.limelight", "Moonlight Game Streaming"),
            ("com.valvesoftware.steamlink", "Steam Link"),
            ("com.nvidia.geforcenow", "NVIDIA GeForce NOW"),
            ("com.xbox.gamepass", "Xbox Game Pass"),
            ("com.mojang.minecraftpe", "Minecraft"),
            ("it.dbassacc.lemuroid", "Lemuroid"),
        ]
        for pkg, expected_name in game_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_GAMES)
            self.assertTrue(meta.is_known)

    def test_oem_vendor_packages_catalog(self):
        """OEM specific packages resolve with Category OEM Components and brand."""
        oem_checks = [
            ("com.sony.dtv.tvx", "Sony Live TV / HDMI", "sony"),
            ("com.sony.dtv.braviasync", "Sony BRAVIA Sync", "sony"),
            ("com.tcl.settings", "TCL Settings", "tcl"),
            ("com.tcl.waterfall.overseas", "TCL Waterfall Feed", "tcl"),
            ("org.droidtv.homeintentresolver", "Philips Home Router", "philips"),
            ("com.jamdeo.tv.input", "Hisense TV Input", "hisense"),
            ("com.xiaomi.mitv.settings", "Mi TV Settings", "xiaomi"),
            ("com.nvidia.shield.agent", "Nvidia Shield Core Agent", "nvidia"),
            ("tv.samba.ssm", "Samba TV ACR", None),
        ]
        for pkg, expected_name, expected_brand in oem_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_OEM)
            self.assertTrue(meta.is_known)
            if expected_brand is not None:
                self.assertEqual(meta.brand, expected_brand)

    def test_android_core_system_catalog(self):
        """Core Android system and Google TV components resolve with Category System & Core."""
        system_checks = [
            ("android", "Android System"),
            ("com.android.settings", "Settings"),
            ("com.android.vending", "Google Play Store"),
            ("com.google.android.gms", "Google Play Services"),
            ("com.google.android.apps.mediashell", "Chromecast Built-in"),
            ("com.google.android.apps.tv.launcherx", "Google TV Home"),
            ("com.google.android.tvlauncher", "Android TV Home"),
            ("com.google.android.inputmethod.latin", "Gboard TV Keyboard"),
        ]
        for pkg, expected_name in system_checks:
            meta = get_app_metadata(pkg)
            self.assertEqual(meta.name, expected_name)
            self.assertEqual(meta.category, CATEGORY_SYSTEM)
            self.assertTrue(meta.is_known)

    def test_catalog_case_insensitivity(self):
        """Package lookup is case-insensitive and whitespace resilient."""
        self.assertEqual(get_app_name("COM.NETFLIX.NINJA"), "Netflix")
        self.assertEqual(get_app_name("  com.netflix.ninja  "), "Netflix")
        self.assertEqual(get_app_name("Com.Google.Android.YouTube.TV"), "YouTube")

    def test_catalog_stats_and_listing(self):
        """get_catalog_stats and list_catalog_apps produce valid summaries."""
        stats = get_catalog_stats()
        self.assertGreaterEqual(stats["total_curated_apps"], 350)
        self.assertEqual(sum(stats["categories"].values()), stats["total_curated_apps"])

        streaming_apps = list_catalog_apps(category=CATEGORY_STREAMING)
        self.assertGreaterEqual(len(streaming_apps), 40)
        for app in streaming_apps:
            self.assertEqual(app.category, CATEGORY_STREAMING)

    def test_is_known_app_helper(self):
        """is_known_app accurately determines whether a package is curated."""
        self.assertTrue(is_known_app("com.netflix.ninja"))
        self.assertTrue(is_known_app("org.videolan.vlc"))
        self.assertFalse(is_known_app("com.unknown.randomapp123"))
        self.assertFalse(is_known_app(""))

    def test_app_metadata_namedtuple_and_alias(self):
        """AppMetadata supports tuple unpacking, dict serialization, and AppInfo alias."""
        meta = AppMetadata(
            name="Test App",
            category="Streaming",
            is_known=True,
            package_name="com.test.app",
            brand="test",
        )
        name, cat = meta[:2]
        self.assertEqual(name, "Test App")
        self.assertEqual(cat, "Streaming")
        d = meta.to_dict()
        self.assertEqual(d["name"], "Test App")
        self.assertEqual(d["package_name"], "com.test.app")
        # AppInfo alias
        self.assertIs(AppInfo, AppMetadata)


# ==============================================================================
# Suite 2: Tokenized Fallback Heuristic
# ==============================================================================

class TestFallbackHeuristic(unittest.TestCase):
    """Verifies tokenizer, regex extraction, compound decomposition, acronyms, and categories."""

    def test_camelcase_tokenization(self):
        """camelCase and PascalCase identifiers split cleanly into capitalized words."""
        self.assertEqual(resolve_fallback_name("com.vendor.mySuperPlayer"), "My Super Player")
        self.assertEqual(resolve_fallback_name("com.dev.SmartTubeNext"), "Smart Tube Next")

    def test_snake_case_tokenization(self):
        """snake_case identifiers split cleanly."""
        self.assertEqual(resolve_fallback_name("org.tools.speed_test_pro"), "Speed Test Pro")
        self.assertEqual(resolve_fallback_name("com.app.live_stream_viewer"), "Live Stream Viewer")

    def test_kebab_case_tokenization(self):
        """kebab-case identifiers split cleanly."""
        self.assertEqual(resolve_fallback_name("net.cloud.retro-gaming-hub"), "Retro Gaming Hub")

    def test_reverse_domain_prefix_stripping(self):
        """Leading TLDs and ecosystem domain prefixes are stripped."""
        self.assertEqual(resolve_fallback_name("com.google.android.apps.tv.sampleapp"), "Sampleapp")
        self.assertEqual(resolve_fallback_name("io.github.muntashirakon.AppManager"), "Muntashirakon App Manager")
        self.assertEqual(resolve_fallback_name("uk.co.bbc.news"), "Bbc News")

    def test_acronym_preservation(self):
        """Technical, video, and audio acronyms remain uppercase."""
        self.assertEqual(resolve_fallback_name("com.example.iptv.hd"), "Example IPTV HD")
        self.assertEqual(resolve_fallback_name("com.test.dvr.sdk"), "Test DVR SDK")
        self.assertEqual(resolve_fallback_name("com.radio.fm.am"), "Radio FM AM")
        self.assertEqual(resolve_fallback_name("com.video.av.4k"), "Video AV 4K")
        self.assertEqual(resolve_fallback_name("net.network.vpn.dns"), "Network VPN DNS")

    def test_brand_casing_preservation(self):
        """Official brand names receive correct mixed casing."""
        self.assertEqual(resolve_fallback_name("com.custom.smarttube"), "Smart Tube")
        self.assertEqual(resolve_fallback_name("com.dev.airplay"), "AirPlay")
        self.assertEqual(resolve_fallback_name("com.app.wifi"), "WiFi")

    def test_compound_word_splitting(self):
        """Solid lowercase compound words split across known prefix and suffix dictionaries."""
        self.assertEqual(resolve_fallback_name("com.app.videoplayer"), "Video Player")
        self.assertEqual(resolve_fallback_name("com.app.filemanager"), "File Manager")
        self.assertEqual(resolve_fallback_name("com.app.smarttube"), "Smart Tube")
        self.assertEqual(resolve_fallback_name("com.app.systemui"), "System UI")

    def test_trailing_filler_pruning_and_tv_preservation(self):
        """Trailing boilerplate filler words are pruned, but TV and ATV are preserved."""
        # Filler pruned
        tokens_twitch = tokenize_package_name("tv.twitch.android.app")
        self.assertEqual(tokens_twitch, ["Twitch"])

        # TV preserved
        tokens_spotify = tokenize_package_name("com.spotify.tv.android")
        self.assertEqual(tokens_spotify, ["Spotify", "TV"])

    def test_duplicate_token_deduplication(self):
        """Repetitive subdomain and package name tokens are deduplicated."""
        tokens_stan = tokenize_package_name("au.com.stan.stan")
        self.assertEqual(tokens_stan, ["Stan"])

        tokens_amazon = tokenize_package_name("com.amazon.amazonvideo.livingroom")
        self.assertEqual(tokens_amazon, ["Amazon", "Video", "Living", "Room"])

    def test_category_inference_launcher(self):
        """Packages with launcher keywords infer TV Launcher category."""
        self.assertEqual(infer_category(["projcon", "launcher"]), CATEGORY_LAUNCHER)
        self.assertEqual(infer_fallback_category("com.my.leanbacklauncher"), CATEGORY_LAUNCHER)

    def test_category_inference_browser(self):
        """Packages with browser keywords infer Web Browser category."""
        self.assertEqual(infer_fallback_category("org.mozilla.firefox"), CATEGORY_BROWSER)
        self.assertEqual(infer_fallback_category("com.chrome.canary"), CATEGORY_BROWSER)

    def test_category_inference_gaming(self):
        """Packages with gaming/emulator keywords infer Games & Emulation category."""
        self.assertEqual(infer_fallback_category("com.retroarch"), CATEGORY_GAMING)
        self.assertEqual(infer_fallback_category("org.my.emulator"), CATEGORY_GAMING)

    def test_category_inference_audio(self):
        """Packages with music/radio keywords infer Music & Audio category."""
        self.assertEqual(infer_fallback_category("com.radio.fm"), CATEGORY_AUDIO)
        self.assertEqual(infer_fallback_category("com.audio.podcast"), CATEGORY_AUDIO)

    def test_category_inference_live_tv(self):
        """Packages with IPTV/tuner/sports keywords infer Live TV & Sports category."""
        self.assertEqual(infer_fallback_category("com.my.iptv"), CATEGORY_LIVE_TV)
        self.assertEqual(infer_fallback_category("com.network.sports"), CATEGORY_LIVE_TV)

    def test_category_inference_streaming(self):
        """Packages with video/player/stream keywords infer Streaming & Video category."""
        self.assertEqual(infer_fallback_category("com.custom.streamer"), CATEGORY_STREAMING_VIDEO)
        self.assertEqual(infer_fallback_category("org.video.player"), CATEGORY_STREAMING_VIDEO)

    def test_category_inference_tools(self):
        """Packages with tool/speed/file keywords infer Tools & Utilities category."""
        self.assertEqual(infer_fallback_category("com.speedtest.android"), CATEGORY_TOOLS_UTILITIES)
        self.assertEqual(infer_fallback_category("com.file.explorer"), CATEGORY_TOOLS_UTILITIES)

    def test_category_inference_system(self):
        """Packages with system/settings keywords infer System & OEM category."""
        self.assertEqual(infer_fallback_category("com.android.settings"), CATEGORY_SYSTEM_OEM)
        self.assertEqual(infer_fallback_category("com.device.bluetooth"), CATEGORY_SYSTEM_OEM)

    def test_category_inference_default(self):
        """Unrecognized packages fall back to Applications category."""
        self.assertEqual(infer_fallback_category("com.unknown.randomwordxyz"), CATEGORY_APPLICATIONS)

    def test_bounded_edge_cases(self):
        """Empty, None, and whitespace strings handle safely without throwing exceptions."""
        info_empty = fallback_app_info("")
        self.assertEqual(info_empty.name, "Unknown")
        self.assertEqual(info_empty.category, CATEGORY_APPLICATIONS)
        self.assertFalse(info_empty.is_known)

        info_none = fallback_app_info(None)  # type: ignore
        self.assertEqual(info_none.name, "Unknown")

        info_ws = fallback_app_info("   ")
        self.assertEqual(info_ws.name, "Unknown")

        info_single = fallback_app_info("a")
        self.assertEqual(info_single.name, "A")

        info_num = fallback_app_info("123")
        self.assertEqual(info_num.name, "123")

    def test_extreme_length_and_unicode_safety(self):
        """Large inputs (500+ chars) and Unicode identifiers process safely."""
        long_pkg = "com." + "test" * 150
        info_long = fallback_app_info(long_pkg)
        self.assertTrue(len(info_long.name) > 0)
        self.assertLessEqual(len(info_long.name), 600)

        unicode_pkg = "com.école.cinéma"
        info_uni = fallback_app_info(unicode_pkg)
        self.assertTrue(len(info_uni.name) > 0)


# ==============================================================================
# Suite 3: Display Formatting
# ==============================================================================

class TestFormatAppDisplay(unittest.TestCase):
    """Verifies format_app_display output patterns, safety labels, and length limits."""

    def test_format_app_display_catalog_item(self):
        """Catalog item formats as [Friendly Name] (pkg.id) - [Category]."""
        formatted = format_app_display("com.netflix.ninja")
        self.assertEqual(formatted, "[Netflix] (com.netflix.ninja) - [Streaming]")

    def test_format_app_display_fallback_item(self):
        """Unlisted fallback package formats accurately."""
        formatted = format_app_display("com.randomdev.myvideoplayer")
        self.assertIn("[Randomdev My Video Player]", formatted)
        self.assertIn("com.randomdev.myvideoplayer", formatted)
        self.assertIn("[Streaming & Video]", formatted)

    def test_format_app_display_without_category(self):
        """Omission of category suffix when include_category is False."""
        formatted = format_app_display("com.netflix.ninja", include_category=False)
        self.assertEqual(formatted, "[Netflix] (com.netflix.ninja)")

    def test_format_app_display_with_safety_label(self):
        """Safety label appends accurately alongside category."""
        formatted = format_app_display("com.sony.dtv.braviasync", safety_label="SAFE")
        self.assertEqual(formatted, "[Sony BRAVIA Sync] (com.sony.dtv.braviasync) - [OEM Components / SAFE]")

    def test_format_app_display_safety_label_only(self):
        """Safety label replaces category when include_category is False."""
        formatted = format_app_display("com.sony.dtv.braviasync", include_category=False, safety_label="SAFE")
        self.assertEqual(formatted, "[Sony BRAVIA Sync] (com.sony.dtv.braviasync) - [SAFE]")

    def test_format_app_display_without_brackets(self):
        """Unbracketed name formatting."""
        formatted = format_app_display("org.xbmc.kodi", bracket_name=False)
        self.assertEqual(formatted, "Kodi (org.xbmc.kodi) - [Media Players]")

    def test_format_app_display_max_width_truncation(self):
        """Truncation with ellipsis when line exceeds max_width."""
        formatted = format_app_display("com.google.android.youtube.tv", max_width=25)
        self.assertLessEqual(len(formatted), 25)
        self.assertTrue(formatted.endswith("..."))

    def test_format_app_display_custom_template(self):
        """Custom format template substitution."""
        template = "{name} :: {package} :: {category}"
        formatted = format_app_display("com.netflix.ninja", template=template)
        self.assertEqual(formatted, "Netflix :: com.netflix.ninja :: Streaming")


# ==============================================================================
# Suite 4: CLI and TUI Integration
# ==============================================================================

class TestCLIAndTUIIntegration(unittest.TestCase):
    """Verifies list-apps --raw flag, enriched JSON, debloat formatting, and TUI grid labels."""

    def test_cli_list_apps_default_friendly_format(self):
        """opentv list-apps defaults to friendly display formatting."""
        stdout = io.StringIO()
        runner = MagicMock(return_value=(0, "com.netflix.ninja\ncom.google.android.youtube.tv\n", ""))
        code = cli.main(["-t", "dev1", "list-apps"], runner=runner, stdout=stdout)
        self.assertEqual(code, cli.EXIT_SUCCESS)
        out = stdout.getvalue()
        self.assertIn("[Netflix] (com.netflix.ninja) - [Streaming]", out)
        self.assertIn("[YouTube] (com.google.android.youtube.tv) - [Streaming]", out)

    def test_cli_list_apps_raw_flag(self):
        """opentv list-apps --raw outputs raw package IDs only."""
        stdout = io.StringIO()
        runner = MagicMock(return_value=(0, "com.netflix.ninja\ncom.google.android.youtube.tv\n", ""))
        code = cli.main(["-t", "dev1", "list-apps", "--raw"], runner=runner, stdout=stdout)
        self.assertEqual(code, cli.EXIT_SUCCESS)
        out = stdout.getvalue()
        self.assertEqual(sorted(out.strip().splitlines()), sorted(["com.netflix.ninja", "com.google.android.youtube.tv"]))

    def test_cli_list_apps_json_enrichment(self):
        """opentv list-apps --json --categories enriches entries with friendly name and functional genre."""
        stdout = io.StringIO()
        runner = MagicMock(return_value=(0, "com.netflix.ninja\n", ""))
        code = cli.main(["-t", "dev1", "list-apps", "--json", "--categories"], runner=runner, stdout=stdout)
        self.assertEqual(code, cli.EXIT_SUCCESS)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item["package"], "com.netflix.ninja")
        self.assertEqual(item["name"], "Netflix")
        self.assertEqual(item["genre"], "Streaming")
        self.assertTrue(item["is_known"])

    def test_cli_debloat_dry_run_friendly_formatting(self):
        """opentv debloat --dry-run presents friendly app name and category tag."""
        stdout = io.StringIO()
        runner = MagicMock(return_value=(0, "package:tv.samba.ssm\n", ""))
        code = cli.main(["-t", "dev1", "debloat", "--safe-only", "--dry-run"], runner=runner, stdout=stdout)
        self.assertEqual(code, cli.EXIT_SUCCESS)
        out = stdout.getvalue()
        self.assertIn("Samba TV ACR", out)
        self.assertIn("tv.samba.ssm", out)
        self.assertIn("SAFE", out)

    def test_tui_grid_preview_renders_friendly_names(self):
        """generate_grid_preview formats cells with friendly names rather than package segments."""
        app = OpenTVApp(force_fallback=True)
        apps = ["com.netflix.ninja", "com.google.android.youtube.tv", "org.xbmc.kodi"]
        grid = app.generate_grid_preview(apps, columns=3)
        self.assertIn("1. Netflix", grid)
        self.assertIn("2. YouTube", grid)
        self.assertIn("3. Kodi", grid)

    def test_device_manager_package_info_uses_friendly_name(self):
        """DeviceManager.get_all_packages_info populates app_label with get_app_name."""
        runner = MagicMock(return_value=(0, "package:com.netflix.ninja\npackage:com.custom.speed_test_pro\n", ""))
        dm = DeviceManager(runner=runner)
        info_list = dm.get_all_packages_info("dev1")
        pkg_map = {p.package_name: p for p in info_list}
        self.assertEqual(pkg_map["com.netflix.ninja"].app_label, "Netflix")
        self.assertEqual(pkg_map["com.custom.speed_test_pro"].app_label, "Speed Test Pro")


# ==============================================================================
# Suite 5: Performance Benchmark (>10,000 lookups/sec)
# ==============================================================================

class TestPerformanceBenchmark(unittest.TestCase):
    """Verifies that lookup and fallback execution speed exceeds 10,000 lookups per second."""

    def test_throughput_exceeds_10000_per_second(self):
        """Resolving 15,000 package lookups must execute in under 1.5 seconds (>10,000 ops/sec)."""
        benchmark_packages = [
            "com.netflix.ninja",
            "com.google.android.youtube.tv",
            "com.amazon.amazonvideo.livingroom",
            "org.videolan.vlc",
            "org.xbmc.kodi",
            "com.spotify.tv.android",
            "com.custom.myvideoplayer",
            "com.tools.speed_test_pro",
            "net.cloud.retro-gaming-hub",
            "com.example.iptv.hd",
        ]
        iterations = 1500  # 1500 * 10 = 15,000 lookups

        start_time = time.perf_counter()
        for _ in range(iterations):
            for pkg in benchmark_packages:
                meta = get_app_metadata(pkg)
                _ = meta.name
                _ = meta.category
        elapsed = time.perf_counter() - start_time

        lookups = iterations * len(benchmark_packages)
        ops_per_sec = lookups / elapsed
        print(f"\n[Benchmark] Completed {lookups:,} lookups in {elapsed:.4f}s ({ops_per_sec:,.0f} ops/sec)")
        self.assertGreater(
            ops_per_sec,
            10000,
            f"Expected >10,000 lookups/sec, achieved {ops_per_sec:,.0f} ops/sec",
        )


if __name__ == "__main__":
    unittest.main()
