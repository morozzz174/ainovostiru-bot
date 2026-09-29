import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

dotenv_path = os.getenv("DOTENV_PATH") or os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
DATABASE_PATH = os.getenv("DATABASE_PATH") or os.path.join(BASE_DIR, "bot_data.db")
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "2"))
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "3"))
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "60"))

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
VOICE_MAX_CHARS = int(os.getenv("VOICE_MAX_CHARS", "200"))
VOICE_RETRIES = int(os.getenv("VOICE_RETRIES", "3"))
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
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
        "name": "New Scientist",
        "url": "https://www.newscientist.com/feed/home",
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
}

THEMES = {
    "ai": {
        "sources": NEWS_SOURCES_AI,
        "hashtags": ["#ИИ", "#AI", "#Новости", "#Технологии", "#ИскусственныйИнтеллект"],
        "brand": "AINOVOSTI.RU",
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
            "антиоксид", "регенерац", "стелл", "восстановлен", "здоровье",
        ],
    },
}

_theme_config = THEMES.get(THEME, THEMES["ai"])
NEWS_SOURCES = _theme_config["sources"]
HASHTAGS = _theme_config["hashtags"]
KEYWORDS = _theme_config["keywords"]
if not BRAND_NAME:
    BRAND_NAME = _theme_config["brand"]
