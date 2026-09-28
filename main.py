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


async def main() -> int:
    logger.info("AINOVOSTI.RU — AI News Bot")
    logger.info("Channel: %s", config.CHANNEL_ID)

    if "--once" in sys.argv:
        logger.info("Mode: single run")
        if not config.BOT_TOKEN:
            logger.error("BOT_TOKEN is not set (checked %s)", config.dotenv_path)
            return 1
        from telegram import Bot
        bot = Bot(token=config.BOT_TOKEN)
        storage = Storage(config.DATABASE_PATH)
        result = await run_once(bot, storage)
        logger.info("SUMMARY %s", result)
        if "--strict" in sys.argv and (result["collected"] == 0 or result["posted"] == 0):
            logger.error("Strict mode: nothing posted (collected=%d, posted=%d)", result["collected"], result["posted"])
            return 1
        return 0

    logger.info("Mode: scheduler (interval: %d hours)", config.SCHEDULE_INTERVAL_HOURS)
    await run_scheduler(config.BOT_TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
