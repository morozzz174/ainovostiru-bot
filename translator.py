import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

_translator = GoogleTranslator(source="en", target="ru")


def translate_text(text: str) -> str:
    if not text or len(text.strip()) < 10:
        return text
    try:
        result = _translator.translate(text)
        return result if result else text
    except Exception as e:
        logger.warning("Translation failed: %s", e)
        return text


def translate_article(title: str, description: str) -> tuple[str, str]:
    title_ru = translate_text(title)
    desc_ru = translate_text(description[:2000])
    return title_ru, desc_ru
