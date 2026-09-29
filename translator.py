import logging
import time

import requests
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

_translator = GoogleTranslator(source="en", target="ru")

MYMEMORY_API = "https://api.mymemory.translated.net/get"
USER_AGENT = "Mozilla/5.0 (compatible; AINOVOSTIRU/1.0)"

MIN_LENGTH = 10
MAX_CHUNK = 450

# Google allows about 5 requests per second. Posting a handful of articles in
# a row tripped that limit and left headlines untranslated, so pace the calls.
_REQUEST_GAP = 0.8
_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = _REQUEST_GAP - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _translate_google_batch(texts: list[str], retries: int = 2) -> list[str] | None:
    for attempt in range(retries + 1):
        try:
            _throttle()
            result = _translator.translate_batch(texts)
            if result and len(result) == len(texts):
                return [r if r and r.strip() else o for r, o in zip(result, texts)]
        except Exception as e:
            if attempt < retries:
                backoff = 2.0 * (attempt + 1)
                logger.warning("Google batch retry %d/%d in %.0fs: %s", attempt + 1, retries, backoff, e)
                time.sleep(backoff)
            else:
                logger.error("Google batch failed after %d attempts: %s", retries + 1, e)
    return None


def _translate_mymemory(text: str) -> str | None:
    if not text:
        return None
    try:
        resp = requests.get(
            MYMEMORY_API,
            params={"q": text[:MAX_CHUNK], "langpair": "en|ru"},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        translated = (resp.json().get("responseData") or {}).get("translatedText")
        if translated and translated.strip():
            return translated
    except Exception as e:
        logger.debug("MyMemory failed: %s", e)
    return None


def _translate_one(text: str) -> str:
    if not text or len(text.strip()) < MIN_LENGTH:
        return text
    batch = _translate_google_batch([text])
    if batch is not None:
        return batch[0]
    fallback = _translate_mymemory(text)
    if fallback:
        logger.info("Translated via MyMemory fallback")
        return fallback
    logger.warning("All translators failed, keeping original: %.50s...", text)
    return text


def translate_text(text: str) -> str:
    return _translate_one(text)


def translate_article(title: str, description: str) -> tuple[str, str]:
    parts = [title, description[:2000]]
    if not any(p and len(p.strip()) >= MIN_LENGTH for p in parts):
        return title, description

    batch = _translate_google_batch(parts)
    if batch is not None:
        return batch[0], batch[1]

    results = []
    for part in parts:
        results.append(_translate_mymemory(part) or part)
    if any(r != p for r, p in zip(results, parts)):
        logger.info("Translated via MyMemory fallback")
    else:
        logger.warning("Translation unavailable, posting original text")
    return results[0], results[1]
