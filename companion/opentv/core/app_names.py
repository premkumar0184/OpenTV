"""
OpenTV Friendly App Name & Category Metadata Engine.
PROJECT.md Milestone 4 / Requirement R4:
Pure-stdlib O(1) dictionary catalog for top ~350 Android TV apps,
with tokenized fallback heuristic for uncataloged packages.
100% standard library (zero external pip dependencies).
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Set, Tuple, Union

# -----------------------------------------------------------------------------
# Functional Category Taxonomy Constants
# -----------------------------------------------------------------------------
CATEGORY_STREAMING = "Streaming"
CATEGORY_MEDIA = "Media Players"
CATEGORY_AUDIO = "Music & Audio"
CATEGORY_LIVE_TV = "Live TV & Sports"
CATEGORY_TOOLS = "Utilities & Tools"
CATEGORY_GAMES = "Games & Emulators"
CATEGORY_OEM = "OEM Components"
CATEGORY_SYSTEM = "System & Core"
CATEGORY_APPLICATIONS = "Applications"

# Category aliases for compatibility across explorer reports and caller contracts
CATEGORY_LAUNCHER = "TV Launcher"
CATEGORY_BROWSER = "Web Browser"
CATEGORY_GAMING = "Games & Emulation"
CATEGORY_STREAMING_VIDEO = "Streaming & Video"
CATEGORY_TOOLS_UTILITIES = "Tools & Utilities"
CATEGORY_SYSTEM_OEM = "System & OEM"

ALL_CATEGORIES: Tuple[str, ...] = (
    CATEGORY_STREAMING,
    CATEGORY_MEDIA,
    CATEGORY_AUDIO,
    CATEGORY_LIVE_TV,
    CATEGORY_TOOLS,
    CATEGORY_GAMES,
    CATEGORY_OEM,
    CATEGORY_SYSTEM,
    CATEGORY_APPLICATIONS,
)


class AppMetadata(NamedTuple):
    """
    Immutable metadata representation for an Android TV application.

    Attributes:
        name: Human-friendly application name (e.g. 'Netflix', 'YouTube', 'Kodi').
        category: Functional category classification (e.g. 'Streaming', 'Media Players').
        is_known: True if resolved via curated catalog; False if inferred via heuristic.
        package_name: Normalized Android package identifier.
        brand: Optional manufacturer / brand association (e.g. 'sony', 'tcl', 'google').
    """
    name: str
    category: str
    is_known: bool = True
    package_name: str = ""
    brand: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "is_known": self.is_known,
            "package_name": self.package_name,
            "brand": self.brand,
        }


# Type alias for caller compatibility
AppInfo = AppMetadata


# -----------------------------------------------------------------------------
# Curated Catalog (~350 Top Android TV Applications)
# -----------------------------------------------------------------------------
CATALOG: Dict[str, Tuple[str, str]] = {
    # 1. Major Streaming Services (50 Packages)
    "com.netflix.ninja": ("Netflix", CATEGORY_STREAMING),
    "com.google.android.youtube.tv": ("YouTube", CATEGORY_STREAMING),
    "com.google.android.youtube.tvkids": ("YouTube Kids", CATEGORY_STREAMING),
    "com.amazon.amazonvideo.livingroom": ("Prime Video", CATEGORY_STREAMING),
    "com.amazon.avod.thirdpartyclient": ("Prime Video", CATEGORY_STREAMING),
    "com.disney.disneyplus": ("Disney+", CATEGORY_STREAMING),
    "com.wbd.stream": ("Max", CATEGORY_STREAMING),
    "com.hbo.hbonow": ("HBO Max", CATEGORY_STREAMING),
    "com.hulu.livingroomplus": ("Hulu", CATEGORY_STREAMING),
    "com.apple.atve.androidtv.appletv": ("Apple TV", CATEGORY_STREAMING),
    "com.peacocktv.peacockandroid": ("Peacock", CATEGORY_STREAMING),
    "com.cbs.ott": ("Paramount+", CATEGORY_STREAMING),
    "com.paramountplus.intl": ("Paramount+ International", CATEGORY_STREAMING),
    "com.tubitv": ("Tubi", CATEGORY_STREAMING),
    "tv.pluto.android": ("Pluto TV", CATEGORY_STREAMING),
    "com.crunchyroll.crunchyroid": ("Crunchyroll", CATEGORY_STREAMING),
    "com.crunchyroll.vrv.android": ("VRV", CATEGORY_STREAMING),
    "com.funimation.funimationtv": ("Funimation", CATEGORY_STREAMING),
    "com.discovery.discoveryplus.androidtv": ("Discovery+", CATEGORY_STREAMING),
    "com.amcplus.amcfull": ("AMC+", CATEGORY_STREAMING),
    "com.starz.starzplay.androidtv": ("Starz", CATEGORY_STREAMING),
    "com.mubi": ("MUBI", CATEGORY_STREAMING),
    "com.criterionchannel": ("The Criterion Channel", CATEGORY_STREAMING),
    "com.curiosity.curiositystream.tv": ("CuriosityStream", CATEGORY_STREAMING),
    "com.fawesome": ("Fawesome TV", CATEGORY_STREAMING),
    "com.freevee": ("Amazon Freevee", CATEGORY_STREAMING),
    "com.vudu.air.tv": ("Fandango at Home", CATEGORY_STREAMING),
    "com.shudder.androidtv": ("Shudder", CATEGORY_STREAMING),
    "com.britbox.atv": ("BritBox", CATEGORY_STREAMING),
    "tv.rakuten.atv": ("Rakuten TV", CATEGORY_STREAMING),
    "com.viaplay.android": ("Viaplay", CATEGORY_STREAMING),
    "com.kanopy": ("Kanopy", CATEGORY_STREAMING),
    "com.hoopladigital.android": ("Hoopla Digital", CATEGORY_STREAMING),
    "tv.twitch.android.app": ("Twitch", CATEGORY_STREAMING),
    "com.rumble.battles": ("Rumble", CATEGORY_STREAMING),
    "tv.dailymotion.app": ("Dailymotion", CATEGORY_STREAMING),
    "com.ted.android.tv": ("TED TV", CATEGORY_STREAMING),
    "com.vimeo.android.videoapp": ("Vimeo", CATEGORY_STREAMING),
    "org.pbs.video": ("PBS Video", CATEGORY_STREAMING),
    "org.pbskids.video": ("PBS KIDS Video", CATEGORY_STREAMING),
    "com.showtime.standalone": ("Showtime", CATEGORY_STREAMING),
    "com.epix.epix": ("MGM+", CATEGORY_STREAMING),
    "com.acorn.tv": ("Acorn TV", CATEGORY_STREAMING),
    "com.nebula.nebula_tv": ("Nebula", CATEGORY_STREAMING),
    "tv.floatplane.mobile": ("Floatplane", CATEGORY_STREAMING),
    "com.viki.android": ("Rakuten Viki", CATEGORY_STREAMING),
    "com.iqiyi.i18n.tv": ("iQIYI TV", CATEGORY_STREAMING),
    "com.wetv.tv": ("WeTV", CATEGORY_STREAMING),
    "com.viu.tv": ("Viu TV", CATEGORY_STREAMING),
    "com.bilibili.tv": ("Bilibili TV", CATEGORY_STREAMING),

    # 2. Media Players & Centers (33 Packages)
    "org.xbmc.kodi": ("Kodi", CATEGORY_MEDIA),
    "org.videolan.vlc": ("VLC", CATEGORY_MEDIA),
    "org.videolan.vlc.betav7": ("VLC Beta", CATEGORY_MEDIA),
    "com.plexapp.android": ("Plex", CATEGORY_MEDIA),
    "com.plexapp.mediaserver.smb": ("Plex Media Server", CATEGORY_MEDIA),
    "org.jellyfin.androidtv": ("Jellyfin", CATEGORY_MEDIA),
    "tv.emby.embyatv": ("Emby for Android TV", CATEGORY_MEDIA),
    "com.emby.embymobile": ("Emby", CATEGORY_MEDIA),
    "com.teamsmart.videoplayer.tv": ("SmartTube", CATEGORY_MEDIA),
    "com.liskovsoft.smarttubetv.beta": ("SmartTube Beta", CATEGORY_MEDIA),
    "com.liskovsoft.videomanager": ("SmartTube Video Manager", CATEGORY_MEDIA),
    "com.archos.mediacenter.videofree": ("Nova Video Player", CATEGORY_MEDIA),
    "org.courville.nova": ("Nova Video Player", CATEGORY_MEDIA),
    "org.courville.nova.legacy": ("Nova Video Player Legacy", CATEGORY_MEDIA),
    "com.brouken.player": ("Just Player", CATEGORY_MEDIA),
    "com.mxtech.videoplayer.ad": ("MX Player", CATEGORY_MEDIA),
    "com.mxtech.videoplayer.pro": ("MX Player Pro", CATEGORY_MEDIA),
    "com.instantbits.cast.webvideo": ("Web Video Caster", CATEGORY_MEDIA),
    "com.bubblesoft.android.bubbleupnp": ("BubbleUPnP", CATEGORY_MEDIA),
    "com.stremio.one": ("Stremio", CATEGORY_MEDIA),
    "com.tvepi.player": ("TiviMate IPTV Player", CATEGORY_MEDIA),
    "ar.tvplayer.tv": ("IPTV Smarters Pro", CATEGORY_MEDIA),
    "ru.iptvremote.android.iptv": ("IPTV", CATEGORY_MEDIA),
    "ru.iptvremote.android.iptv.pro": ("IPTV Pro", CATEGORY_MEDIA),
    "com.clapp": ("OTT Navigator IPTV", CATEGORY_MEDIA),
    "com.progdvb.progtv.android": ("ProgTV", CATEGORY_MEDIA),
    "com.mvas.stb.emu.free": ("STBEmu", CATEGORY_MEDIA),
    "com.mvas.stb.emu.pro": ("STBEmu Pro", CATEGORY_MEDIA),
    "com.extreamsd.usbaudioplayerpro": ("USB Audio Player PRO", CATEGORY_MEDIA),
    "com.kmplayer": ("KMPlayer", CATEGORY_MEDIA),
    "com.bsplayer.bspandroid.free": ("BSPlayer", CATEGORY_MEDIA),
    "de.cyberdream.androidtv.dreamepg.tv": ("dream Player", CATEGORY_MEDIA),
    "de.cyberdream.dreamepg.iptv.tv": ("dream Player IPTV", CATEGORY_MEDIA),

    # 3. Music & Audio (25 Packages)
    "com.spotify.tv.android": ("Spotify TV", CATEGORY_AUDIO),
    "com.spotify.music": ("Spotify", CATEGORY_AUDIO),
    "com.aspiro.tidal": ("TIDAL", CATEGORY_AUDIO),
    "deezer.android.tv": ("Deezer TV", CATEGORY_AUDIO),
    "deezer.android.app": ("Deezer", CATEGORY_AUDIO),
    "com.pandora.android.atv": ("Pandora TV", CATEGORY_AUDIO),
    "com.pandora.android": ("Pandora", CATEGORY_AUDIO),
    "tunein.player": ("TuneIn Radio", CATEGORY_AUDIO),
    "tunein.player.tv": ("TuneIn Radio TV", CATEGORY_AUDIO),
    "com.clearchannel.iheartradio.tv": ("iHeartRadio TV", CATEGORY_AUDIO),
    "com.clearchannel.iheartradio.controller": ("iHeartRadio", CATEGORY_AUDIO),
    "com.amazon.mp3": ("Amazon Music", CATEGORY_AUDIO),
    "com.google.android.apps.youtube.music": ("YouTube Music", CATEGORY_AUDIO),
    "com.google.android.youtube.tvmusic": ("YouTube Music TV", CATEGORY_AUDIO),
    "com.soundcloud.android": ("SoundCloud", CATEGORY_AUDIO),
    "com.apple.android.music": ("Apple Music", CATEGORY_AUDIO),
    "com.qobuz.music": ("Qobuz", CATEGORY_AUDIO),
    "com.audiomack": ("Audiomack", CATEGORY_AUDIO),
    "radiotime.player": ("RadioTime", CATEGORY_AUDIO),
    "com.siriusxm.car": ("SiriusXM", CATEGORY_AUDIO),
    "com.audible.application": ("Audible", CATEGORY_AUDIO),
    "org.stitcher.app": ("Stitcher", CATEGORY_AUDIO),
    "fm.player": ("Player FM", CATEGORY_AUDIO),
    "com.bambuna.podcastaddict": ("Podcast Addict", CATEGORY_AUDIO),
    "com.shazam.android": ("Shazam", CATEGORY_AUDIO),

    # 4. Live TV, Sports & Regional Broadcasters (64 Packages)
    "com.google.android.youtube.tvunplugged": ("YouTube TV", CATEGORY_LIVE_TV),
    "com.sling": ("Sling TV", CATEGORY_LIVE_TV),
    "tv.fubo.mobile": ("Fubo TV", CATEGORY_LIVE_TV),
    "com.philo.philo.google": ("Philo", CATEGORY_LIVE_TV),
    "com.att.tv": ("DirecTV Stream", CATEGORY_LIVE_TV),
    "com.dish.dishanywhere": ("DISH Anywhere", CATEGORY_LIVE_TV),
    "com.xfinity.cloudtvr": ("Xfinity Stream", CATEGORY_LIVE_TV),
    "com.espn.score_center": ("ESPN", CATEGORY_LIVE_TV),
    "com.bleacherreport.android.teamstream": ("B/R Sports", CATEGORY_LIVE_TV),
    "com.nbcuni.nbc": ("NBC", CATEGORY_LIVE_TV),
    "com.nbcuni.nbcsports.prod": ("NBC Sports", CATEGORY_LIVE_TV),
    "com.foxsports.android": ("FOX Sports", CATEGORY_LIVE_TV),
    "com.cbs.app": ("CBS", CATEGORY_LIVE_TV),
    "com.mlb.atbat": ("MLB", CATEGORY_LIVE_TV),
    "com.nba.ibasket": ("NBA", CATEGORY_LIVE_TV),
    "com.nhl.gc1112.free": ("NHL", CATEGORY_LIVE_TV),
    "com.nfl.mobile": ("NFL", CATEGORY_LIVE_TV),
    "com.dazn": ("DAZN", CATEGORY_LIVE_TV),
    "com.redbull.tv.android": ("Red Bull TV", CATEGORY_LIVE_TV),
    "com.wwe.universe": ("WWE Network", CATEGORY_LIVE_TV),
    "com.haystack.android": ("Haystack News", CATEGORY_LIVE_TV),
    "uk.co.bbc.iplayer": ("BBC iPlayer", CATEGORY_LIVE_TV),
    "uk.co.bbc.sounds": ("BBC Sounds", CATEGORY_LIVE_TV),
    "air.itv.mobile.itvplayer": ("ITVX", CATEGORY_LIVE_TV),
    "com.channel4.ondemand": ("Channel 4", CATEGORY_LIVE_TV),
    "com.five.my5": ("My5", CATEGORY_LIVE_TV),
    "com.nowtv.nowtvplayer": ("NOW TV", CATEGORY_LIVE_TV),
    "in.startv.hotstar": ("Disney+ Hotstar", CATEGORY_LIVE_TV),
    "com.jio.media.ondemand": ("JioCinema", CATEGORY_LIVE_TV),
    "com.jio.jioplay.tv": ("JioTV", CATEGORY_LIVE_TV),
    "com.sonyliv": ("SonyLIV", CATEGORY_LIVE_TV),
    "com.zee5.tv": ("ZEE5", CATEGORY_LIVE_TV),
    "com.altbalaji": ("ALTT", CATEGORY_LIVE_TV),
    "com.sunnxt": ("Sun NXT", CATEGORY_LIVE_TV),
    "ca.cbc.gem": ("CBC Gem", CATEGORY_LIVE_TV),
    "au.gov.abc.iview": ("ABC iview", CATEGORY_LIVE_TV),
    "com.sbs.ondemand": ("SBS On Demand", CATEGORY_LIVE_TV),
    "com.nine.nineplus": ("9Now", CATEGORY_LIVE_TV),
    "tv.ten.tenplay": ("10 play", CATEGORY_LIVE_TV),
    "tv.seven.sevenplus": ("7plus", CATEGORY_LIVE_TV),
    "de.zdf.android.mediathek": ("ZDFmediathek", CATEGORY_LIVE_TV),
    "de.daserste.ardmediathek": ("ARD Mediathek", CATEGORY_LIVE_TV),
    "fr.francetv.pluzz": ("france.tv", CATEGORY_LIVE_TV),
    "com.molotov.app": ("Molotov TV", CATEGORY_LIVE_TV),
    "com.rtve.alacarta": ("RTVE Play", CATEGORY_LIVE_TV),
    "es.atresmedia.atresplayer": ("atresplayer", CATEGORY_LIVE_TV),
    "com.telecinco.mitele": ("Mitele", CATEGORY_LIVE_TV),
    "it.rai.play": ("RaiPlay", CATEGORY_LIVE_TV),
    "com.mediaset.infinity": ("Mediaset Infinity", CATEGORY_LIVE_TV),
    "nl.uitzendinggemist": ("NPO Start", CATEGORY_LIVE_TV),
    "com.rtl.videoland.v2": ("Videoland", CATEGORY_LIVE_TV),
    "com.globo.globotv": ("Globoplay", CATEGORY_LIVE_TV),
    "com.televisa.blim": ("ViX", CATEGORY_LIVE_TV),
    "com.clarovideo.tv": ("Claro Video", CATEGORY_LIVE_TV),
    "jp.tver": ("TVer", CATEGORY_LIVE_TV),
    "jp.co.abema": ("ABEMA", CATEGORY_LIVE_TV),
    "jp.co.u_next.square": ("U-NEXT", CATEGORY_LIVE_TV),
    "kr.co.tving.tv": ("TVING", CATEGORY_LIVE_TV),
    "com.frograms.wplay": ("WATCHA", CATEGORY_LIVE_TV),
    "com.cwtv.android.cw": ("The CW", CATEGORY_LIVE_TV),
    "com.turner.tnt.android.network": ("TNT", CATEGORY_LIVE_TV),
    "com.turner.tbs.android.network": ("TBS", CATEGORY_LIVE_TV),
    "com.usanetwork.usa": ("USA Network", CATEGORY_LIVE_TV),
    "com.amc.androidtv": ("AMC", CATEGORY_LIVE_TV),

    # 5. Utilities, File Management & Web Browsers (40 Packages)
    "com.esotericsoftware.clouddrive": ("Downloader by AFTVnews", CATEGORY_TOOLS),
    "com.mobisystems.fileman": ("File Commander", CATEGORY_TOOLS),
    "com.lonelycatgames.xplore": ("X-plore File Manager", CATEGORY_TOOLS),
    "com.google.android.apps.nbu.files": ("Files by Google", CATEGORY_TOOLS),
    "com.amaze.filemanager": ("Amaze File Manager", CATEGORY_TOOLS),
    "com.yablio.sendfilestotv": ("Send Files to TV", CATEGORY_TOOLS),
    "com.speedsoftware.rootexplorer": ("Root Explorer", CATEGORY_TOOLS),
    "com.speedtest.android.tv": ("Speedtest by Ookla", CATEGORY_TOOLS),
    "org.zwanoo.android.speedtest": ("Speedtest", CATEGORY_TOOLS),
    "com.analiti.fast.android": ("analiti WiFi & Speed Test", CATEGORY_TOOLS),
    "net.fast.speedtest": ("Fast.com Speed Test", CATEGORY_TOOLS),
    "com.browser.tv": ("TV Bro Browser", CATEGORY_TOOLS),
    "com.jio.web.browser": ("JioPages TV Browser", CATEGORY_TOOLS),
    "com.seraphic.openinet.preinstall": ("Open-Internet Browser", CATEGORY_TOOLS),
    "com.opera.browser": ("Opera Browser", CATEGORY_TOOLS),
    "org.mozilla.firefox": ("Firefox", CATEGORY_TOOLS),
    "org.mozilla.tv.firefox": ("Firefox for Android TV", CATEGORY_TOOLS),
    "com.amazon.cloud9": ("Amazon Silk Browser", CATEGORY_TOOLS),
    "com.brave.browser": ("Brave Browser", CATEGORY_TOOLS),
    "com.aloha.browser": ("Aloha Browser", CATEGORY_TOOLS),
    "com.duckduckgo.mobile.android": ("DuckDuckGo Browser", CATEGORY_TOOLS),
    "com.droidlogic.filebrowser": ("Amlogic File Browser", CATEGORY_TOOLS),
    "com.mixplorer": ("MiXplorer", CATEGORY_TOOLS),
    "com.ghisler.android.totalcommander": ("Total Commander", CATEGORY_TOOLS),
    "com.cxinventor.file.explorer": ("Cx File Explorer", CATEGORY_TOOLS),
    "flar2.homebutton": ("Button Mapper", CATEGORY_TOOLS),
    "com.sumotv.remotebutton": ("TV Quick Actions", CATEGORY_TOOLS),
    "com.spocky.projcon": ("Projectivy Launcher", CATEGORY_TOOLS),
    "com.tsynik.pralauncher": ("FLauncher", CATEGORY_TOOLS),
    "org.opentv.launcher": ("OpenTV Launcher", CATEGORY_TOOLS),
    "com.cgutman.androidremotedbg": ("Remote ADB Shell", CATEGORY_TOOLS),
    "com.termux": ("Termux", CATEGORY_TOOLS),
    "com.wireguard.android": ("WireGuard", CATEGORY_TOOLS),
    "net.openvpn.openvpn": ("OpenVPN Connect", CATEGORY_TOOLS),
    "com.nordvpn.android": ("NordVPN", CATEGORY_TOOLS),
    "com.expressvpn.vpn": ("ExpressVPN", CATEGORY_TOOLS),
    "com.surfshark.vpnclient.android": ("Surfshark VPN", CATEGORY_TOOLS),
    "com.protonvpn.android": ("Proton VPN", CATEGORY_TOOLS),
    "com.topjohnwu.magisk": ("Magisk", CATEGORY_TOOLS),
    "me.kavish.atvtools": ("ATV Tools", CATEGORY_TOOLS),

    # 6. Games & Emulators (37 Packages)
    "com.retroarch": ("RetroArch", CATEGORY_GAMES),
    "com.retroarch.aarch64": ("RetroArch Plus", CATEGORY_GAMES),
    "org.ppsspp.ppsspp": ("PPSSPP", CATEGORY_GAMES),
    "org.ppsspp.ppssppgold": ("PPSSPP Gold", CATEGORY_GAMES),
    "com.limelight": ("Moonlight Game Streaming", CATEGORY_GAMES),
    "com.valvesoftware.steamlink": ("Steam Link", CATEGORY_GAMES),
    "com.nvidia.geforcenow": ("NVIDIA GeForce NOW", CATEGORY_GAMES),
    "com.xbox.gamepass": ("Xbox Game Pass", CATEGORY_GAMES),
    "com.playstation.remoteplay": ("PS Remote Play", CATEGORY_GAMES),
    "com.explusalpha.snes9xplus": ("Snes9x EX+", CATEGORY_GAMES),
    "com.explusalpha.mdex": ("MD.emu", CATEGORY_GAMES),
    "com.explusalpha.nesex": ("NES.emu", CATEGORY_GAMES),
    "com.explusalpha.gbcex": ("GBC.emu", CATEGORY_GAMES),
    "com.fastemulator.gba": ("My Boy! GBA Emulator", CATEGORY_GAMES),
    "com.dsemu.drastic": ("DraStic DS Emulator", CATEGORY_GAMES),
    "org.mupen64plusae.v3.fzurita": ("Mupen64Plus FZ", CATEGORY_GAMES),
    "org.citra.citra_emu": ("Citra", CATEGORY_GAMES),
    "org.yuzu.yuzu_emu": ("Yuzu", CATEGORY_GAMES),
    "org.dolphinemu.dolphinemu": ("Dolphin Emulator", CATEGORY_GAMES),
    "com.antstream.arcade": ("Antstream Arcade", CATEGORY_GAMES),
    "com.blacknut.tv": ("Blacknut Cloud Gaming", CATEGORY_GAMES),
    "com.gameloft.android.anmp.glofta8hm": ("Asphalt 8: Airborne", CATEGORY_GAMES),
    "com.gameloft.android.anmp.glofta9hm": ("Asphalt 9: Legends", CATEGORY_GAMES),
    "com.vectorunit.cobalt.googleplay": ("Beach Buggy Racing", CATEGORY_GAMES),
    "com.vectorunit.red.googleplay": ("Riptide GP: Renegade", CATEGORY_GAMES),
    "com.playdead.limbo.full": ("LIMBO", CATEGORY_GAMES),
    "com.mojang.minecraftpe": ("Minecraft", CATEGORY_GAMES),
    "com.chucklefish.stardewvalley": ("Stardew Valley", CATEGORY_GAMES),
    "com.crossyroad.androidtv": ("Crossy Road", CATEGORY_GAMES),
    "com.frogmind.badland": ("BADLAND", CATEGORY_GAMES),
    "com.badflyinteractive.deadeffect2": ("Dead Effect 2", CATEGORY_GAMES),
    "com.madfingergames.deadtrigger2": ("Dead Trigger 2", CATEGORY_GAMES),
    "com.nvidia.tegrazone3": ("TegraZone", CATEGORY_GAMES),
    "com.retro.retrox": ("RetroX", CATEGORY_GAMES),
    "it.dbassacc.lemuroid": ("Lemuroid", CATEGORY_GAMES),
    "com.supercell.clashofclans": ("Clash of Clans", CATEGORY_GAMES),
    "com.playstack.bombclub": ("Bomb Club", CATEGORY_GAMES),

    # 7. OEM Components & Vendor Software (55 Packages)
    "com.sony.dtv.tvx": ("Sony Live TV / HDMI", CATEGORY_OEM),
    "com.sony.dtv.tvinput": ("Sony TV Input", CATEGORY_OEM),
    "com.sony.dtv.braviasync": ("Sony BRAVIA Sync", CATEGORY_OEM),
    "com.sony.dtv.settings": ("Sony Bravia Settings", CATEGORY_OEM),
    "com.sony.dtv.systemui": ("Sony System UI", CATEGORY_OEM),
    "com.sony.dtv.remotepairing": ("Sony Remote Pairing", CATEGORY_OEM),
    "com.sony.dtv.rcpowerkey": ("Sony Power Key Handler", CATEGORY_OEM),
    "com.sony.dtv.uinputservice": ("Sony UInput Service", CATEGORY_OEM),
    "com.sony.sonysystemservice": ("Sony System Service", CATEGORY_OEM),
    "com.sony.dtv.airplayapp": ("Sony AirPlay Receiver", CATEGORY_OEM),
    "tv.samba.ssm": ("Samba TV ACR", CATEGORY_OEM),
    "com.vewd.core.service": ("Vewd Core", CATEGORY_OEM),
    "com.tcl.settings": ("TCL Settings", CATEGORY_OEM),
    "com.tcl.suspension": ("TCL Source Picker", CATEGORY_OEM),
    "com.tcl.tvinput": ("TCL TV Input", CATEGORY_OEM),
    "com.tcl.providers.config": ("TCL Config Provider", CATEGORY_OEM),
    "com.tcl.tv": ("TCL Live TV", CATEGORY_OEM),
    "com.tcl.micmanager": ("TCL Mic Manager", CATEGORY_OEM),
    "com.tcl.waterfall.overseas": ("TCL Waterfall Feed", CATEGORY_OEM),
    "com.tcl.audioplayer": ("TCL Audio Player", CATEGORY_OEM),
    "com.tcl.videoplayer": ("TCL Video Player", CATEGORY_OEM),
    "com.tcl.dashboard": ("TCL Dashboard Feed", CATEGORY_OEM),
    "com.tcl.tcl_bt_rcu_service": ("TCL Bluetooth RCU", CATEGORY_OEM),
    "com.tcl.useragreement": ("TCL User Agreement", CATEGORY_OEM),
    "com.tcl.messagebox": ("TCL Message Box", CATEGORY_OEM),
    "com.tcl.smartalexa": ("TCL Alexa Integration", CATEGORY_OEM),
    "org.droidtv.homeintentresolver": ("Philips Home Router", CATEGORY_OEM),
    "org.droidtv.globalkey": ("Philips Global Key", CATEGORY_OEM),
    "org.droidtv.playtv": ("Philips PlayTV", CATEGORY_OEM),
    "org.droidtv.hdmiservice": ("Philips HDMI Service", CATEGORY_OEM),
    "org.droidtv.channels": ("Philips Channel Database", CATEGORY_OEM),
    "org.droidtv.tvsystemui": ("Philips TV System UI", CATEGORY_OEM),
    "org.droidtv.settings": ("Philips TV Settings", CATEGORY_OEM),
    "org.droidtv.nettv": ("Philips NetTV Portal", CATEGORY_OEM),
    "org.droidtv.tvpowermanagerservice": ("Philips Power Manager Service", CATEGORY_OEM),
    "org.droidtv.lkb": ("Philips Local Keyboard", CATEGORY_OEM),
    "org.droidtv.aurora": ("Philips Aurora Framework", CATEGORY_OEM),
    "com.jamdeo.tv.common": ("Hisense HAL Service", CATEGORY_OEM),
    "com.jamdeo.tv.input": ("Hisense TV Input", CATEGORY_OEM),
    "com.hisense.tv.settings": ("Hisense TV Settings", CATEGORY_OEM),
    "com.hisense.service.remote": ("Hisense Remote Service", CATEGORY_OEM),
    "net.vidaatv.hisense.android.tv": ("Hisense FAST Channels", CATEGORY_OEM),
    "com.hisense.storemode": ("Hisense Store Mode", CATEGORY_OEM),
    "com.xiaomi.mitv.settings": ("Mi TV Settings", CATEGORY_OEM),
    "com.mitv.inputservice": ("Mi TV Input Service", CATEGORY_OEM),
    "com.mitv.remoteservice": ("Mi Remote Service", CATEGORY_OEM),
    "com.mitv.tvhome": ("Xiaomi PatchWall Home", CATEGORY_OEM),
    "com.mitv.tvhome.atv": ("Xiaomi PatchWall ATV Bridge", CATEGORY_OEM),
    "com.mitv.tvhome.mitvplus": ("Mi TV+ Channels", CATEGORY_OEM),
    "com.xiaomi.mitv.mediaexplorer": ("Mi Media Explorer", CATEGORY_OEM),
    "com.nvidia.shield.agent": ("Nvidia Shield Core Agent", CATEGORY_OEM),
    "com.nvidia.shield.settings": ("Nvidia Shield TV Settings", CATEGORY_OEM),
    "com.nvidia.inputdevices": ("Nvidia Shield Controller Service", CATEGORY_OEM),
    "com.nvidia.tegraremote.server": ("Nvidia Shield Remote Server", CATEGORY_OEM),
    "com.nvidia.sharedstorage": ("Nvidia Shield Storage Provider", CATEGORY_OEM),

    # 8. Google & Android Core System Apps (46 Packages)
    "android": ("Android System", CATEGORY_SYSTEM),
    "com.android.systemui": ("System UI", CATEGORY_SYSTEM),
    "com.android.settings": ("Settings", CATEGORY_SYSTEM),
    "com.android.tv.settings": ("TV Settings", CATEGORY_SYSTEM),
    "com.android.vending": ("Google Play Store", CATEGORY_SYSTEM),
    "com.google.android.gms": ("Google Play Services", CATEGORY_SYSTEM),
    "com.google.android.gsf": ("Google Services Framework", CATEGORY_SYSTEM),
    "com.google.android.packageinstaller": ("Google Package Installer", CATEGORY_SYSTEM),
    "com.android.packageinstaller": ("Package Installer", CATEGORY_SYSTEM),
    "com.google.android.permissioncontroller": ("Permission Controller", CATEGORY_SYSTEM),
    "com.android.bluetooth": ("Bluetooth Service", CATEGORY_SYSTEM),
    "com.google.android.inputmethod.latin": ("Gboard TV Keyboard", CATEGORY_SYSTEM),
    "com.android.inputmethod.latin": ("AOSP Keyboard", CATEGORY_SYSTEM),
    "com.google.android.leanback.ime": ("Leanback Keyboard", CATEGORY_SYSTEM),
    "com.google.android.katniss": ("Google Assistant", CATEGORY_SYSTEM),
    "com.google.android.tv.assistant": ("Google Assistant TV", CATEGORY_SYSTEM),
    "com.google.android.apps.mediashell": ("Chromecast Built-in", CATEGORY_SYSTEM),
    "com.google.android.apps.tv.launcherx": ("Google TV Home", CATEGORY_SYSTEM),
    "com.google.android.tvlauncher": ("Android TV Home", CATEGORY_SYSTEM),
    "com.google.android.tvrecommendations": ("Android TV Core Services", CATEGORY_SYSTEM),
    "com.google.android.marvin.talkback": ("TalkBack", CATEGORY_SYSTEM),
    "com.google.android.tts": ("Google Speech Recognition & TTS", CATEGORY_SYSTEM),
    "com.google.android.webview": ("Android System WebView", CATEGORY_SYSTEM),
    "com.android.providers.tv": ("TV Provider", CATEGORY_SYSTEM),
    "com.android.providers.media": ("Media Provider", CATEGORY_SYSTEM),
    "com.android.providers.media.module": ("Media Module", CATEGORY_SYSTEM),
    "com.android.providers.downloads": ("Download Manager", CATEGORY_SYSTEM),
    "com.android.providers.settings": ("Settings Storage Provider", CATEGORY_SYSTEM),
    "com.android.shell": ("Android Shell", CATEGORY_SYSTEM),
    "com.android.externalstorage": ("External Storage Provider", CATEGORY_SYSTEM),
    "com.android.vpndialogs": ("VPN Dialogs", CATEGORY_SYSTEM),
    "com.android.captiveportallogin": ("Captive Portal Login", CATEGORY_SYSTEM),
    "com.dolby.android.audio.service": ("Dolby Audio", CATEGORY_SYSTEM),
    "com.android.dreams.basic": ("Basic Screensaver", CATEGORY_SYSTEM),
    "com.google.android.apps.tv.dreamx": ("Google TV Ambient", CATEGORY_SYSTEM),
    "com.google.android.tv.remote.service": ("Android TV Remote", CATEGORY_SYSTEM),
    "com.google.android.videos": ("Google TV Movies", CATEGORY_SYSTEM),
    "com.google.android.play.games": ("Google Play Games", CATEGORY_SYSTEM),
    "com.google.android.feedback": ("Feedback Reporter", CATEGORY_SYSTEM),
    "com.google.android.tungsten.setupwraith": ("Google TV Setup Wizard", CATEGORY_SYSTEM),
    "com.google.android.tungsten.overscanmouselayer": ("Google TV Overscan Layer", CATEGORY_SYSTEM),
    "com.google.android.apps.nbu.smartconnect.tv": ("Google Smart Connect", CATEGORY_SYSTEM),
    "com.android.keychain": ("Key Chain", CATEGORY_SYSTEM),
    "com.android.inputdevices": ("Input Devices", CATEGORY_SYSTEM),
    "com.android.location.fused": ("Fused Location", CATEGORY_SYSTEM),
    "com.android.certinstaller": ("Certificate Installer", CATEGORY_SYSTEM),
}

# Alias for backward-compatible naming
APP_CATALOG = CATALOG


# -----------------------------------------------------------------------------
# Heuristic Configuration Dictionaries & Lookup Tables (Explorer 2)
# -----------------------------------------------------------------------------

# Ordered by length descending so longer/more-specific prefixes match first
KNOWN_PREFIXES: Tuple[str, ...] = tuple(sorted([
    # Multi-level ecosystem & publisher prefixes
    "com.google.android.apps.tv.",
    "com.google.android.apps.",
    "com.google.android.tv.",
    "com.google.android.",
    "com.android.tv.",
    "com.android.",
    "google.android.",
    "com.app.",
    "com.apps.",
    "org.app.",
    "net.app.",
    "io.github.",
    "com.github.",
    "org.gitlab.",
    # Compound ccTLD prefixes
    "uk.co.", "jp.co.", "in.co.", "nz.co.", "za.co.", "kr.co.",
    "au.com.", "br.com.", "tr.com.", "mx.com.", "ar.com.", "sg.com.",
    "uk.org.", "au.org.", "uk.net.", "au.net.",
    # Generic TLDs
    "com.", "org.", "net.", "edu.", "gov.", "mil.", "int.", "io.", "ai.",
    "app.", "dev.", "tv.", "me.", "co.", "info.", "biz.", "xyz.", "mobi.",
    "cloud.", "pro.", "tech.", "online.", "site.", "store.", "vip.", "live.",
    "world.", "link.",
    # Common ccTLDs
    "uk.", "de.", "fr.", "jp.", "cn.", "in.", "ru.", "br.", "au.", "ca.",
    "es.", "it.", "nl.", "se.", "no.", "fi.", "dk.", "ch.", "at.", "be.",
    "pl.", "cz.", "gr.", "za.", "kr.", "tw.", "hk.", "sg.", "my.", "id.",
    "th.", "vn.", "ph.", "mx.", "ar.", "cl.", "ie.", "pt.", "il.", "tr.", "nz.",
    # Vendor / OS / Generic Developer
    "android.", "vendor.", "tools.", "custom.",
], key=len, reverse=True))

# Standard acronyms that must always remain in uppercase
KNOWN_ACRONYMS: Set[str] = {
    # TV, Display, and Video
    "TV", "HD", "FHD", "UHD", "4K", "8K", "3D", "2D",
    "IPTV", "OTT", "DVR", "PVR", "VOD", "EPG", "OTA", "DVB", "ATSC", "STB",
    "VLC", "XBMC", "SPMC", "MX", "BS", "KM",
    # Audio & Radio
    "FM", "AM", "DAB", "MP3", "MP4", "AAC", "FLAC", "WAV", "OGG", "EQ", "DSP",
    # Networking & Protocols
    "DLNA", "UPNP", "SMB", "NFS", "FTP", "SFTP", "SSH", "HTTP", "HTTPS", "URL", "URI",
    "IP", "TCP", "UDP", "DNS", "VPN", "LAN", "WAN", "WLAN", "BLE", "NFC", "MAC",
    # Systems, Hardware & Development
    "UI", "GUI", "UX", "OS", "AOSP", "APK", "ADB", "SDK", "API", "CLI", "TUI",
    "CPU", "GPU", "RAM", "ROM", "USB", "HDMI", "CEC", "AV", "ARC", "HDR", "SDR",
    "LED", "OLED", "QLED", "AI", "VR", "AR", "QR", "ID", "PIN", "SMS", "TTS", "IME",
    "DRM", "PAC", "ATV", "DTV", "PPSSPP",
}

# Specific official brand casing mappings
BRAND_CASING: Dict[str, str] = {
    "youtube": "YouTube",
    "wifi": "WiFi",
    "wi-fi": "Wi-Fi",
    "airplay": "AirPlay",
    "airdrop": "AirDrop",
    "chromecast": "Chromecast",
    "playstation": "PlayStation",
    "retroarch": "RetroArch",
    "videolan": "VideoLAN",
    "quicktime": "QuickTime",
    "soundcloud": "SoundCloud",
    "tunein": "TuneIn",
    "deezer": "Deezer",
    "spotify": "Spotify",
    "netflix": "Netflix",
    "kodi": "Kodi",
    "plex": "Plex",
    "jellyfin": "Jellyfin",
    "steamlink": "Steam Link",
    "geforcenow": "GeForce NOW",
    "moonlight": "Moonlight",
    "magisk": "Magisk",
}

# Common Android TV compound word prefixes and suffixes
COMPOUND_PREFIXES: Tuple[str, ...] = tuple(sorted([
    "video", "media", "smart", "speed", "file", "screen", "sound", "html",
    "print", "air", "radio", "tv", "web", "game", "audio", "cast", "live",
    "retro", "quick", "open", "free", "clean", "down", "home", "net", "super",
    "ultra", "mega", "easy", "fast", "auto", "photo", "voice", "cloud", "task",
    "living", "system", "input", "my", "pro", "lite", "all", "top", "the",
], key=len, reverse=True))

COMPOUND_SUFFIXES: Tuple[str, ...] = tuple(sorted([
    "player", "center", "tube", "test", "manager", "explorer", "mirror",
    "picker", "viewer", "spooler", "play", "fm", "am", "menu", "launcher",
    "browser", "cast", "share", "remote", "box", "hub", "room", "shell",
    "view", "load", "loader", "finder", "helper", "master", "direct",
    "stream", "music", "radio", "track", "droid", "link", "ui", "method",
], key=len, reverse=True))

def decompose_compound(word: str) -> List[str]:
    """Recursively decomposes a solid lowercase word into compound sub-tokens."""
    if not word or len(word) < 4:
        return []
    for pfx in COMPOUND_PREFIXES:
        if word.startswith(pfx) and len(word) > len(pfx):
            rem = word[len(pfx):]
            if rem in COMPOUND_SUFFIXES:
                return [pfx, rem]
            sub = decompose_compound(rem)
            if sub:
                return [pfx] + sub
    return []

# Boilerplate packaging tokens to prune when other meaningful tokens exist
FILLER_SUFFIXES: Set[str] = {
    "android", "app", "application", "mobile", "release", "debug", "package",
}

# Unicode-aware regex matching alphanumeric tokens, acronyms, and version tags
TOKEN_PATTERN: re.Pattern = re.compile(
    r"""
    (?:[0-9]+[kKdD])                                                                    # 4k, 8k, 3d, 2d
    | (?:[mM][pP][34])                                                                  # mp3, mp4, MP3, MP4
    | (?:[hH]26[45])                                                                    # h264, h265
    | (?:[vV][0-9]+)                                                                    # v2, v3, V2
    | [A-Z\u00C0-\u024F\u0400-\u042F]+(?=[A-Z\u00C0-\u024F\u0400-\u042F][a-z\u00DF-\u024F\u0430-\u044F]|\d|\b)  # Acronyms before TitleCase/digits
    | [A-Z\u00C0-\u024F\u0400-\u042F]?[a-z\u00DF-\u024F\u0430-\u044F]+               # TitleCase or lowercase words
    | [0-9]+                                                                            # Standalone numbers
    | [^\W\d_]+                                                                         # Any remaining Unicode word characters
    """,
    re.VERBOSE,
)


# -----------------------------------------------------------------------------
# Algorithmic Functions & Heuristics
# -----------------------------------------------------------------------------

def infer_brand(package_name: str) -> Optional[str]:
    """Infers manufacturer / brand affiliation from package name."""
    if not package_name:
        return None
    pkg = package_name.lower()
    if "sony" in pkg:
        return "sony"
    if "tcl" in pkg:
        return "tcl"
    if "droidtv" in pkg or "philips" in pkg:
        return "philips"
    if "hisense" in pkg or "jamdeo" in pkg or "vidaa" in pkg:
        return "hisense"
    if "xiaomi" in pkg or "mitv" in pkg:
        return "xiaomi"
    if "nvidia" in pkg:
        return "nvidia"
    if pkg.startswith("com.google.") or pkg.startswith("com.android.") or pkg == "android":
        return "google"
    if "amazon" in pkg:
        return "amazon"
    if "netflix" in pkg:
        return "netflix"
    if "apple" in pkg:
        return "apple"
    return None


def strip_reverse_domain_prefix(pkg: str) -> str:
    """Strips leading reverse-DNS TLDs, ccTLDs, or platform prefixes."""
    cleaned = (pkg or "").strip()
    changed = True
    while changed:
        changed = False
        for pfx in KNOWN_PREFIXES:
            if cleaned.lower().startswith(pfx) and len(cleaned) > len(pfx):
                cleaned = cleaned[len(pfx):]
                changed = True
                break
    return cleaned


def tokenize_package_name(raw_pkg: Optional[str], max_len: int = 512) -> List[str]:
    """
    Tokenizes a package name across dots, camelCase, snake_case, numbers,
    and compound words into normalized tokens.
    """
    if not raw_pkg or not isinstance(raw_pkg, str):
        return []

    s = raw_pkg.strip()[:max_len]
    if not s:
        return []

    # Handle all-uppercase inputs
    if s.isupper():
        s = s.lower()

    cleaned = strip_reverse_domain_prefix(s)

    # Split across standard delimiters
    segments = [seg for seg in re.split(r"[._\-+/: ]+", cleaned) if seg]
    if not segments:
        segments = [seg for seg in re.split(r"[._\-+/: ]+", s) if seg]
    if not segments:
        return [s]

    # Drop trailing filler words while multiple segments exist
    while len(segments) > 1 and segments[-1].lower() in FILLER_SUFFIXES:
        segments.pop()

    raw_tokens: List[str] = []
    prev_segment = ""
    for seg in segments:
        lower_seg = seg.lower()

        # Check if segment begins with preceding segment (e.g. amazon -> amazonvideo)
        if (
            prev_segment
            and len(prev_segment) >= 3
            and lower_seg.startswith(prev_segment)
            and len(lower_seg) > len(prev_segment)
        ):
            rem = lower_seg[len(prev_segment):]
            raw_tokens.extend([prev_segment, rem])
            prev_segment = lower_seg
            continue
        prev_segment = lower_seg

        if lower_seg in BRAND_CASING:
            raw_tokens.append(BRAND_CASING[lower_seg])
            continue

        decomposed = decompose_compound(lower_seg)
        if decomposed:
            raw_tokens.extend(decomposed)
        else:
            matches = TOKEN_PATTERN.findall(seg)
            if matches:
                raw_tokens.extend(matches)
            else:
                raw_tokens.append(seg)

    # Normalize tokens and deduplicate case-insensitively
    normalized: List[str] = []
    seen: Set[str] = set()
    for tok in raw_tokens:
        tok_low = tok.lower()
        if tok_low in seen:
            continue
        seen.add(tok_low)

        up = tok.upper()
        if up in KNOWN_ACRONYMS:
            normalized.append(up)
        elif tok_low in BRAND_CASING:
            normalized.append(BRAND_CASING[tok_low])
        elif len(tok_low) >= 2 and tok_low[0] == "v" and tok_low[1:].isdigit():
            normalized.append(f"V{tok_low[1:]}")
        elif tok.isdigit():
            normalized.append(tok)
        else:
            normalized.append(tok[:1].upper() + tok[1:])

    return normalized


def infer_category(tokens: List[str], raw_package: str = "") -> str:
    """
    Infers standard category from token list and raw package name
    following Explorer 2's 9-tier priority hierarchy.
    """
    all_terms = set(t.lower() for t in tokens)
    for seg in (raw_package or "").lower().split("."):
        all_terms.add(seg)

    def has_any(*keywords: str) -> bool:
        return any(k in all_terms or any(k in t for t in all_terms) for k in keywords)

    # 1. Launcher (highest precedence for shells/launchers)
    if has_any("launcher", "leanbacklauncher", "homemenu", "tvmenu", "homescreen", "projmymenu"):
        return CATEGORY_LAUNCHER

    # 2. Web Browser
    if has_any(
        "browser", "chrome", "firefox", "opera", "edge", "brave", "silk",
        "vivaldi", "puffin", "duckduckgo", "navigator",
    ):
        return CATEGORY_BROWSER

    # 3. Games & Emulation
    if has_any(
        "game", "arcade", "retro", "emulator", "retroarch", "ppsspp", "mame",
        "steamlink", "geforcenow", "moonlight", "playstation", "xbox", "nintendo",
        "sega", "rom", "controller", "joystick",
    ):
        return CATEGORY_GAMING

    # 4. Music & Audio
    if has_any(
        "music", "radio", "audio", "sound", "podcast", "tunein", "spotify",
        "deezer", "tidal", "pandora", "iheart", "soundcloud", "shazam",
        "audiomack", "ytmusic", "mp3", "flac", "equalizer",
    ):
        return CATEGORY_AUDIO

    # 5. Live TV & Sports
    if has_any(
        "iptv", "livetv", "sports", "sport", "broadcast", "channel", "tuner",
        "epg", "dvb", "atsc", "espn", "sling", "fubo", "tivimate", "ott",
        "dvr", "pvr", "antenna",
    ):
        return CATEGORY_LIVE_TV

    # 6. Streaming & Video (Media Centers & Players)
    if has_any(
        "stream", "video", "movie", "cinema", "film", "theater", "player",
        "media", "plex", "kodi", "jellyfin", "emby", "vlc", "tube", "netflix",
        "primevideo", "disney", "hulu", "peacock", "paramount", "max", "hbo",
        "crunchyroll", "anime", "cast", "screenmirror", "airplay", "dlna",
    ):
        return CATEGORY_STREAMING_VIDEO

    # 7. Tools & Utilities
    if has_any(
        "tool", "util", "file", "explorer", "commander", "manager",
        "downloader", "clean", "speed", "speedtest", "backup", "network",
        "wifi", "vpn", "remote", "adb", "dns", "terminal", "monitor", "cpu",
        "task", "benchmark", "installer", "sideload", "xplore",
    ):
        return CATEGORY_TOOLS_UTILITIES

    # 8. System & OEM
    if has_any(
        "system", "setting", "settings", "setup", "provision", "service",
        "framework", "keyboard", "ime", "inputmethod", "bluetooth", "driver",
        "oem", "updater", "ota",
    ):
        return CATEGORY_SYSTEM_OEM

    return CATEGORY_APPLICATIONS


def resolve_fallback_name(package_name: str) -> str:
    """Convenience helper extracting tokenized fallback display name."""
    if not package_name or not isinstance(package_name, str) or not package_name.strip():
        return "Unknown"
    tokens = tokenize_package_name(package_name)
    return " ".join(tokens) if tokens else package_name.strip()


def infer_fallback_category(package_name: str, friendly_name: str = "") -> str:
    """Convenience helper inferring fallback category from package ID and name."""
    tokens = tokenize_package_name(f"{package_name} {friendly_name}")
    return infer_category(tokens, package_name)


def fallback_app_info(package_name: str) -> AppMetadata:
    """
    Generates an AppMetadata instance for an unlisted package using token heuristics.
    Adheres strictly to Explorer 2's benchmarked algorithm.
    """
    if not package_name or not isinstance(package_name, str):
        return AppMetadata(
            name="Unknown",
            category=CATEGORY_APPLICATIONS,
            is_known=False,
            package_name=str(package_name or ""),
            brand=None,
        )

    clean = package_name.strip()
    if not clean:
        return AppMetadata(
            name="Unknown",
            category=CATEGORY_APPLICATIONS,
            is_known=False,
            package_name="",
            brand=None,
        )

    tokens = tokenize_package_name(clean)
    name = " ".join(tokens) if tokens else clean
    category = infer_category(tokens, clean)

    return AppMetadata(
        name=name,
        category=category,
        is_known=False,
        package_name=clean,
        brand=infer_brand(clean),
    )


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def normalize_package_name(package_name: str) -> str:
    """Strip whitespace and normalize to lowercase for O(1) dictionary key lookup."""
    if not package_name:
        return ""
    return package_name.strip().lower()


def get_app_metadata(
    package_name: str,
    fallback_resolver: Optional[Callable[[str], Tuple[str, str]]] = None,
) -> AppMetadata:
    """
    Resolve an Android package ID to its friendly display name and category.
    Performs pure O(1) dictionary lookup in CATALOG.
    If not found, delegates to the fallback tokenizer.

    Args:
        package_name: Reverse-domain Android package name (e.g. 'com.netflix.ninja').
        fallback_resolver: Optional callable accepting a package name and returning (name, category).
            If omitted, uses the built-in fallback tokenizer.

    Returns:
        AppMetadata NamedTuple containing (name, category, is_known, package_name, brand).
    """
    clean_pkg = (package_name or "").strip()
    norm_pkg = clean_pkg.lower()

    if not norm_pkg:
        return AppMetadata(
            name="Unknown",
            category=CATEGORY_APPLICATIONS,
            is_known=False,
            package_name="",
            brand=None,
        )

    # O(1) Catalog lookup
    if norm_pkg in CATALOG:
        val = CATALOG[norm_pkg]
        name = val[0]
        category = val[1]
        brand = val[2] if len(val) >= 3 else infer_brand(clean_pkg)
        return AppMetadata(
            name=name,
            category=category,
            is_known=True,
            package_name=clean_pkg,
            brand=brand,
        )

    # Fallback to custom resolver if provided
    if fallback_resolver is not None:
        fb_name, fb_cat = fallback_resolver(clean_pkg)
        return AppMetadata(
            name=fb_name,
            category=fb_cat,
            is_known=False,
            package_name=clean_pkg,
            brand=infer_brand(clean_pkg),
        )

    # Standard fallback heuristic
    return fallback_app_info(clean_pkg)


def resolve_app(package_name: str) -> AppMetadata:
    """Primary API: Resolves an Android TV package name to AppMetadata."""
    return get_app_metadata(package_name)


def get_app_name(package_name: str) -> str:
    """Convenience helper returning only the friendly display name."""
    return get_app_metadata(package_name).name


def get_app_category(package_name: str) -> str:
    """Convenience helper returning only the functional category."""
    return get_app_metadata(package_name).category


def is_known_app(package_name: str) -> bool:
    """Check if package exists in the curated catalog."""
    if not package_name:
        return False
    return package_name.strip().lower() in CATALOG


def format_app_display(
    app: Union[str, AppMetadata],
    include_category: bool = True,
    bracket_name: bool = True,
    safety_label: Optional[str] = None,
    max_width: Optional[int] = None,
    max_name_len: Optional[int] = None,
    template: Optional[str] = None,
) -> str:
    """
    Format package into standard UI string for CLI / TUI screens.

    Default Format:
        '[Friendly Name] (package.id) - [Category]'
    Example:
        '[Netflix] (com.netflix.ninja) - [Streaming]'
    With Safety Label:
        '[Sony BRAVIA Sync] (com.sony.dtv.braviasync) - [OEM Components / SAFE]'
    Without Category:
        '[Netflix] (com.netflix.ninja)'
    """
    if isinstance(app, str):
        meta = resolve_app(app)
        pkg_name = meta.package_name or app.strip()
    else:
        meta = app
        pkg_name = meta.package_name

    name = meta.name
    if max_name_len and len(name) > max_name_len:
        name = name[: max_name_len - 3] + "..."

    if template is not None:
        return template.format(
            name=name,
            package=pkg_name,
            category=meta.category,
            is_known=meta.is_known,
            brand=meta.brand,
        )

    name_str = f"[{name}]" if bracket_name else name

    if safety_label and include_category:
        cat_suffix = f" - [{meta.category} / {safety_label}]"
    elif safety_label:
        cat_suffix = f" - [{safety_label}]"
    elif include_category:
        cat_suffix = f" - [{meta.category}]"
    else:
        cat_suffix = ""

    formatted = f"{name_str} ({pkg_name}){cat_suffix}"
    if max_width and len(formatted) > max_width:
        formatted = formatted[: max_width - 3] + "..."
    return formatted


def list_catalog_apps(category: Optional[str] = None) -> List[AppMetadata]:
    """Return all curated catalog entries, optionally filtered by category."""
    results: List[AppMetadata] = []
    for pkg, (name, cat) in sorted(CATALOG.items()):
        if category is None or cat == category:
            results.append(
                AppMetadata(
                    name=name,
                    category=cat,
                    is_known=True,
                    package_name=pkg,
                    brand=infer_brand(pkg),
                )
            )
    return results


def get_catalog_stats() -> Dict[str, Any]:
    """Return statistical summary of the curated catalog."""
    counts: Dict[str, int] = {}
    for _, cat in CATALOG.values():
        counts[cat] = counts.get(cat, 0) + 1
    return {
        "total_curated_apps": len(CATALOG),
        "categories": counts,
    }
