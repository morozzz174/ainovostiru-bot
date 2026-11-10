import hashlib
import html
import io
import json
import logging
import os
import re
from datetime import datetime, timezone
from email.utils import format_datetime

from PIL import Image

import config
import dzen_writer

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DIST_DIR = os.path.join(DOCS_DIR, "dzen")
ARTICLES_DIR = os.path.join(DIST_DIR, "articles")
PENDING_PATH = os.path.join(BASE_DIR, ".dzen_pending.json")

SITE = "https://morozzz174.github.io/ainovostiru-bot"
MAX_ITEMS = 20
JPEG_QUALITY = 82
PAGE_WIDTH = 1200
PAGE_HEIGHT = 630

CHANNELS = {
    "ai": {
        "title": "AINOVOSTI.RU",
        "description": "Новости искусственного интеллекта и технологий: переводы, анализ, видео с озвучкой.",
    },
    "facts": {
        "title": "FACTUM.RU",
        "description": "Наука, история, космос и открытия — коротко и по делу.",
    },
    "beauty": {
        "title": "Космобб",
        "description": "Косметология, уход за кожей и процедуры — без обещаний и волшебных кремов.",
        "avatar": "avatar-beauty.jpg",
    },
}

ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{summary}">
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 760px; margin: 40px auto;
        padding: 0 20px; line-height: 1.65; color: #1c1c1e; }}
img {{ width: 100%; height: auto; border-radius: 12px; display: block; }}
h1 {{ font-size: 30px; line-height: 1.25; margin: 24px 0 16px; }}
h2 {{ font-size: 22px; line-height: 1.3; margin: 28px 0 12px; }}
.lead {{ font-size: 19px; color: #3a3a3c; }}
figure {{ margin: 24px 0; }}
figcaption {{ color: #6e6e73; font-size: 14px; margin-top: 8px; }}
.meta {{ color: #6e6e73; font-size: 14px; margin: 14px 0 24px; }}
a {{ color: #0a58ca; }}
</style>
</head>
<body>
<article>
<p class="meta">{channel} · {date}</p>
<img src="{image}" alt="{title}">
<h1>{title}</h1>
{body}
</article>
</body>
</html>
"""

LANDING_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
body {{ font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 880px; margin: 40px auto;
        padding: 0 20px; line-height: 1.6; color: #1c1c1e; background: #fbfaf9; }}
header {{ margin-bottom: 28px; }}
h1 {{ font-size: 34px; margin: 0 0 6px; }}
.sub {{ color: #6e6e73; margin: 0; font-size: 17px; }}
.grid {{ display: grid; gap: 22px; }}
.card {{ background: #fff; border: 1px solid #eee7e2; border-radius: 14px; overflow: hidden; }}
.card img {{ width: 100%; height: 220px; object-fit: cover; display: block; }}
.card-body {{ padding: 16px 20px 20px; }}
.card h2 {{ font-size: 21px; line-height: 1.3; margin: 0 0 8px; }}
.card h2 a {{ color: #1c1c1e; text-decoration: none; }}
.card p {{ margin: 0; color: #4a4a4f; }}
.card .date {{ color: #8a8a8f; font-size: 13px; margin-bottom: 6px; }}
footer {{ margin-top: 36px; color: #8a8a8f; font-size: 14px; }}
a {{ color: #0a58ca; }}
</style>
</head>
<body>
<header>
<h1>{title}</h1>
<p class="sub">{description}</p>
</header>
<main class="grid">
{cards}
</main>
<footer>Материалы носят информационный характер и не заменяют консультацию врача.</footer>
</body>
</html>
"""

CARD_TEMPLATE = """<article class="card">
<a href="articles/{slug}.html"><img src="{image}" alt="{title}"></a>
<div class="card-body">
<p class="date">{date}</p>
<h2><a href="articles/{slug}.html">{title}</a></h2>
<p>{summary}</p>
</div>
</article>"""

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>{title}</title>
    <link>{channel_link}</link>
    <description>{description}</description>
    <language>ru</language>
    <generator>ainovostiru-bot</generator>
    <lastBuildDate>{now}</lastBuildDate>
    <image>
      <url>{avatar}</url>
      <title>{title}</title>
      <link>{channel_link}</link>
    </image>
{items}
  </channel>
</rss>
"""

ITEM_TEMPLATE = """    <item>
      <title>{title}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{pub_date}</pubDate>
      <category>format-article</category>
      <category>index</category>
      <category>comment-all</category>
      <description>{summary}</description>
      <content:encoded><![CDATA[{body}]]></content:encoded>
      <enclosure url="{image}" type="image/jpeg" />
    </item>"""


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _article_slug(title: str, pub_date: str) -> str:
    """Human-readable URL slug: Dzen rejects feeds with hash-only links.

    A short hash suffix keeps two articles with the same headline apart, while
    the transliterated title makes the link look like a normal publication
    rather than a random token.
    """
    latin = "".join(_TRANSLIT.get(ch, ch) for ch in title.lower())
    latin = re.sub(r"[^a-z0-9]+", "-", latin).strip("-")
    if len(latin) > 60:
        latin = latin[:60].rsplit("-", 1)[0]
    digest = hashlib.sha1(f"{title}{pub_date}".encode("utf-8")).hexdigest()[:6]
    return f"{latin or 'article'}-{digest}"


def _clean(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"[*_`~\[\]]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _meta_description(summary: str, limit: int = 200) -> str:
    """Escape first, then cut: cutting the escaped text can split an entity."""
    return html.escape(summary[:limit])


def _paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", _clean(text)) if p.strip()]
    if not parts:
        return ""
    return "".join(f"<p>{html.escape(part)}</p>" for part in parts)


def _summary(text: str, limit: int = 300) -> str:
    clean = _clean(text)
    if len(clean) <= limit:
        return clean
    cut = clean[:limit]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut + "…"


def to_jpeg(image: io.BytesIO) -> bytes:
    image.seek(0)
    picture = Image.open(image).convert("RGB")
    if picture.size != (PAGE_WIDTH, PAGE_HEIGHT):
        picture = picture.resize((PAGE_WIDTH, PAGE_HEIGHT), Image.LANCZOS)
    buf = io.BytesIO()
    picture.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    return buf.getvalue()


def load_pending() -> dict:
    if not os.path.exists(PENDING_PATH):
        return {}
    try:
        with open(PENDING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        logger.warning("Dzen: pending file unreadable: %s", e)
        return {}


def save_pending(pending: dict) -> None:
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def _source_text(url: str, limit: int = 8000) -> str:
    """Opening paragraphs of the source page, used to ground the LLM."""
    try:
        from collector import _page_paragraphs
    except Exception:
        return ""
    try:
        pieces: list[str] = []
        total = 0
        for paragraph in _page_paragraphs(url):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            pieces.append(paragraph)
            total += len(paragraph)
            if total >= limit:
                break
        return " ".join(pieces)[:limit]
    except Exception as e:
        logger.info("Dzen: source text fetch failed: %s", e)
        return ""


def add_article(article, image_buf: io.BytesIO) -> bool:
    """Queue a published article for the next feed build.

    Dzen needs a long read, not the two-sentence Telegram teaser. The draft is
    generated here, while the source text is still at hand. If the model is
    unavailable or returns something unusable, the short teaser is kept so a
    feed build never blocks a Telegram post.
    """
    if not config.DZEN_ENABLED or image_buf is None:
        return False
    theme = config.THEME if config.THEME in CHANNELS else "ai"
    try:
        jpeg = to_jpeg(image_buf)
    except Exception as e:
        logger.warning("Dzen: image conversion failed: %s", e)
        return False

    draft = None
    if config.LLM_API_KEY:
        source_text = _source_text(article.url)
        if dzen_writer.business_source(source_text):
            logger.info("Dzen: source page is business news, skipping the feed item")
            return False
        draft = dzen_writer.generate_article(
            article.title,
            article.description or "",
            article.source,
            source_text=source_text,
        )
    if not draft and config.DZEN_REQUIRE_ARTICLE:
        logger.warning("Dzen: no long article for %r, skipping the feed item", article.title[:60])
        return False

    images = []
    if draft:
        images.append({"hex": jpeg.hex(), "caption": draft["title"]})
        quote_cards = draft.get("quotes") or []
        for i, quote in enumerate(quote_cards[: max(0, config.DZEN_IMAGES - 1)]):
            try:
                card = dzen_writer.make_quote_card(quote, i)
            except Exception as e:
                logger.warning("Dzen: quote card failed: %s", e)
                break
            images.append({"hex": card.hex(), "caption": "Ключевая мысль"})
        placeholders = [""] + [f"{{{{IMG{i}}}}}" for i in range(1, len(images))]
        body = dzen_writer.render_body(draft, placeholders, article.url, article.source)
        summary = _summary(draft["lead"])
        title = draft["title"]
        logger.info("Dzen: long article %d chars for %r", len(body), title[:60])
    else:
        images.append({"hex": jpeg.hex(), "caption": ""})
        body = _paragraphs(article.description)
        summary = _summary(article.description)
        title = _clean(article.title)

    pending = load_pending()
    pending.setdefault(theme, []).append({
        "title": title,
        "body": body,
        "summary": summary,
        "source_url": article.url,
        "source": article.source,
        "images": images,
        "pub_date": datetime.now(timezone.utc).isoformat(),
    })
    save_pending(pending)
    logger.info("Dzen: queued %r for the %s feed", title[:60], theme)
    return True


def _write_avatar() -> str:
    os.makedirs(DIST_DIR, exist_ok=True)
    target = os.path.join(DIST_DIR, "avatar.jpg")
    if os.path.exists(target):
        return target
    for candidate in (
        os.path.join(BASE_DIR, "app_icon_1024.png"),
        os.path.join(DIST_DIR, "..", "..", "app_icon_1024.png"),
    ):
        if not os.path.exists(candidate):
            continue
        picture = Image.open(candidate).convert("RGB")
        square = min(picture.size)
        picture = picture.crop((
            (picture.width - square) // 2, 0,
            (picture.width - square) // 2 + square, square,
        )).resize((512, 512), Image.LANCZOS)
        picture.save(target, "JPEG", quality=88, optimize=True)
        logger.info("Dzen: avatar written from %s", os.path.basename(candidate))
        return target
    return ""


def _items_path(theme: str) -> str:
    return os.path.join(DIST_DIR, f"items-{theme}.json")


def _load_items(theme: str) -> list[dict]:
    path = _items_path(theme)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return []


def _build_item(item: dict, theme: str) -> tuple[str, dict]:
    slug = _article_slug(item["title"], item["pub_date"])
    article_path = f"dzen/articles/{slug}.html"
    link = f"{SITE}/{article_path}"
    pub_date = format_datetime(
        datetime.fromisoformat(item["pub_date"]).astimezone(timezone.utc),
    )
    channel = CHANNELS[theme]["title"]

    # New items carry a list (hero + quote cards); old items have one image.
    images = item.get("images")
    if not images:
        images = [{"hex": item.get("image", ""), "caption": ""}]
    image_slug = hashlib.sha1(f"{item['title']}{item['pub_date']}".encode("utf-8")).hexdigest()[:12]
    image_names: list[str] = []
    for image in images:
        if not image.get("hex"):
            continue
        name = f"{image_slug}.jpg" if not image_names else f"{image_slug}-{len(image_names)}.jpg"
        with open(os.path.join(DIST_DIR, name), "wb") as f:
            f.write(bytes.fromhex(image["hex"]))
        image_names.append(name)
    if not image_names:
        raise ValueError(f"Dzen item has no images: {item['title'][:60]}")
    image_urls = [f"{SITE}/dzen/{name}" for name in image_names]
    image_url = image_urls[0]

    body = item["body"] or f"<p>{html.escape(item['summary'])}</p>"
    for i, url in enumerate(image_urls[1:], start=1):
        body = body.replace(f"{{{{IMG{i}}}}}", url)
    body = re.sub(r'<figure><img src="\{\{IMG\d+\}\}">.*?</figure>', "", body, flags=re.S)

    os.makedirs(ARTICLES_DIR, exist_ok=True)
    with open(os.path.join(ARTICLES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(ARTICLE_TEMPLATE.format(
            title=html.escape(item["title"]),
            summary=_meta_description(item["summary"]),
            channel=html.escape(channel),
            date=datetime.fromisoformat(item["pub_date"]).astimezone().strftime("%d.%m.%Y"),
            image=f"../{image_names[0]}",
            body=body,
            source=html.escape(item["source_url"]),
        ))

    # Dzen ignores the item <title> during conversion, so the headline must be
    # repeated inside content:encoded. The site page already has its own h1.
    rss_body = f"<h1>{html.escape(item['title'])}</h1>\n{body}"
    rss_body = rss_body.replace('<p class="lead">', "<p>")

    xml = ITEM_TEMPLATE.format(
        title=html.escape(item["title"]),
        link=link,
        pub_date=pub_date,
        summary=html.escape(item["summary"]),
        body=rss_body,
        image=image_url,
    )
    card = {
        "slug": slug,
        "title": html.escape(item["title"]),
        "summary": html.escape(item["summary"]),
        "image": image_names[0],
        "date": datetime.fromisoformat(item["pub_date"]).astimezone().strftime("%d.%m.%Y"),
    }
    return xml, card


def flush(theme: str | None = None) -> dict:
    """Write feeds and article pages. Called by the workflow, not the bot."""
    os.makedirs(DIST_DIR, exist_ok=True)
    avatar = _write_avatar()
    avatar_url = f"{SITE}/dzen/avatar.jpg" if avatar else ""

    pending = load_pending()
    themes = [theme] if theme else (list(pending) or list(CHANNELS))
    result = {"themes": {}, "written": 0}

    for name in themes:
        channel = CHANNELS.get(name, CHANNELS["ai"])
        channel_avatar = channel.get("avatar")
        channel_avatar_url = (
            f"{SITE}/dzen/{channel_avatar}" if channel_avatar else avatar_url
        )
        items = _load_items(name)

        for item in pending.get(name, []):
            if any(existing["title"] == item["title"] for existing in items):
                continue
            items.append(item)

        items = items[-MAX_ITEMS:]
        built = [_build_item(item, name) for item in items]
        rendered = [xml for xml, _ in built]
        cards = [card for _, card in built]

        channel_link = (
            f"{SITE}/dzen/" if name == "beauty" else f"{SITE}/dzen/index-{name}.html"
        )
        feed_path = os.path.join(DIST_DIR, f"feed-{name}.xml")
        with open(feed_path, "w", encoding="utf-8") as f:
            f.write(RSS_TEMPLATE.format(
                title=channel["title"],
                description=channel["description"],
                channel_link=channel_link,
                avatar=channel_avatar_url,
                now=format_datetime(datetime.now(timezone.utc)),
                items="\n".join(rendered),
            ))
        if name == "ai":
            with open(os.path.join(DOCS_DIR, "feed.xml"), "w", encoding="utf-8") as f:
                f.write(RSS_TEMPLATE.format(
                    title=channel["title"],
                    description=channel["description"],
                    channel_link=channel_link,
                    avatar=channel_avatar_url,
                    now=format_datetime(datetime.now(timezone.utc)),
                    items="\n".join(rendered),
                ))

        landing_name = "index.html" if name == "beauty" else f"index-{name}.html"
        with open(os.path.join(DIST_DIR, landing_name), "w", encoding="utf-8") as f:
            f.write(LANDING_TEMPLATE.format(
                title=html.escape(channel["title"]),
                description=html.escape(channel["description"]),
                cards="\n".join(
                    CARD_TEMPLATE.format(**card) for card in reversed(cards)
                ),
            ))

        with open(_items_path(name), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        result["themes"][name] = len(items)
        result["written"] += len(rendered)
        logger.info("Dzen: feed-%s.xml written with %d items", name, len(items))

    # Only clear the queue for the feeds that were actually rebuilt, otherwise
    # a partial run would throw away articles it never wrote to a feed.
    remaining = {name: items for name, items in pending.items() if name not in themes}
    save_pending(remaining)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import sys

    args = [a for a in sys.argv[1:] if a]
    theme = None
    if args and args[0] in ("flush", "build", "publish"):
        args = args[1:]
    if args:
        theme = args[0]
    outcome = flush(theme)
    logger.info("Dzen: %s", outcome)
    raise SystemExit(0 if outcome["written"] >= 0 else 1)
