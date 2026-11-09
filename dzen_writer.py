"""Long-form articles for the Dzen RSS feed.

Telegram gets a short news card; Dzen needs a real article people read for
several minutes, otherwise the platform never counts the engaged reading time
required for monetisation. This module turns a collected headline + teaser
into a structured Russian article with an LLM and renders it as clean HTML
plus a couple of branded quote cards.

The LLM client is OpenAI-compatible on purpose: DeepSeek, OpenRouter and
OpenAI differ only by base URL and model name.
"""

import html
import io
import json
import logging
import os
import re

import requests
from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)

CARD_W, CARD_H = 1200, 800
BEAUTY_BG_TOP = (251, 247, 244)
BEAUTY_BG_BOTTOM = (243, 227, 230)
BEAUTY_ACCENT = (201, 106, 122)
BEAUTY_ACCENT_ALT = (166, 120, 136)
BEAUTY_TEXT = (46, 38, 40)
BEAUTY_MUTED = (126, 108, 112)

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | None] = {}


def _font(size: int, bold: bool = False):
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = []
    if bold:
        candidates += [
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
        ]
    else:
        candidates += [
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSans-Regular.ttf",
        ]
    font = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
    _FONT_CACHE[key] = font
    return font


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]):
    width, height = size
    image = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        colour = tuple(int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=colour)
    return image


def _clean_quote(text: str, limit: int = 170) -> str:
    if not isinstance(text, str):
        return ""
    text = re.sub(r"[*_`#]+", "", text or "")
    text = re.sub(r"\s+", " ", text).strip().strip("«»\"'")
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(".,;:") + "…"


def make_quote_card(text: str, index: int = 0) -> bytes:
    """Render one branded 1200x800 quote card as JPEG."""
    image = _gradient((CARD_W, CARD_H), BEAUTY_BG_TOP, BEAUTY_BG_BOTTOM)
    draw = ImageDraw.Draw(image)
    accent = BEAUTY_ACCENT if index % 2 == 0 else BEAUTY_ACCENT_ALT

    draw.rectangle([0, 0, 11, CARD_H], fill=accent)
    draw.ellipse([CARD_W - 260, -120, CARD_W + 120, 260], fill=(255, 255, 255))
    draw.ellipse([-90, CARD_H - 210, 210, CARD_H + 90], fill=(255, 255, 255))

    brand_font = _font(26, bold=True)
    quote_font = _font(54, bold=True)
    caption_font = _font(24)

    draw.text((72, 58), "КОСМОББ", font=brand_font, fill=accent)

    quote = _clean_quote(text)
    lines = _wrap(draw, quote, quote_font, CARD_W - 150)
    if len(lines) > 7:
        lines = lines[:7]
        lines[-1] = lines[-1].rstrip(".,;:") + "…"
    line_height = 72
    block_height = len(lines) * line_height
    y = max(190, (CARD_H - block_height) // 2 - 10)
    for line in lines:
        draw.text((72, y), line, font=quote_font, fill=BEAUTY_TEXT)
        y += line_height

    draw.line([(72, CARD_H - 104), (CARD_W - 72, CARD_H - 104)], fill=(226, 204, 208), width=2)
    draw.text(
        (72, CARD_H - 78),
        "Косметология и уход · без обещаний и волшебных кремов",
        font=caption_font,
        fill=BEAUTY_MUTED,
    )

    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return buf.getvalue()


SYSTEM_PROMPT = (
    "Ты редактор русскоязычного канала о доказательной косметологии и уходе за кожей. "
    "Пиши спокойно, по делу, без сенсаций, без обещаний «вечной молодости» и без "
    "медицинских гарантий. Не выдумывай исследования, цены, сроки, проценты, цифры "
    "и названия препаратов: если данных нет в исходнике, объясняй общий принцип без "
    "конкретных чисел. Не путай процедуры: криолиполиз — это охлаждение жировой "
    "складки, LPG — вакуумно-роликовый массаж, а не холодовая процедура. Не копируй "
    "исходный текст дословно. Верни только валидный JSON без markdown."
)

USER_PROMPT = """Сделай из этой новости полноценную статью для Дзена.

Заголовок: {title}
Краткое описание: {description}
Источник: {source}

Исходный текст (может быть на английском, может быть неполным):
{source_text}

Требования:
- Объём основного текста — не менее 4500 символов (примерно 700–900 слов).
- Заголовок до 90 символов, конкретный, без кликбейта.
- Лид: 2–3 предложения, сразу объясняет, о чём речь и почему это важно.
- 3–4 раздела с подзаголовками. В каждом ровно 2 отдельных абзаца, не объединяй их.
- Каждый абзац — 300–500 символов. Если текст получается короче 4500 символов,
  добавь по одному абзацу в каждый раздел.
- Пиши литературным русским языком, без английских слов, кальки и канцелярита.
- Проверяй грамматику, падежи и согласование.
- В конце — блок «Коротко» (2–3 предложения) и вопрос читателям для комментариев.
- 2 короткие цитаты для карточек (до 140 символов каждая), по смыслу из статьи.
- Тон: доказательная косметология, уход, кожа, процедуры. Без диагнозов и назначений.
- Опирайся на факты из исходного текста. Не добавляй цены, стоимость, проценты,
  сроки сохранения результата, число сеансов и статистику, которых там нет.
- Если исходный текст короткий или недоступен, пиши общие принципы и вопросы,
  которые стоит задать специалисту, без конкретных цифр и обещаний.
- Никаких «сжигает жир», «выводит токсины», «запускает молодость».
- Не добавляй ссылки, списки и markdown.

Верни JSON строго такой структуры:
{{
  "title": "...",
  "lead": "...",
  "sections": [
    {{"heading": "...", "paragraphs": ["...", "..."]}},
    {{"heading": "...", "paragraphs": ["...", "..."]}},
    {{"heading": "...", "paragraphs": ["...", "..."]}}
  ],
  "takeaway": "...",
  "question": "...",
  "quotes": ["...", "..."]
}}"""

EXTEND_PROMPT = """Статья для Дзена уже написана, но ей не хватает объёма.

Заголовок статьи: {title}
Уже есть разделы: {headings}

Напиши ещё один раздел на практическую тему, которой в статье ещё нет.
Требования:
- Заголовок до 80 символов, без кликбейта.
- Ровно 2 абзаца по 400–600 символов, всего 900–1200 символов.
- Опирайся на исходный текст: объясняй, что обсудить со специалистом,
  как подготовиться, кому процедура не подходит, от чего зависит результат.
- Не добавляй цены, проценты, сроки, число сеансов и статистику, которых нет в исходнике.
- Не повторяй уже существующие разделы. Без markdown и ссылок.

Исходный текст:
{source_text}

Верни только JSON:
{{"heading": "...", "paragraphs": ["...", "..."]}}"""

PROOFREAD_PROMPT = """Проверь русский текст статьи и исправь только орфографию,
опечатки, падежи и согласование. Не меняй факты, структуру, заголовки и смысл.
Не добавляй и не убирай числа, цены, сроки, проценты и названия процедур.
Убери случайные латинские и другие иностранные вставки внутри русских слов.
Верни только исправленный JSON той же структуры, без markdown и пояснений.

Статья:
{article}"""


def _chat(messages: list[dict], max_tokens: int = 5000) -> str | None:
    if not config.LLM_API_KEY:
        return None
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in config.LLM_BASE_URL:
        # Optional attribution headers OpenRouter uses for rate-limit ranking.
        headers["HTTP-Referer"] = "https://morozzz174.github.io/ainovostiru-bot/"
        headers["X-Title"] = "Cosmobb Dzen"
    url = f"{config.LLM_BASE_URL}/chat/completions"
    for attempt in (1, 2):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=config.LLM_TIMEOUT)
            if resp.status_code == 400 and "response_format" in payload:
                # Some OpenAI-compatible gateways do not support JSON mode.
                payload.pop("response_format", None)
                continue
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            finish = choice.get("finish_reason")
            if finish == "length":
                logger.warning("Dzen LLM response hit max_tokens and was truncated")
            logger.info("Dzen LLM: %d chars, finish=%s", len(content), finish)
            return content
        except Exception as e:
            logger.warning("Dzen LLM attempt %d failed: %s", attempt, e)
            if attempt == 2:
                return None
    return None


def _parse_json(content: str | None) -> dict | None:
    if not content:
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError as e:
        logger.warning("Dzen LLM returned invalid JSON: %s", e)
        return None


def _draft_text(draft: dict) -> str:
    """All prose of a raw (possibly malformed) draft as plain text."""
    parts: list[str] = []
    for key in ("title", "lead", "takeaway", "question"):
        value = draft.get(key)
        if isinstance(value, str):
            parts.append(value)
    sections = draft.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = section.get("heading")
            if isinstance(heading, str):
                parts.append(heading)
            paragraphs = section.get("paragraphs")
            if isinstance(paragraphs, list):
                parts.extend(p for p in paragraphs if isinstance(p, str))
    quotes = draft.get("quotes")
    if isinstance(quotes, list):
        parts.extend(q for q in quotes if isinstance(q, str))
    return " ".join(parts)


_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_FOREIGN_SCRIPT_RE = re.compile(
    r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F"
    r"\u0E00-\u0E7F\u3040-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]"
)


def _bad_language(text: str) -> bool:
    """True when Russian text is corrupted with mixed alphabets or scripts.

    Small free models occasionally glue Latin or Arabic fragments into Russian
    words ("постинflammatory", "фотоoproteкция", "النمшей"). That reads as
    machine garbage and must never reach Dzen, so it is rejected and the
    article is regenerated.
    """
    if not text:
        return False
    if _FOREIGN_SCRIPT_RE.search(text):
        return True
    for word in re.findall(r"[A-Za-zА-Яа-яЁё]+", text):
        if _CYRILLIC_RE.search(word) and _LATIN_RE.search(word):
            return True
    return False


def _text_len(draft: dict) -> int:
    parts = [draft.get("lead") if isinstance(draft.get("lead"), str) else ""]
    sections = draft.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            paragraphs = section.get("paragraphs")
            if isinstance(paragraphs, list):
                parts.extend(p for p in paragraphs if isinstance(p, str))
    parts.append(draft.get("takeaway") if isinstance(draft.get("takeaway"), str) else "")
    return len(re.sub(r"\s+", " ", " ".join(parts)))


_PRICE_RE = re.compile(
    r"\d[\d\s.,]*\s*(?:₽|руб(?:\.|лей|ля|ль)?|доллар(?:ов|а)?|евро|\$|€)",
    re.I,
)
_PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*%")
_SPF_RE = re.compile(r"\bspf\s*\d{1,3}\+?", re.I)
_PA_RE = re.compile(r"\bpa\+{2,}", re.I)
_TIMEFRAME_RE = re.compile(
    r"\d+\s*(?:[–-]\s*\d+\s*)?(?:недел|месяц|сеанс|процедур|курс)",
    re.I,
)
_BANNED_PHRASES = (
    "сжигает жир",
    "сжигание жира",
    "убивает жир",
    "убийство жира",
    "выводит токсины",
    "выведение токсинов",
    "запускает молодость",
    "вечная молодость",
)


def _unsupported_specifics(text: str, source_text: str) -> bool:
    """True when the draft invents prices/percentages or uses beauty clichés.

    The model is told to avoid concrete numbers unless the source has them, but
    instructions alone are not enough: a fabricated course price is a real
    credibility risk for a medical-adjacent channel. Prices and percentages
    are cheap to check, so they are rejected outright unless the source text
    contains the same token.
    """
    lowered = text.lower().replace("ё", "е")
    source = (source_text or "").lower().replace("ё", "е")
    if any(phrase in lowered for phrase in _BANNED_PHRASES):
        return True
    for regex in (_PRICE_RE, _PERCENT_RE):
        for match in regex.finditer(lowered):
            if match.group(0).strip() not in source:
                return True
    for regex in (_SPF_RE, _PA_RE, _TIMEFRAME_RE):
        for match in regex.finditer(lowered):
            token = re.sub(r"\s+", " ", match.group(0)).strip()
            if token not in re.sub(r"\s+", " ", source):
                return True
    return False


def _structure(draft: dict) -> dict | None:
    """Clean a raw draft into a well-formed article, ignoring its length."""
    if not isinstance(draft, dict):
        return None
    title = _clean_quote(draft.get("title", ""), 120).rstrip(" .,:;—–-")
    lead = _clean_quote(draft.get("lead", ""), 700)
    sections = []
    for section in draft.get("sections") or []:
        if not isinstance(section, dict):
            continue
        heading = _clean_quote(section.get("heading", ""), 100).rstrip(" .,:;—–-")
        paragraphs = [
            _clean_quote(p, 1200)
            for p in section.get("paragraphs") or []
            if isinstance(p, str) and len(p.strip()) >= 40
        ]
        if heading and paragraphs:
            sections.append({"heading": heading, "paragraphs": paragraphs})
    takeaway = _clean_quote(draft.get("takeaway", ""), 500)
    question = _clean_quote(draft.get("question", ""), 300)
    quotes = [
        _clean_quote(q, 170)
        for q in draft.get("quotes") or []
        if isinstance(q, str) and len(q.strip()) >= 20
    ]
    # Models sometimes forget the quote cards. Pull the first sentence of a
    # section instead of shipping an article with one lonely image.
    if len(quotes) < 2:
        for section in sections:
            for paragraph in section["paragraphs"]:
                sentence = re.split(r"(?<=[.!?])\s+", paragraph)[0].strip()
                if 40 <= len(sentence) <= 170 and sentence not in quotes:
                    quotes.append(sentence)
                if len(quotes) >= 2:
                    break
            if len(quotes) >= 2:
                break
    if not title or len(lead) < 80 or len(sections) < 2 or not takeaway or not question:
        logger.info(
            "Dzen LLM validation failed: title=%s lead=%d sections=%d takeaway=%s question=%s",
            bool(title), len(lead), len(sections), bool(takeaway), bool(question),
        )
        return None
    return {
        "title": title,
        "lead": lead,
        "sections": sections,
        "takeaway": takeaway,
        "question": question,
        "quotes": quotes,
    }


def _finish(clean: dict, source_text: str = "") -> dict | None:
    """Accept a well-formed draft only if it is long and factually safe."""
    prose = _draft_text(clean)
    if _bad_language(prose):
        logger.info("Dzen LLM article contains mixed alphabets or foreign characters")
        return None
    total = _text_len(clean)
    if total < config.DZEN_ARTICLE_MIN_CHARS or total > config.DZEN_ARTICLE_MAX_CHARS:
        logger.info(
            "Dzen LLM article length %d outside %d..%d",
            total, config.DZEN_ARTICLE_MIN_CHARS, config.DZEN_ARTICLE_MAX_CHARS,
        )
        return None
    if _unsupported_specifics(prose, source_text):
        logger.info("Dzen LLM article contains unsupported prices, percentages or clichés")
        return None
    return clean


def _validate(draft: dict, source_text: str = "") -> dict | None:
    clean = _structure(draft)
    return _finish(clean, source_text) if clean else None


def _extend_article(
    title: str,
    source_text: str,
    clean: dict,
) -> dict | None:
    """Write one extra section instead of asking the model to stretch everything.

    Small free models tend to ignore "make it longer" and keep returning
    ~3000 characters. Asking for a single fresh section with a concrete
    practical angle is a much more reliable way to reach the length Dzen
    rewards, and it costs one request.
    """
    headings = ", ".join(section["heading"] for section in clean["sections"])
    prompt = EXTEND_PROMPT.format(
        title=clean["title"] or title,
        headings=headings,
        source_text=(source_text or "недоступен").strip()[:6000],
    )
    content = _chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])
    draft = _parse_json(content)
    if not draft or not isinstance(draft, dict):
        return None
    heading = _clean_quote(draft.get("heading", ""), 100).rstrip(" .,:;—–-")
    paragraphs = [
        _clean_quote(p, 1200)
        for p in draft.get("paragraphs") or []
        if isinstance(p, str) and len(p.strip()) >= 40
    ]
    if not heading or len(paragraphs) < 2:
        return None
    if _bad_language(" ".join(paragraphs) + " " + heading):
        logger.info("Dzen LLM extension contains mixed alphabets, skipping")
        return None
    lowered = heading.lower()
    if any(lowered == section["heading"].lower() for section in clean["sections"]):
        return None
    if _unsupported_specifics(" ".join(paragraphs), source_text):
        logger.info("Dzen LLM extension contains unsupported specifics, skipping")
        return None
    extended = dict(clean)
    extended["sections"] = clean["sections"] + [{
        "heading": heading,
        "paragraphs": paragraphs,
    }]
    return extended


def _proofread(clean: dict, source_text: str) -> dict | None:
    """Fix typos and grammar without changing facts, structure or length.

    A small model can write a decent article and still leave "защищает коже"
    or "дермальный мелазма". This pass is optional: on any validation failure
    the caller keeps the original draft, so it can never make the article
    unpublishable.
    """
    content = _chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PROOFREAD_PROMPT.format(
                article=json.dumps(clean, ensure_ascii=False)
            ),
        },
    ])
    draft = _parse_json(content)
    if not draft:
        return None
    fixed = _structure(draft)
    if not fixed:
        return None
    fixed = _finish(fixed, source_text)
    if not fixed:
        return None
    if _text_len(fixed) < int(_text_len(clean) * 0.9):
        logger.info("Dzen LLM proofread shrank the article too much, keeping the draft")
        return None
    return fixed


def generate_article(
    title: str,
    description: str,
    source: str,
    source_text: str = "",
) -> dict | None:
    """Return a validated long-form draft, or None when the LLM is unavailable."""
    if not config.LLM_API_KEY:
        logger.info("Dzen LLM: no LLM_API_KEY, keeping the short teaser")
        return None
    prompt = USER_PROMPT.format(
        title=title,
        description=description or title,
        source=source,
        source_text=(source_text or "недоступен").strip()[:8000],
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    # The headline and teaser are legitimate sources too: a survey story says
    # "74%" in the title while the page spells out "seventy-four percent".
    allowed_source = f"{title}\n{description}\n{source_text}"
    last_good: dict | None = None
    for attempt in (1, 2, 3):
        content = _chat(messages)
        if not content:
            if attempt < 3:
                messages.append({
                    "role": "user",
                    "content": "Ответ не пришёл. Повтори генерацию и верни только JSON.",
                })
            continue
        draft = _parse_json(content)
        if draft:
            structured = _structure(draft)
            if structured:
                last_good = structured
                clean = _finish(structured, allowed_source)
                if clean:
                    return _proofread(clean, allowed_source) or clean
            total = _text_len(draft)
            all_text = _draft_text(draft)
            if structured and _bad_language(all_text):
                instruction = (
                    "В тексте есть слова со смешанной кириллицей и латиницей, "
                    "посторонние символы или иностранные вставки. Перепиши весь "
                    "текст чистым русским языком, без латинских и арабских "
                    "фрагментов внутри русских слов. Верни только тот же JSON."
                )
            elif structured and total < config.DZEN_ARTICLE_MIN_CHARS:
                # The tiny model keeps ignoring "make it longer", so stop
                # retrying the same prompt and extend the article separately.
                break
            elif _unsupported_specifics(all_text, allowed_source):
                instruction = (
                    "Убери из статьи цены, проценты, сроки и обещания, которых нет "
                    "в исходнике, а также штампы вроде «сжигает жир» и «выводит "
                    "токсины». Смысл и структуру сохрани. Верни только тот же JSON."
                )
            else:
                instruction = (
                    "Статья неполная: заполни заголовок, лид, 3–4 раздела с двумя "
                    "абзацами, блок «Коротко», вопрос читателям и две цитаты. "
                    "Верни только тот же JSON."
                )
        else:
            instruction = (
                "Предыдущий ответ — невалидный JSON. Верни только исправленный JSON "
                "той же структуры, без markdown и пояснений. Не сокращай текст."
            )
        if attempt < 3:
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": instruction})

    # A short but well-formed article is easier to rescue with one extra
    # section than with another round of "please expand" (which the small
    # free models routinely ignore).
    if (
        last_good
        and not _bad_language(_draft_text(last_good))
        and not _unsupported_specifics(_draft_text(last_good), allowed_source)
    ):
        for _ in range(2):
            if _text_len(last_good) >= config.DZEN_ARTICLE_MIN_CHARS:
                break
            extended = _extend_article(title, allowed_source, last_good)
            if not extended:
                break
            last_good = extended
        clean = _finish(last_good, allowed_source)
        if clean:
            return _proofread(clean, allowed_source) or clean
    logger.warning("Dzen LLM: could not produce a long article for %r", title[:80])
    return None


def _paragraphs_html(paragraphs: list[str]) -> str:
    return "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip())


def render_body(draft: dict, image_urls: list[str], source_url: str, source: str) -> str:
    """Render the draft as semantic HTML for content:encoded."""
    parts = [f'<p class="lead">{html.escape(draft["lead"])}</p>']
    extra_images = image_urls[1:]
    image_index = 0
    for i, section in enumerate(draft["sections"]):
        parts.append(f"<h2>{html.escape(section['heading'])}</h2>")
        parts.append(_paragraphs_html(section["paragraphs"]))
        if image_index < len(extra_images):
            url = extra_images[image_index]
            cap = f"<figcaption>{html.escape(section['heading'])}</figcaption>"
            parts.append(f'<figure><img src="{html.escape(url)}">{cap}</figure>')
            image_index += 1
    parts.append(f'<p><b>Коротко:</b> {html.escape(draft["takeaway"])}</p>')
    parts.append(f'<p><i>{html.escape(draft["question"])}</i></p>')
    parts.append(
        '<p class="meta">Материал носит информационный характер и не заменяет '
        "консультацию врача.</p>"
    )
    parts.append(
        f'<p class="meta">Источник: <a href="{html.escape(source_url)}">'
        f"{html.escape(source)}</a></p>"
    )
    return "\n".join(parts)
