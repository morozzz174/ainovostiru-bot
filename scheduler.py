import asyncio
import logging
import random
from collections import defaultdict

from telegram import Bot
from telegram.error import InvalidToken

import config
from collector import collect_news, Article
from publisher import prepare_post, send_post
from storage import Storage
from translator import translate_article

logger = logging.getLogger(__name__)


def _post_to_instagram(text: str, image_buf):
    if not config.IG_USERNAME:
        logger.info("Instagram: skipped (no credentials)")
        return
    try:
        from instagram_publisher import post_article
        success = post_article(text, image_buf)
        if success:
            logger.info("Instagram: posted successfully")
        else:
            logger.warning("Instagram: post failed")
    except Exception as e:
        logger.error("Instagram: error: %s", e)


async def run_once(bot: Bot, storage: Storage):
    logger.info("=== Starting news collection ===")

    all_articles = collect_news()
    if not all_articles:
        logger.warning("No articles collected")
        return

    new_articles: list[Article] = []
    for art in all_articles:
        if not storage.is_posted(art.url):
            new_articles.append(art)

    logger.info("New articles: %d out of %d", len(new_articles), len(all_articles))

    if not new_articles:
        logger.info("No new articles to post")
        return

    random.shuffle(new_articles)

    by_source = defaultdict(list)
    for art in new_articles:
        by_source[art.source].append(art)

    sources = list(by_source.keys())
    random.shuffle(sources)

    selected = []
    used_sources = set()
    while len(selected) < config.MAX_POSTS_PER_RUN and sources:
        next_sources = [s for s in sources if s not in used_sources] or sources
        src = random.choice(next_sources)
        if by_source[src]:
            selected.append(by_source[src].pop(0))
            used_sources.add(src)
        if not by_source[src]:
            sources.remove(src)
        if len(used_sources) >= len(sources):
            used_sources.clear()

    for i, article in enumerate(selected):
        try:
            if article.lang == "en":
                title_ru, desc_ru = translate_article(article.title, article.description)
                article.title = title_ru
                article.description = desc_ru
                article.lang = "ru"

            text, image_buf, media_type = prepare_post(article)
            await send_post(bot, config.CHANNEL_ID, text, image_buf, media_type, title=article.title, source=article.source)
            _post_to_instagram(text, image_buf)
            storage.mark_posted(article.url, article.title)

            if i < len(selected) - 1:
                await asyncio.sleep(config.POST_DELAY_SECONDS)
        except Exception as e:
            logger.error("Error posting article %s: %s", article.url, e)

    logger.info("=== Collection finished ===")


async def scheduler_loop(bot: Bot, storage: Storage):
    logger.info(
        "Scheduler started. Interval: %d hours",
        config.SCHEDULE_INTERVAL_HOURS,
    )
    while True:
        try:
            await run_once(bot, storage)
        except Exception as e:
            logger.exception("Scheduler error: %s", e)
        await asyncio.sleep(config.SCHEDULE_INTERVAL_HOURS * 3600)


async def run_scheduler(bot_token: str):
    if not bot_token:
        logger.error("BOT_TOKEN is not set. Create .env file from .env.example")
        return

    try:
        bot = Bot(token=bot_token)
        me = await bot.get_me()
        logger.info("Bot authorized: @%s", me.username)
    except InvalidToken:
        logger.error("Invalid BOT_TOKEN. Check your .env file")
        return

    storage = Storage(config.DATABASE_PATH)
    logger.info("Database: %s (%d articles indexed)", config.DATABASE_PATH, storage.get_posted_count())

    await scheduler_loop(bot, storage)
