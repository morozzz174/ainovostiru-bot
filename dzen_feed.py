import hashlib
import html
import io
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import quote

from PIL import Image

import config

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
        "title": "FACTUM.RU Beauty",
        "description": "Косметология, уход за кожей, антивозрастные исследования и индустрия красоты.",
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
<hr>
<p class="meta">Источник: <a href="{source}">{source}</a></p>
</article>
</body>
</html>
"""

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>{title}</title>
    <link>{site}/dzen/</link>
    <description>{description}</description>
    <language>ru</language>
    <generator>ainovostiru-bot</generator>
    <lastBuildDate>{now}</lastBuildDate>
    <image>
      <url>{avatar}</url>
      <title>{title}</title>
      <link>{site}/dzen/</link>
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
      <category>{category}</category>
      <description>{summary}</description>
      <content:encoded><![CDATA[{body}]]></content:encoded>
      <media:content url="{image}" medium="image" type="image/jpeg" />
    </item>"""


def _slug(title: str) -> str:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10]
    return f"{digest}-{int(time.time() * 1000) % 100000:05d}"


def _clean(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"[*_`~\[\]]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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


def add_article(article, image_buf: io.BytesIO) -> bool:
    """Queue a published article for the next feed build."""
    if not config.DZEN_ENABLED or image_buf is None:
        return False
    theme = config.THEME if config.THEME in CHANNELS else "ai"
    try:
        jpeg = to_jpeg(image_buf)
    except Exception as e:
        logger.warning("Dzen: image conversion failed: %s", e)
        return False

    pending = load_pending()
    pending.setdefault(theme, []).append({
        "title": _clean(article.title),
        "body": _paragraphs(article.description),
        "summary": _summary(article.description),
        "source_url": article.url,
        "source": article.source,
        "image": jpeg.hex(),
        "pub_date": datetime.now(timezone.utc).isoformat(),
    })
    save_pending(pending)
    logger.info("Dzen: queued %r for the %s feed", article.title[:60], theme)
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


def _build_item(item: dict, theme: str) -> str:
    slug = hashlib.sha1(f"{item['title']}{item['pub_date']}".encode("utf-8")).hexdigest()[:12]
    image_name = f"{slug}.jpg"
    article_path = f"dzen/articles/{slug}.html"
    image_url = f"{SITE}/{image_name}"
    link = f"{SITE}/{article_path}"
    pub_date = format_datetime(
        datetime.fromisoformat(item["pub_date"]).astimezone(timezone.utc),
    )
    channel = CHANNELS[theme]["title"]

    os.makedirs(ARTICLES_DIR, exist_ok=True)
    with open(os.path.join(ARTICLES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(ARTICLE_TEMPLATE.format(
            title=html.escape(item["title"]),
            summary=html.escape(item["summary"])[:200],
            channel=html.escape(channel),
            date=datetime.fromisoformat(item["pub_date"]).astimezone().strftime("%d.%m.%Y"),
            image=f"../{image_name}",
            body=item["body"] or f"<p>{html.escape(item['summary'])}</p>",
            source=html.escape(item["source_url"]),
        ))
    with open(os.path.join(DIST_DIR, image_name), "wb") as f:
        f.write(bytes.fromhex(item["image"]))

    return ITEM_TEMPLATE.format(
        title=html.escape(item["title"]),
        link=link,
        pub_date=pub_date,
        category=html.escape(item["source"]),
        summary=html.escape(item["summary"]),
        body=item["body"] or f"<p>{html.escape(item['summary'])}</p>",
        image=image_url,
    )


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
        items = _load_items(name)

        for item in pending.get(name, []):
            if any(existing["title"] == item["title"] for existing in items):
                continue
            items.append(item)

        items = items[-MAX_ITEMS:]
        rendered = [_build_item(item, name) for item in items]

        feed_path = os.path.join(DIST_DIR, f"feed-{name}.xml")
        with open(feed_path, "w", encoding="utf-8") as f:
            f.write(RSS_TEMPLATE.format(
                title=channel["title"],
                description=channel["description"],
                site=SITE,
                avatar=avatar_url,
                now=format_datetime(datetime.now(timezone.utc)),
                items="\n".join(rendered),
            ))
        if name == "ai":
            with open(os.path.join(DOCS_DIR, "feed.xml"), "w", encoding="utf-8") as f:
                f.write(RSS_TEMPLATE.format(
                    title=channel["title"],
                    description=channel["description"],
                    site=SITE,
                    avatar=avatar_url,
                    now=format_datetime(datetime.now(timezone.utc)),
                    items="\n".join(rendered),
                ))

        with open(_items_path(name), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        result["themes"][name] = len(items)
        result["written"] += len(rendered)
        logger.info("Dzen: feed-%s.xml written with %d items", name, len(items))

    save_pending({})
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    import sys

    args = sys.argv[1:]
    outcome = flush(args[0] if args else None)
    logger.info("Dzen: %s", outcome)
