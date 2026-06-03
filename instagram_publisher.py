import io
import json
import logging
import os
import pickle
from pathlib import Path

from instagrapi import Client
from instagrapi.exceptions import LoginRequired

import config

logger = logging.getLogger(__name__)

SESSION_FILE = Path("instagram_session.pkl")


def _get_client() -> Client | None:
    if not config.IG_USERNAME or not config.IG_PASSWORD:
        logger.warning("Instagram credentials not configured")
        return None

    cl = Client()

    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "rb") as f:
                cl.load_settings(f.read())
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)
            logger.info("Instagram: logged in via saved session")
            return cl
        except LoginRequired:
            logger.info("Instagram: session expired, re-login required")
            SESSION_FILE.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("Instagram: session load failed: %s", e)
            SESSION_FILE.unlink(missing_ok=True)

    try:
        cl.login(config.IG_USERNAME, config.IG_PASSWORD)
        with open(SESSION_FILE, "wb") as f:
            f.write(cl.get_settings())
        logger.info("Instagram: logged in and session saved")
        return cl
    except Exception as e:
        logger.error("Instagram login failed: %s", e)
        return None


def post_article(text: str, image_buf: io.BytesIO) -> bool:
    cl = _get_client()
    if not cl:
        return False

    try:
        caption = _format_caption(text)
        image_buf.seek(0)
        cl.photo_upload(image_buf, caption)
        logger.info("Instagram: post published")
        return True
    except Exception as e:
        logger.error("Instagram: post failed: %s", e)
        return False


def _format_caption(text: str) -> str:
    text = text.replace("*", "")
    lines = text.split("\n")
    clean = []
    for line in lines:
        line = line.strip()
        if line.startswith("📅 Источник:"):
            clean.append(line.replace("📅 Источник: [", "📅 Источник: ").replace("](", " (").rstrip(")"))
        else:
            clean.append(line)
    return "\n".join(clean)
