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


def _post_to_tiktok(article: Article, text: str, image_buf):
    if not config.TT_ENABLED:
        return
    try:
        from tiktok_publisher import post_article
        success = post_article(text, article.title, article.description, image_buf)
        if success:
            logger.info("TikTok: posted successfully")
        else:
            logger.warning("TikTok: post failed")
    except Exception as e:
        logger.error("TikTok: error: %s", e)


def _draw_candidates(new_articles: list[Article], count: int) -> list[Article]:
    """Round-robin across sources so a single busy feed cannot fill the run."""
    by_source = defaultdict(list)
    for art in new_articles:
        by_source[art.source].append(art)

    sources = list(by_source.keys())
    random.shuffle(sources)
    for bucket in by_source.values():
        random.shuffle(bucket)

    picked: list[Article] = []
    while len(picked) < count and sources:
        for source in list(sources):
            if by_source[source]:
                picked.append(by_source[source].pop(0))
                if len(picked) >= count:
                    break
            if not by_source[source]:
                sources.remove(source)
    return picked


async def run_once(bot: Bot, storage: Storage) -> dict:
    logger.info("=== Starting news collection ===")

    all_articles = collect_news()
    if not all_articles:
        logger.warning("No articles collected")
        return {"collected": 0, "new": 0, "posted": 0}

    new_articles: list[Article] = []
    skipped_dupe = 0
    for art in all_articles:
        if storage.is_posted(art.url):
            continue
        # Same story republished under a different headline.
        if storage.is_duplicate_title(art.title):
            skipped_dupe += 1
            logger.info("Skipped as already covered: %s", art.title[:70])
            storage.mark_posted(art.url, art.title)
            continue
        new_articles.append(art)

    logger.info("New articles: %d out of %d", len(new_articles), len(all_articles))
    if skipped_dupe:
        logger.info("Skipped %d already-covered stories", skipped_dupe)

    if not new_articles:
        logger.info("No new articles to post")
        return {"collected": len(all_articles), "new": 0, "posted": 0}

    # Draw a wider pool than MAX_POSTS_PER_RUN. The duplicate-story filter is
    # worth keeping, but stopping at the first rejected article was costing a
    # post on nearly every run, so the loop now keeps drawing until the quota
    # is filled or the pool runs out.
    pool = _draw_candidates(new_articles, config.MAX_POSTS_PER_RUN * 5)

    posted = 0
    failed = 0
    skipped_story = 0
    for article in pool:
        if posted >= config.MAX_POSTS_PER_RUN:
            break
        try:
            if storage.is_duplicate_title(article.title):
                skipped_story += 1
                logger.info("Skipped, same story as an earlier post: %s", article.title[:60])
                continue

            if article.lang == "en":
                title_ru, desc_ru = translate_article(article.title, article.description)
                article.title = title_ru
                article.description = desc_ru
                article.lang = "ru"

            text, image_buf, media_type = prepare_post(article)
            sent = await send_post(bot, config.CHANNEL_ID, text, image_buf, media_type, title=article.title, source=article.source, description=article.description)
            if sent:
                posted += 1
                storage.mark_posted(article.url, article.title)
            else:
                failed += 1
                logger.error("Post NOT delivered: %s", article.url)
            _post_to_instagram(text, image_buf)
            _post_to_tiktok(article, text, image_buf)

            if posted < config.MAX_POSTS_PER_RUN:
                await asyncio.sleep(config.POST_DELAY_SECONDS)
        except Exception as e:
            failed += 1
            logger.error("Error posting article %s: %s", article.url, e)

    if skipped_story:
        logger.info("Skipped %d stories already covered", skipped_story)
    logger.info("=== Collection finished: posted %d/%d, failed %d ===", posted, config.MAX_POSTS_PER_RUN, failed)
    return {"collected": len(all_articles), "new": len(new_articles), "posted": posted, "failed": failed}


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
