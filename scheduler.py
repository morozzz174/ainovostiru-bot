import asyncio
import logging
import random
from collections import defaultdict
from datetime import datetime, timedelta

from telegram import Bot
from telegram.error import InvalidToken

import config
from collector import collect_news, enrich_description, Article
from publisher import prepare_post, send_post
from storage import Storage
from translator import translate_article

logger = logging.getLogger(__name__)


def create_bot(token: str) -> Bot:
    """Build a Bot, routing through TELEGRAM_PROXY when one is configured."""
    if not config.TELEGRAM_PROXY:
        return Bot(token=token)
    from telegram.request import HTTPXRequest

    request = HTTPXRequest(
        proxy=config.TELEGRAM_PROXY,
        connect_timeout=config.TG_CONNECT_TIMEOUT,
        read_timeout=config.TG_READ_TIMEOUT,
        write_timeout=config.TG_READ_TIMEOUT,
        pool_timeout=config.TG_CONNECT_TIMEOUT,
    )
    logger.info("Telegram proxy: %s", config.TELEGRAM_PROXY)
    return Bot(token=token, request=request)


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
    """Round-robin across sources so a single busy feed cannot fill the run.

    Paywalled feeds only give a headline, so stories that come with a teaser
    are drawn first; bare headlines are kept as a fallback when a run has
    nothing else, not as the default post.
    """
    by_source = defaultdict(list)
    for art in new_articles:
        by_source[art.source].append(art)

    sources = list(by_source.keys())
    random.shuffle(sources)
    for bucket in by_source.values():
        random.shuffle(bucket)
        bucket.sort(
            key=lambda a: len((a.description or "").strip()) >= 120,
            reverse=True,
        )

    picked: list[Article] = []
    for minimum in (120, 0):
        while len(picked) < count:
            advanced = False
            for source in list(sources):
                bucket = by_source[source]
                while bucket and len((bucket[0].description or "").strip()) < minimum:
                    bucket.pop(0)
                if bucket:
                    picked.append(bucket.pop(0))
                    advanced = True
                    if len(picked) >= count:
                        break
            if not advanced:
                break
    return picked


def _queue_to_dzen(article: Article, image_buf) -> None:
    if not config.DZEN_ENABLED:
        return
    try:
        from dzen_feed import add_article

        add_article(article, image_buf)
    except Exception as e:
        logger.error("Dzen: queue failed: %s", e)


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

            # A headline alone says little, so pull the opening sentences from
            # the article page when the feed did not carry a teaser.
            enriched = enrich_description(article)
            if enriched != article.description:
                logger.info("Expanded description: %d chars", len(enriched))
                article.description = enriched

            if article.lang == "en":
                title_ru, desc_ru = translate_article(article.title, article.description)
                # A Russian channel should never carry raw English text. If every
                # translator is rate limited, translate_article hands the original
                # back unchanged, so drop the article instead of posting it.
                if title_ru.strip() == article.title.strip():
                    logger.info("Skipped, translation unavailable: %s", article.title[:60])
                    continue
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
            _queue_to_dzen(article, image_buf)

            if posted < config.MAX_POSTS_PER_RUN:
                await asyncio.sleep(config.POST_DELAY_SECONDS)
        except Exception as e:
            failed += 1
            logger.error("Error posting article %s: %s", article.url, e)

    if skipped_story:
        logger.info("Skipped %d stories already covered", skipped_story)
    logger.info("=== Collection finished: posted %d/%d, failed %d ===", posted, config.MAX_POSTS_PER_RUN, failed)
    return {"collected": len(all_articles), "new": len(new_articles), "posted": posted, "failed": failed}


def _local_now() -> datetime:
    """Current time in POST_TIMEZONE, or machine-local time when unset."""
    if config.POST_TIMEZONE:
        try:
            from zoneinfo import ZoneInfo

            return datetime.now(ZoneInfo(config.POST_TIMEZONE))
        except Exception as e:
            logger.warning(
                "Bad POST_TIMEZONE %r (%s), using local time",
                config.POST_TIMEZONE,
                e,
            )
    return datetime.now()


def _slot_times() -> list[float]:
    """Evenly spaced posting hours inside the window, as decimal hours."""
    start = config.POSTING_START_HOUR
    end = config.POSTING_END_HOUR
    count = max(config.POSTS_PER_DAY, 1)
    span = max(end - start, 1)
    return [start + span * i / count for i in range(count)]


def _at_hour(day: datetime, hour: float) -> datetime:
    whole = int(hour)
    minutes = int(round((hour - whole) * 60))
    if minutes >= 60:
        whole += 1
        minutes -= 60
    return day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        hours=whole, minutes=minutes
    )


def next_slot(now: datetime) -> datetime:
    """Next posting time strictly after ``now``."""
    for hour in _slot_times():
        candidate = _at_hour(now, hour)
        if candidate > now:
            return candidate
    return _at_hour(now + timedelta(days=1), _slot_times()[0])


async def scheduler_loop(bot: Bot, storage: Storage):
    if config.POSTS_PER_DAY > 0:
        logger.info(
            "Scheduler started. %d posts/day between %02d:00 and %02d:00 (%s)",
            config.POSTS_PER_DAY,
            config.POSTING_START_HOUR,
            config.POSTING_END_HOUR,
            config.POST_TIMEZONE or "local time",
        )
        while True:
            now = _local_now()
            target = next_slot(now)
            wait = max((target - now).total_seconds(), 0)
            logger.info(
                "Next post at %s (in %.1f h)",
                target.strftime("%d.%m.%Y %H:%M"),
                wait / 3600,
            )
            await asyncio.sleep(wait)
            try:
                await run_once(bot, storage)
            except Exception as e:
                logger.exception("Scheduler error: %s", e)
        return

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
        bot = create_bot(bot_token)
        me = await bot.get_me()
        logger.info("Bot authorized: @%s", me.username)
    except InvalidToken:
        logger.error("Invalid BOT_TOKEN. Check your .env file")
        return
    except Exception as e:
        logger.error("Cannot reach Telegram API: %s", e)
        logger.error("If the network blocks Telegram, set TELEGRAM_PROXY in your .env file")
        return

    storage = Storage(config.DATABASE_PATH)
    logger.info("Database: %s (%d articles indexed)", config.DATABASE_PATH, storage.get_posted_count())

    await scheduler_loop(bot, storage)
