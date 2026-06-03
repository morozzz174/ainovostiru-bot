import asyncio
import logging
import sys

import config
from scheduler import run_scheduler, run_once
from storage import Storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


async def main():
    logger.info("AINOVOSTI.RU — AI News Bot")
    logger.info("Channel: %s", config.CHANNEL_ID)

    if "--once" in sys.argv:
        logger.info("Mode: single run")
        if not config.BOT_TOKEN:
            logger.error("BOT_TOKEN is not set")
            return
        from telegram import Bot
        bot = Bot(token=config.BOT_TOKEN)
        storage = Storage(config.DATABASE_PATH)
        await run_once(bot, storage)
    else:
        logger.info("Mode: scheduler (interval: %d hours)", config.SCHEDULE_INTERVAL_HOURS)
        await run_scheduler(config.BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
