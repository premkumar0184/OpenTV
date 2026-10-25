package org.opentv.launcher;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Zero-asset multi-lingual localization engine.
 * Covers 17 major TV languages with dynamic fallback.
 */
public final class Strings {

    public static final String[] EN = {
        "Settings", "Add app", "Network", "Offline", "Sound", "Picture",
        "Move", "Replace", "Remove from home", "Uninstall", "App info",
        "Use the arrows to move it, then press OK", "Every app is already here", "Add an app", "Replace %s", "Wallpaper", "TV settings", "Brightness",
        "Inputs", "HDMI", "Wi-Fi", "Ethernet", "OLED Protection"
    };

    private static final Map<String, String[]> LANGS = new HashMap<>();

    static {
        LANGS.put("ar", new String[] {
            "الإعدادات", "إضافة تطبيق", "الشبكة", "غير متصل", "الصوت", "الصورة",
            "نقل", "استبدال", "إزالة من الشاشة الرئيسية", "إلغاء التثبيت", "معلومات التطبيق",
            "استخدم الأسهم لنقله، ثم اضغط OK", "كل التطبيقات موجودة هنا", "إضافة تطبيق", "استبدال %s", "الخلفية", "إعدادات التلفزيون", "السطوع",
            "المداخل", "HDMI", "Wi-Fi", "إيثرنت", "حماية OLED"
        });
        LANGS.put("de", new String[] {
            "Einstellungen", "App hinzufügen", "Netzwerk", "Offline", "Ton", "Bild",
            "Verschieben", "Ersetzen", "Vom Startbildschirm entfernen", "Deinstallieren", "App-Info",
            "Mit den Pfeiltasten verschieben, dann OK drücken", "Alle Apps sind schon da", "App hinzufügen", "%s ersetzen", "Hintergrund", "TV-Einstellungen", "Helligkeit",
            "Eingänge", "HDMI", "WLAN", "Ethernet", "OLED-Schutz"
        });
        LANGS.put("es", new String[] {
            "Ajustes", "Añadir app", "Red", "Sin conexión", "Sonido", "Imagen",
            "Mover", "Reemplazar", "Quitar del inicio", "Desinstalar", "Info. de la app",
            "Usa las flechas para moverla y pulsa OK", "Todas las apps ya están aquí", "Añadir una app", "Reemplazar %s", "Fondo de pantalla", "Ajustes de la TV", "Brillo",
            "Entradas", "HDMI", "Wi-Fi", "Ethernet", "Protección OLED"
        });
        LANGS.put("fr", new String[] {
            "Paramètres", "Ajouter une app", "Réseau", "Hors ligne", "Son", "Image",
            "Déplacer", "Remplacer", "Retirer de l'accueil", "Désinstaller", "Infos sur l'app",
            "Utilisez les flèches pour la déplacer, puis appuyez sur OK", "Toutes les apps sont déjà là", "Ajouter une app", "Remplacer %s", "Fond d'écran", "Paramètres du téléviseur", "Luminosité",
            "Entrées", "HDMI", "Wi-Fi", "Ethernet", "Protection OLED"
        });
        LANGS.put("hi", new String[] {
            "सेटिंग्स", "ऐप जोड़ें", "नेटवर्क", "ऑफ़लाइन", "ध्वनि", "चित्र",
            "ले जाएँ", "बदलें", "होम से हटाएँ", "अनइंस्टॉल करें", "ऐप की जानकारी",
            "तीर से खिसकाएँ, फिर OK दबाएँ", "सभी ऐप पहले से यहाँ हैं", "ऐप जोड़ें", "%s बदलें", "वॉलपेपर", "टीवी सेटिंग्स", "चमक",
            "इनपुट", "HDMI", "वाई-फ़ाई", "ईथरनेट", "OLED सुरक्षा"
        });
        String[] id = {
            "Setelan", "Tambah aplikasi", "Jaringan", "Offline", "Suara", "Gambar",
            "Pindahkan", "Ganti", "Hapus dari beranda", "Uninstal", "Info aplikasi",
            "Gunakan tombol panah untuk memindahkan, lalu tekan OK", "Semua aplikasi sudah ada di sini", "Tambah aplikasi", "Ganti %s", "Wallpaper", "Setelan TV", "Kecerahan",
            "Input", "HDMI", "Wi-Fi", "Ethernet", "Perlindungan OLED"
        };
        LANGS.put("id", id);
        LANGS.put("in", id);

        LANGS.put("it", new String[] {
            "Impostazioni", "Aggiungi app", "Rete", "Offline", "Audio", "Immagine",
            "Sposta", "Sostituisci", "Rimuovi dalla home", "Disinstalla", "Info app",
            "Usa le frecce per spostarla, poi premi OK", "Tutte le app sono già qui", "Aggiungi un'app", "Sostituisci %s", "Sfondo", "Impostazioni TV", "Luminosità",
            "Ingressi", "HDMI", "Wi-Fi", "Ethernet", "Protezione OLED"
        });
        LANGS.put("ja", new String[] {
            "設定", "アプリを追加", "ネットワーク", "オフライン", "サウンド", "画像",
            "移動", "置き換え", "ホームから削除", "アンインストール", "アプリ情報",
            "矢印キーで移動して、OK を押してください", "すべてのアプリが追加済みです", "アプリを追加", "%s を置き換え", "壁紙", "テレビの設定", "明るさ",
            "入力", "HDMI", "Wi-Fi", "イーサネット", "OLED保護"
        });
        LANGS.put("ko", new String[] {
            "설정", "앱 추가", "네트워크", "오프라인", "소리", "화면",
            "이동", "바꾸기", "홈에서 삭제", "제거", "앱 정보",
            "화살표로 옮긴 다음 OK를 누르세요", "모든 앱이 이미 있습니다", "앱 추가", "%s 바꾸기", "배경화면", "TV 설정", "밝기",
            "입력", "HDMI", "Wi-Fi", "이더넷", "OLED 보호"
        });
        LANGS.put("nl", new String[] {
            "Instellingen", "App toevoegen", "Netwerk", "Offline", "Geluid", "Beeld",
            "Verplaatsen", "Vervangen", "Van startscherm halen", "Verwijderen", "App-info",
            "Verplaats met de pijltjes en druk dan op OK", "Alle apps staan er al", "Een app toevoegen", "%s vervangen", "Achtergrond", "Tv-instellingen", "Helderheid",
            "Ingangen", "HDMI", "Wifi", "Ethernet", "OLED-bescherming"
        });
        LANGS.put("pl", new String[] {
            "Ustawienia", "Dodaj aplikację", "Sieć", "Offline", "Dźwięk", "Obraz",
            "Przenieś", "Zamień", "Usuń z ekranu głównego", "Odinstaluj", "Informacje o aplikacji",
            "Przesuń strzałkami, potem naciśnij OK", "Wszystkie aplikacje już tu są", "Dodaj aplikację", "Zamień %s", "Tapeta", "Ustawienia telewizora", "Jasność",
            "Wejścia", "HDMI", "Wi-Fi", "Ethernet", "Ochrona OLED"
        });
        LANGS.put("pt", new String[] {
            "Configurações", "Adicionar app", "Rede", "Sem conexão", "Som", "Imagem",
            "Mover", "Substituir", "Remover do início", "Desinstalar", "Informações do app",
            "Use as setas para mover e depois aperte OK", "Todos os apps já estão aqui", "Adicionar um app", "Substituir %s", "Plano de fundo", "Configurações da TV", "Brilho",
            "Entradas", "HDMI", "Wi-Fi", "Ethernet", "Proteção OLED"
        });
        LANGS.put("ru", new String[] {
            "Настройки", "Добавить", "Сеть", "Нет сети", "Звук", "Изображение",
            "Переместить", "Заменить", "Убрать с главного экрана", "Удалить", "О приложении",
            "Перемещайте стрелками, затем нажмите OK", "Все приложения уже здесь", "Добавить приложение", "Заменить %s", "Обои", "Настройки телевизора", "Яркость",
            "Входы", "HDMI", "Wi-Fi", "Ethernet", "Защита OLED"
        });
        LANGS.put("tr", new String[] {
            "Ayarlar", "Uygulama ekle", "Ağ", "Çevrimdışı", "Ses", "Görüntü",
            "Taşı", "Değiştir", "Ana ekrandan kaldır", "Kaldır", "Uygulama bilgisi",
            "Ok tuşlarıyla taşıyın, sonra OK'e basın", "Tüm uygulamalar zaten burada", "Uygulama ekle", "Değiştir: %s", "Duvar kağıdı", "TV ayarları", "Parlaklık",
            "Girişler", "HDMI", "Wi-Fi", "Ethernet", "OLED Koruması"
        });
        LANGS.put("uk", new String[] {
            "Налаштування", "Додати додаток", "Мережа", "Офлайн", "Звук", "Зображення",
            "Перемістити", "Замінити", "Прибрати з головного екрана", "Видалити", "Інформація про додаток",
            "Переміщуйте стрілками, а потім натисніть OK", "Усі додатки вже тут", "Додати додаток", "Замінити %s", "Шпалери", "Налаштування телевізора", "Яскравість",
            "Входи", "HDMI", "Wi-Fi", "Ethernet", "Захист OLED"
        });
        LANGS.put("zh", new String[] {
            "设置", "添加应用", "网络", "未联网", "声音", "图像",
            "移动", "替换", "从主屏幕移除", "卸载", "应用信息",
            "用方向键移动，然后按 OK", "所有应用都已在这里", "添加应用", "替换 %s", "壁纸", "电视设置", "亮度",
            "输入源", "HDMI", "Wi-Fi", "以太网", "OLED保护"
        });
        String[] hant = {
            "設定", "新增應用程式", "網路", "離線", "音效", "影像",
            "移動", "取代", "從主畫面移除", "解除安裝", "應用程式資訊",
            "使用方向鍵移動，然後按 OK", "所有應用程式都已在這裡", "新增應用程式", "取代 %s", "桌布", "電視設定", "亮度",
            "輸入來源", "HDMI", "Wi-Fi", "乙太網路", "OLED保護"
        };
        LANGS.put("zh-TW", hant);
        LANGS.put("zh-HK", hant);
        LANGS.put("zh-MO", hant);
    }

    private Strings() {}

    public static String lang() {
        return Locale.getDefault().getLanguage();
    }

    public static String t(String en) {
        Locale l = Locale.getDefault();
        String key = l.getLanguage() + "-" + l.getCountry();
        if ("zh".equals(l.getLanguage())) {
            if ("Hant".equals(l.getScript())) key = "zh-TW";
            else if ("Hans".equals(l.getScript())) key = "zh";
        }
        String[] table = LANGS.get(key);
        if (table == null) table = LANGS.get(l.getLanguage());
        if (table == null) return en;

        for (int i = 0; i < EN.length; i++) {
            if (EN[i].equals(en)) {
                return i < table.length ? table[i] : en;
            }
        }
        return en;
    }

    public static String datePattern() {
        if ("en".equals(lang())) return "EEEE, d MMMM";
        return android.text.format.DateFormat.getBestDateTimePattern(Locale.getDefault(), "EEEEdMMMM");
    }
}
