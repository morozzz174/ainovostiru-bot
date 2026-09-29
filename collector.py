import logging
import re
import time
from html import unescape

import feedparser
import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


class Article:
    def __init__(self, title: str, url: str, description: str, source: str,
                 image_url: str | None = None, lang: str = "en"):
        self.title = self._clean_html(title)
        self.url = url
        self.description = self._clean_html(description)
        self.source = source
        self.image_url = image_url
        self.lang = lang

    @staticmethod
    def _clean_html(text: str) -> str:
        # Some feeds (Dermatology Times) wrap values in CDATA. Strip the
        # wrapper first, otherwise the tag-strip below eats the whole title.
        text = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", text, flags=re.S)
        text = re.sub(r"<[^>]+>", "", text)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def __repr__(self):
        return f"Article({self.title[:50]}... | {self.source})"


def _fetch_image_from_page(url: str) -> str | None:
    try:
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in [
            'meta[property="og:image"]',
            'meta[name="twitter:image"]',
            'meta[property="twitter:image"]',
        ]:
            meta = soup.select_one(tag)
            if meta and meta.get("content"):
                return meta["content"]
        for img in soup.select("article img, .post-content img, .entry-content img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http"):
                return src
    except Exception as e:
        logger.debug("Image fetch failed for %s: %s", url, e)
    return None


def _is_relevant(title: str, description: str) -> bool:
    text = (title + " " + description).lower()
    for kw in config.KEYWORDS:
        if kw in text:
            return True
    return False


def _fetch_feed(url: str, attempts: int = 3) -> bytes | None:
    """Fetch a feed, retrying the rate limits and blocks publishers hand out.

    VentureBeat answered 429 and science.org 403 on the GitHub runners, so a
    single request was not enough: back off, drop a browser Accept header in
    and try again. Connection timeouts are not retried, an unreachable host
    stays unreachable and the retry would only triple the wait.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    }
    for attempt in range(attempts):
        try:
            resp = SESSION.get(url, timeout=20, headers=headers)
        except requests.RequestException:
            raise
        if resp.status_code == 200:
            return resp.content
        if resp.status_code in (429, 403, 503) and attempt + 1 < attempts:
            logger.info("Feed %s answered %s, retry %d", url[:60], resp.status_code, attempt + 1)
            time.sleep(2.0 * (attempt + 1))
            continue
        resp.raise_for_status()
    return None


def _parse_rss(source_key: str, source_cfg: dict) -> list[Article]:
    articles = []
    try:
        content = _fetch_feed(source_cfg["url"])
        if not content:
            return articles
        feed = feedparser.parse(content)
        for entry in feed.entries[:12]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            desc = entry.get("summary") or entry.get("description") or ""
            if not _is_relevant(title, desc):
                continue
            image_url = None
            if entry.get("media_content"):
                for media in entry["media_content"]:
                    if media.get("type", "").startswith("image"):
                        image_url = media["url"]
                        break
            if not image_url and entry.get("media_thumbnail"):
                image_url = entry["media_thumbnail"][0].get("url")
            articles.append(
                Article(
                    title=title,
                    url=link,
                    description=desc,
                    source=source_cfg["name"],
                    image_url=image_url,
                    lang=source_cfg["lang"],
                )
            )
    except Exception as e:
        logger.warning("RSS error for %s (%s): %s", source_key, source_cfg["name"], e)
    return articles


def collect_news() -> list[Article]:
    all_articles: list[Article] = []
    seen_urls: set[str] = set()

    for key, cfg in config.NEWS_SOURCES.items():
        logger.info("Fetching: %s (%s)", cfg["name"], key)
        for article in _parse_rss(key, cfg):
            if article.url and article.url not in seen_urls:
                seen_urls.add(article.url)
                all_articles.append(article)

    logger.info("Collected %d unique articles", len(all_articles))

    for article in all_articles[:]:
        if not article.image_url:
            img = _fetch_image_from_page(article.url)
            if img:
                article.image_url = img

    return all_articles
