import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@ainovostiru")
DATABASE_PATH = os.getenv("DATABASE_PATH", "ainovosti.db")
MAX_POSTS_PER_RUN = int(os.getenv("MAX_POSTS_PER_RUN", "3"))
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "4"))
POST_DELAY_SECONDS = int(os.getenv("POST_DELAY_SECONDS", "60"))

NEWS_SOURCES = {
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

HASHTAGS = ["#ИИ", "#AI", "#Новости", "#Технологии", "#ИскусственныйИнтеллект"]
