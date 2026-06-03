import logging
import time

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

_translator = GoogleTranslator(source="en", target="ru")


def translate_text(text: str, retries: int = 2) -> str:
    if not text or len(text.strip()) < 10:
        return text
    for attempt in range(retries + 1):
        try:
            result = _translator.translate(text)
            if result:
                return result
        except Exception as e:
            if attempt < retries:
                logger.warning("Translation retry %d/%d: %s", attempt + 1, retries, e)
                time.sleep(2)
            else:
                logger.error("Translation failed after %d attempts: %s", retries + 1, e)
    logger.warning("Returning original text for: %.50s...", text)
    return text


def translate_article(title: str, description: str) -> tuple[str, str]:
    title_ru = translate_text(title)
    desc_ru = translate_text(description[:2000])
    return title_ru, desc_ru
