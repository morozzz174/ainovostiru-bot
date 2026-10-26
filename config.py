import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.getenv("DOTENV_PATH") or os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
# Прокси для Telegram API, например socks5://127.0.0.1:10809 или
# http://user:pass@host:port. Нужен там, где api.telegram.org недоступен
# напрямую (приложение должно быть запущено).
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "")
TG_CONNECT_TIMEOUT = float(os.getenv("TG_CONNECT_TIMEOUT", "30"))
TG_READ_TIMEOUT = float(os.getenv("TG_READ_TIMEOUT", "60"))
DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(BASE_DIR, "bot_data.db")
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "2"))
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "3"))
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "60"))

# Постинг по расписанию: N постов в день, равномерно внутри окна.
# 10-18 и 4 поста дают слоты 10:00, 12:00, 14:00, 16:00.
# 0 = старый режим "каждые SCHEDULE_INTERVAL_HOURS часов".
POSTING_START_HOUR = int(os.getenv("POSTING_START_HOUR", "10"))
POSTING_END_HOUR = int(os.getenv("POSTING_END_HOUR", "18"))
POSTS_PER_DAY = int(os.getenv("POSTS_PER_DAY", "0"))
# Пусто = локальное время машины. Пример: Europe/Moscow
POST_TIMEZONE = os.getenv("POST_TIMEZONE", "").strip()

THEME = os.getenv("THEME", "ai")
BRAND_NAME = os.getenv("BRAND_NAME", "AINOVOSTI.RU")
POST_MODE = os.getenv("POST_MODE", "mixed")
VIDEO_DURATION = int(os.getenv("VIDEO_DURATION", "15"))
MUSIC_ENABLED = os.getenv("MUSIC_ENABLED", "true").lower() == "true"
MUSIC_STYLE = os.getenv("MUSIC_STYLE", "auto")
MUSIC_FILE = os.getenv("MUSIC_FILE", "")
MUSIC_VOLUME = float(os.getenv("MUSIC_VOLUME", "0.35"))
MUSIC_SEED = os.getenv("MUSIC_SEED", "")
VOICE_ENABLED = os.getenv("VOICE_ENABLED", "true").lower() == "true"
VOICE_NAME = os.getenv("VOICE_NAME", "ru-RU-DmitryNeural")
VOICE_FALLBACK_NAME = os.getenv("VOICE_FALLBACK_NAME", "ru-RU-SvetlanaNeural")
VOICE_RATE = os.getenv("VOICE_RATE", "+5%")
VOICE_MAX_CHARS = int(os.getenv("VOICE_MAX_CHARS", "600"))
VOICE_RETRIES = int(os.getenv("VOICE_RETRIES", "3"))
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
VIDEO_MIN_DURATION = int(os.getenv("VIDEO_MIN_DURATION", "20"))
VIDEO_MAX_DURATION = int(os.getenv("VIDEO_MAX_DURATION", "60"))
VIDEO_DURATION_TAIL = float(os.getenv("VIDEO_DURATION_TAIL", "5"))
VIDEO_SWAY_X = float(os.getenv("VIDEO_SWAY_X", "1.8"))
VIDEO_SWAY_Y = float(os.getenv("VIDEO_SWAY_Y", "1.1"))
VIDEO_SWAY_PERIOD = float(os.getenv("VIDEO_SWAY_PERIOD", "7"))
VIDEO_SWAY_PERIOD_Y = float(os.getenv("VIDEO_SWAY_PERIOD_Y", "4.6"))
VIDEO_ZOOM = float(os.getenv("VIDEO_ZOOM", "0.07"))
VIDEO_SWEEP_PERIOD = float(os.getenv("VIDEO_SWEEP_PERIOD", "9"))
VIDEO_BOKEH = int(os.getenv("VIDEO_BOKEH", "18"))
# Формат видео для Telegram. vertical - 9:16 (1080x1920), horizontal - 16:9 (1200x630)
VIDEO_ORIENTATION = os.getenv("VIDEO_ORIENTATION", "vertical")

TT_ENABLED = os.getenv("TT_ENABLED", "false").lower() == "true"
TT_ACCESS_TOKEN = os.getenv("TT_ACCESS_TOKEN", "")
TT_REFRESH_TOKEN = os.getenv("TT_REFRESH_TOKEN", "")
TT_CLIENT_KEY = os.getenv("TT_CLIENT_KEY", "")
TT_CLIENT_SECRET = os.getenv("TT_CLIENT_SECRET", "")
TT_OPEN_ID = os.getenv("TT_OPEN_ID", "")
TT_REDIRECT_URI = os.getenv("TT_REDIRECT_URI", "https://localhost/tiktok-callback")
TT_PRIVACY_LEVEL = os.getenv("TT_PRIVACY_LEVEL", "SELF_ONLY")
TT_MAX_CHARS = int(os.getenv("TT_MAX_CHARS", "2200"))
TT_CHUNK_SIZE = int(os.getenv("TT_CHUNK_SIZE", str(10 * 1024 * 1024)))
TT_STATUS_ATTEMPTS = int(os.getenv("TT_STATUS_ATTEMPTS", "10"))
TT_STATUS_INTERVAL = int(os.getenv("TT_STATUS_INTERVAL", "6"))
TT_DISABLE_DUET = os.getenv("TT_DISABLE_DUET", "true").lower() == "true"
TT_DISABLE_COMMENT = os.getenv("TT_DISABLE_COMMENT", "false").lower() == "true"
TT_DISABLE_STITCH = os.getenv("TT_DISABLE_STITCH", "true").lower() == "true"

DZEN_ENABLED = os.getenv("DZEN_ENABLED", "false").lower() == "true"
USE_THEMED_IMAGES = os.getenv("USE_THEMED_IMAGES", "true").lower() == "true"
# Ориентация искомых фото: portrait (9:16, для видео) или landscape (для постов)
IMAGE_ORIENTATION = os.getenv("IMAGE_ORIENTATION", "portrait")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
IG_PROXY = os.getenv("IG_PROXY", "")
IG_2FA_CODE = os.getenv("IG_2FA_CODE", "")
IG_2FA_CALLBACK = None
IG_USER_AGENT = os.getenv("IG_USER_AGENT", "")
IG_DEVICE = os.getenv("IG_DEVICE", "")
IG_LOCALE = os.getenv("IG_LOCALE", "ru_RU")
IG_DELAY_RANGE = (1, 3)
IG_REQUEST_TIMEOUT = 30
IG_LOGIN_MAX_RETRIES = int(os.getenv("IG_LOGIN_MAX_RETRIES", "3"))
IG_POST_MAX_RETRIES = int(os.getenv("IG_POST_MAX_RETRIES", "3"))
IG_RETRY_DELAY = int(os.getenv("IG_RETRY_DELAY", "10"))
IG_FEEDBACK_WAIT = int(os.getenv("IG_FEEDBACK_WAIT", "300"))

NEWS_SOURCES_AI = {
    "habr_ai": {
        "name": "Habr",
        "url": "https://habr.com/ru/rss/hubs/artificial_intelligence/articles/",
        "lang": "ru",
    },
    "3dnews": {
        "name": "3DNews",
        "url": "https://3dnews.ru/news/rss/",
        "lang": "ru",
    },
    "techcrunch_ai": {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "lang": "en",
    },
    "venturebeat_ai": {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/category/ai/feed/",
        "lang": "en",
    },
    "theverge": {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "lang": "en",
    },
    "mit_tech_review": {
        "name": "MIT Tech Review",
        "url": "https://www.technologyreview.com/feed/",
        "lang": "en",
    },
    "ars_technica": {
        "name": "Ars Technica",
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "lang": "en",
    },
}

NEWS_SOURCES_FACTS = {
    "historynet": {
        "name": "HistoryNet",
        "url": "https://www.historynet.com/feed/",
        "lang": "en",
    },
    "nasa": {
        "name": "NASA",
        "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
        "lang": "en",
    },
    "astronomy": {
        "name": "Astronomy.com",
        "url": "https://www.astronomy.com/feed/",
        "lang": "en",
    },
    "universetoday": {
        "name": "Universe Today",
        "url": "https://www.universetoday.com/feed/",
        "lang": "en",
    },

    "tass_science": {
        "name": "ТАСС Наука",
        "url": "https://tass.ru/rss/v2.xml?category=science",
        "lang": "ru",
    },
    "naked_science": {
        "name": "Naked Science",
        "url": "https://naked-science.ru/feed",
        "lang": "ru",
    },
    "lenta_science": {
        "name": "Lenta Наука",
        "url": "https://lenta.ru/rss/news/science/",
        "lang": "ru",
    },
    "gazeta_science": {
        "name": "Gazeta Наука",
        "url": "https://www.gazeta.ru/export/rss/science.xml",
        "lang": "ru",
    },
    "rg_science": {
        "name": "РГ Наука",
        "url": "https://rg.ru/xml/index.xml",
        "lang": "ru",
    },
    "newscientist": {
        "name": "Phys.org",
        "url": "https://phys.org/rss-feed/",
        "lang": "en",
    },
    "sciencedaily": {
        "name": "ScienceDaily",
        "url": "https://www.sciencedaily.com/rss/all.xml",
        "lang": "en",
    },
    "wired": {
        "name": "Wired",
        "url": "https://www.wired.com/feed/rss",
        "lang": "en",
    },
    "bigthink": {
        "name": "Big Think",
        "url": "https://bigthink.com/feed/",
        "lang": "en",
    },
    "quanta": {
        "name": "Quanta Magazine",
        "url": "https://www.quantamagazine.org/feed/",
        "lang": "en",
    },
    "aeon": {
        "name": "Aeon",
        "url": "https://aeon.co/feed.rss",
        "lang": "en",
    },
    "nautilus": {
        "name": "Nautilus",
        "url": "https://nautil.us/feed/",
        "lang": "en",
    },
    "openculture": {
        "name": "Open Culture",
        "url": "https://www.openculture.com/feed",
        "lang": "en",
    },
}

NEWS_SOURCES_BEAUTY = {
    # Дерматология и клиническая косметология
    "dermatology_times": {
        "name": "Dermatology Times",
        "url": "https://www.dermatologytimes.com/rss.xml",
        "lang": "en",
    },
    # Наука о старении и долголетии
    "fightaging": {
        "name": "Fight Aging",
        "url": "https://www.fightaging.org/feed/",
        "lang": "en",
    },
    "frontiers_aging": {
        "name": "Frontiers in Aging",
        "url": "https://www.frontiersin.org/journals/aging/rss",
        "lang": "en",
    },
    # Рецензируемые исследования
    "plos_biology": {
        "name": "PLOS Biology",
        "url": "https://journals.plos.org/plosbiology/feed/atom",
        "lang": "en",
    },
    "medical_xpress": {
        "name": "Medical Xpress",
        "url": "https://medicalxpress.com/rss-feed/",
        "lang": "en",
    },
    "sciencedaily_health": {
        "name": "ScienceDaily Health",
        "url": "https://www.sciencedaily.com/rss/health_medicine.xml",
        "lang": "en",
    },
    # Индустрия и потребительский сегмент
    "allure": {
        "name": "Allure",
        "url": "https://www.allure.com/feed/rss",
        "lang": "en",
    },
    "glamour": {
        "name": "Glamour",
        "url": "https://www.glamour.com/feed/rss",
        "lang": "en",
    },
    "newbeauty": {
        "name": "NewBeauty",
        "url": "https://www.newbeauty.com/feed/",
        "lang": "en",
    },
    # Русскоязычные
    "naked_beauty": {
        "name": "Naked Science",
        "url": "https://naked-science.ru/feed",
        "lang": "ru",
    },
    "hi_news": {
        "name": "Hi-News",
        "url": "https://hi-news.ru/feed/",
        "lang": "ru",
    },
    "tass_science_beauty": {
        "name": "ТАСС Наука",
        "url": "https://tass.ru/rss/v2.xml?category=science",
        "lang": "ru",
    },
    "gazeta_science_beauty": {
        "name": "Газета Наука",
        "url": "https://www.gazeta.ru/export/rss/science.xml",
        "lang": "ru",
    },
    "tass_health_beauty": {
        "name": "ТАСС Здоровье",
        "url": "https://tass.ru/rss/v2.xml?category=zdorovie",
        "lang": "ru",
    },
    "lenta_science_beauty": {
        "name": "Lenta.ru Наука",
        "url": "https://lenta.ru/rss/news/science/",
        "lang": "ru",
    },
    "interfax_science_beauty": {
        "name": "Интерфакс Наука",
        "url": "https://www.interfax.ru/rss.asp?cat=science",
        "lang": "ru",
    },
    "ixbt_beauty": {
        "name": "iXBT",
        "url": "https://www.ixbt.com/export/news.rss",
        "lang": "ru",
    },

    # Питание и образ жизни - основной вклад в долголетие (80% попадание)
    "sciencedaily_nutrition": {
        "name": "ScienceDaily Nutrition",
        "url": "https://www.sciencedaily.com/rss/health_medicine/nutrition.xml",
        "lang": "en",
    },
    "sciencedaily_health": {
        "name": "ScienceDaily Health",
        "url": "https://www.sciencedaily.com/rss/health_medicine.xml",
        "lang": "en",
    },
    # Дерматология и эстетическая медицина
    "plos_one": {
        "name": "PLOS ONE",
        "url": "https://journals.plos.org/plosone/feed/atom",
        "lang": "en",
    },
    # Здоровье и долголетие
    "guardian_health": {
        "name": "The Guardian Health",
        "url": "https://www.theguardian.com/society/health/rss",
        "lang": "en",
    },
    "science_news": {
        "name": "Phys.org",
        "url": "https://phys.org/rss-feed/",
        "lang": "en",
    },
    "lemonde_sante": {
        "name": "Le Monde Santé",
        "url": "https://www.lemonde.fr/sante/rss_full.xml",
        "lang": "fr",
    },
    "premium_beauty": {
        "name": "Premium Beauty News",
        "url": "https://www.premiumbeautynews.com/spip.php?page=backend&lang=en",
        "lang": "en",
    },
    "glossy": {
        "name": "Glossy",
        "url": "https://www.glossy.co/feed/",
        "lang": "en",
    },
}

NEWS_SOURCES_METAL = {
    # Канал русскоязычный и сфокусирован на РФ и СНГ, поэтому источники
    # подобраны по региону: российские отраслевые порталы, украинские и
    # белорусские/казахстанские ленты, плюс деловые СМИ РФ. Глобальные
    # англоязычные ленты (World Steel, Stainless Steel World, Investing)
    # убраны - они давали новости про США и Европу.
    #
    # Отраслевые HTML-источники: главный контент для труб и металлопроката.
    "metaltorg": {
        "name": "MetalTorg.Ru",
        "type": "html",
        "url": "https://www.metaltorg.ru/news/",
        "lang": "ru",
        "mode": "block",
        "item_selector": "td.txt",
        "title_selector": "a.news[href^='/n/']",
        "link_regex": r"/n/[0-9A-Z]+$",
        "require_keyword": False,
    },
    "metalbulletin": {
        "name": "МеталлБюллетин",
        "type": "html",
        "url": "https://www.metalbulletin.ru/",
        "lang": "ru",
        "mode": "pairs",
        "title_selector": "a.mainnews, a.news",
        "desc_selector": "a.normal_news",
        "link_contains": "/news/",
        "require_keyword": False,
        # Лента сильно разбавлена мировыми рынками, поэтому берём только
        # материалы с явной привязкой к РФ/СНГ.
        "require_geo": True,
    },
    "metallurgprom": {
        "name": "Металлургпром",
        "type": "html",
        "url": "https://metallurgprom.org/news",
        "lang": "ru",
        "mode": "block",
        "item_selector": "div.news-item",
        "title_selector": "h3.entry-title-index a[href]",
        "desc_selector": "div.entry-content-index",
        "image_style_selector": "a.news-item-img",
        "image_style_regex": r"background-image:url\('([^']+)'\)",
        "link_contains": "/news/",
        "require_keyword": False,
    },
    "metalinfo": {
        "name": "Металлосфера (МеталлИнфо)",
        "type": "html",
        "url": "https://www.metalinfo.ru/",
        "lang": "ru",
        "timeout": 8,
        "mode": "block",
        "item_selector": "div.news-list p, div.col-md-9",
        "title_selector": "a[href*='/ru/news/']",
        "desc_selector": "div.news-body",
        "image_selector": "img.news-image",
        "link_contains": "/ru/news/",
        "link_regex": r"/ru/news/\d+$",
        "require_keyword": True,
    },
    "rusmet": {
        "name": "Русмет",
        "type": "rss",
        "url": "https://www.rusmet.ru/feed/",
        "lang": "ru",
        # RSS отдаёт первые абзацы новости, HTML-лента - только заголовки.
        "require_keyword": False,
    },
    "minpromtorg": {
        "name": "Минпромторг России",
        "type": "html",
        "url": "https://minpromtorg.gov.ru/press-centre/news/",
        "lang": "ru",
        "timeout": 8,
        "mode": "list",
        "title_selector": "a[href*='/press-centre/news/']",
        "link_regex": r"/press-centre/news/[0-9a-f-]{10,}$",
        # "19.10.2026 Заголовок" -> "Заголовок"
        "title_strip_regex": r"^\d{2}\.\d{2}\.\d{4}\s+",
        "require_keyword": True,
        "strong": True,
    },

    # Деловые RSS: фильтруются по ключевым словам отрасли.
    # Общие ленты дают шум, поэтому берём только экономические/сырьевые
    # и держим список ключевых слов строго отраслевым.
    "vedomosti": {
        "name": "Ведомости",
        "url": "https://www.vedomosti.ru/rss/news",
        "lang": "ru",
        "strong": True,
    },
    "interfax": {
        "name": "Интерфакс",
        "url": "https://www.interfax.ru/rss.asp",
        "lang": "ru",
        "strong": True,
    },
    "kommersant_economics": {
        "name": "Коммерсантъ",
        "url": "https://www.kommersant.ru/RSS/section-economics.xml",
        "lang": "ru",
        "strong": True,
    },
    "gmk_center": {
        "name": "GMK Center",
        "url": "https://gmk.center/feed/",
        "lang": "ru",
        "require_keyword": True,
        "require_geo": True,
    },
    # Казахстан: деловая лента, берём только отраслевые материалы.
    "kursiv_kz": {
        "name": "Kursiv.kz",
        "url": "https://kursiv.kz/rss",
        "lang": "ru",
        "require_keyword": True,
        "strong": True,
    },
}

THEMES = {
    "ai": {
        "sources": NEWS_SOURCES_AI,
        "hashtags": ["#ИИ", "#AI", "#Новости", "#Технологии", "#ИскусственныйИнтеллект"],
        "brand": "AINOVOSTI.RU",
        "image_queries": ["artificial intelligence", "data center", "technology"],
        "keywords": [
            "ai", "artificial intelligence", "machine learning", "deep learning",
            "neural network", "llm", "gpt", "openai", "anthropic", "gemini",
            "chatgpt", "claude", "robot", "robotics", "automation",
            "ии", "искусственный интеллект", "нейросеть", "робот",
            "робототехника", "машинное обучение", "гпт",
        ],
    },
    "facts": {
        "sources": NEWS_SOURCES_FACTS,
        "hashtags": ["#Факты", "#История", "#Астрономия", "#Наука", "#Цитаты", "#Познавательно", "#Открытия"],
        "brand": "FACTUM.RU",
        "keywords": [
            "history", "historical", "ancient", "discovery", "invention",
            "nasa", "space", "planet", "star", "galaxy", "astronomy",
            "quote", "philosophy", "wisdom", "fact", "universe",
            "evolution", "archaeology", "paleontology", "dinosaur",
            "physics", "biology", "chemistry", "psychology",
            "science", "research", "study", "scientist", "explore",
            "история", "факт", "открытие", "древний", "изобретение",
            "космос", "звезда", "планета", "галактика", "астрономия",
            "цитата", "философия", "мудрость", "наука", "ученый",
            "вселенная", "солнце", "луна", "марс", "земля",
            "эволюция", "археология", "палеонтология", "динозавр",
            "физика", "биология", "химия", "психология",
            "исследование", "эксперимент", "технология", "природа",
            "идея", "мысль", "гениально", "интересно", "удивительно",
        ],
    },
    "beauty": {
        "sources": NEWS_SOURCES_BEAUTY,
        "hashtags": [
            "#Косметология", "#Омоложение", "#Долголетие", "#Здоровье",
            "#Кожа", "#Антиэйджинг", "#Наука", "#Красота",
        ],
        "brand": "AESTHETIC.RU",
        "image_queries": ["skincare", "cosmetics laboratory", "wellness"],
        "keywords": [
            # косметология и дерматология
            "cosmetic", "dermatolog", "skin", "skin barrier", "wrinkle",
            "collagen", "retinol", "retinoid", "botox", "filler",
            "hyaluronic", "peptide", "sunscreen", "spf", "photoaging",
            "biostimulator", "mesotherapy", "prp", "acne", "psoriasis",
            "eczema", "melanoma", "hair loss", "alopecia", "pigment",
            # омоложение и долголетие
            "aging", "ageing", "longevity", "senolytic", "anti-aging",
            "telomere", "cellular", "regenerat", "stem cell", "epigenetic",
            "mitochondri", "metabolic", "microbiome", "inflammation",
            "antioxidant", "healthspan", "biological age",
            # русский
            "косметолог", "дерматолог", "омоложен", "долголет", "старени",
            "кожа", "морщин", "коллаген", "ретинол", "гиалурон",
            "антиоксид", "регенерац", "стелл", "здоровье",
        ],
    },
    "metal": {
        "sources": NEWS_SOURCES_METAL,
        "hashtags": [
            "#Металлопрокат", "#Трубы", "#Сталь", "#Прокат",
            "#Металлургия", "#ЧерныеМеталлы", "#Промышленность",
        ],
        "brand": "NOVOSTI TRUBY METALL",
        "stem": 7,
        "geo_filter": True,
        "image_queries": [
            "steel pipes",
            "metallurgy plant",
            "steel rolling mill",
            "scrap metal yard",
        ],
        "palette": {
            "bg_top": (28, 33, 41),
            "bg_bottom": (12, 14, 18),
            "accent": (255, 176, 46),
            "brand": (148, 156, 168),
            "hex_grid": False,
        },
        "keywords": [
            # Ключи намеренно строгие: общие слова ("экспорт", "лист",
            # "строительство") в общих новостных лентах тянут за собой
            # пожары, iPhone и магнитные бури, а не металлургию.
            # трубы и трубный прокат
            "труб", "трубопровод", "бесшов", "сварн", "муфт", "флан",
            "фитин", "тройник", "катанк",
            # сталь и прокат
            "стал", "прокат", "сортовой", "рулон", "арматур", "оцинков",
            "нержаве", "швеллер", "двутавр", "листовой", "рифлен",
            # металлургия и сырьё
            "металл", "металлург", "чугун", "домен", "выплавк",
            "ферросплав", "руда", "кокс",
            # цветные металлы
            "медь", "цинк", "никел", "алюмин", "свинец",
            # инфраструктура и энергетика (потребление проката)
            "нефт", "газопровод", "скважин", "резервуар", "компрессор",
            # экспорт / таможня (в связке со сталью и трубами)
            "пошлин", "антидемпинг", "квот",
            # компании отрасли
            "северст", "евраз", "русал", "нлмк", "арселор", "метинвест",
            # english
            "steel", "pipe", "tube", "tubular", "metal", "alloy",
            "iron", "scrap", "coil", "rebar", "section", "hollow",
            "seamless", "welded", "aluminium", "aluminum", "billet", "slab",
        ],
        # Строгий набор для общих деловых лент (Ведомости, Интерфакс,
        # Коммерсантъ). "стал" там ловит "стало любопытство", поэтому в
        # строгом списке только однозначные отраслевые корни.
        "strong_keywords": [
            "металлург", "металлопрокат", "металлообработ", "металлолом",
            "трубопрокат", "трубопровод", "трубн", "труб", "газопровод",
            "чугун", "доменн", "выплавк", "ферросплав", "рудн", "кокс",
            "прокатн", "сортамент", "арматур",
            "нержаве", "оцинков", "алюмин", "цинк", "никел", "медн",
            "пошлин", "антидемпинг", "квот", "стальн", "сталь", "сталей",
            "сталелитей", "горнорудн", "горнометаллург", "комбинат",
            "северстал", "евраз", "русал", "нлмк", "ммк", "тмк", "омк",
            "пмх", "мечел", "норильск", "металлоинвест", "русская сталь",
        ],
    },
}

_theme_config = THEMES.get(THEME, THEMES["ai"])
NEWS_SOURCES = _theme_config["sources"]
HASHTAGS = _theme_config["hashtags"]
KEYWORDS = _theme_config["keywords"]
STRONG_KEYWORDS = _theme_config.get("strong_keywords") or KEYWORDS
# Длина стемма для поиска по ключевым словам. 4 - как раньше, 6 - строже
# для отраслей, где 4-символьные стеммы дают ложные срабатывания.
STEM_LEN = _theme_config.get("stem", 4)
GEO_FILTER = _theme_config.get("geo_filter", False)
PALETTE = _theme_config.get("palette")
# Английские запросы для стоковых фото. Нужны, когда из заголовка не
# вытащить ни одного отраслевого слова: без них Pexels искал по случайному
# глаголу и присылал кофе, закаты и собак.
IMAGE_QUERIES = _theme_config.get("image_queries") or ["industry", "technology"]
if not BRAND_NAME:
    BRAND_NAME = _theme_config["brand"]
