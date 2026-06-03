import io
import logging
import random
import re

import requests

import config

logger = logging.getLogger(__name__)

PEXELS_API = "https://api.pexels.com/v1/search"
PEXELS_PHOTO = "https://api.pexels.com/v1/photos/{id}"
UNSPLASH_API = "https://api.unsplash.com/search/photos"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _extract_keywords(text: str) -> list[str]:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "has", "have", "had", "do", "does", "did", "will", "would",
        "can", "could", "may", "might", "shall", "should", "to", "of",
        "in", "on", "at", "for", "with", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how",
        "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or",
        "if", "while", "that", "this", "these", "those", "it", "its",
        "и", "в", "на", "с", "по", "для", "от", "из", "до", "за",
        "о", "об", "при", "про", "без", "через", "над", "под",
        "этот", "это", "эта", "эти", "тот", "та", "те",
        "который", "которая", "которые", "что", "как", "так",
        "уже", "еще", "ещё", "у", "к", "а", "но", "да", "не",
    }
    words = text.split()
    keywords = [w for w in words if w not in stopwords and len(w) > 3]
    return keywords[:5]


def _search_pexels(query: str) -> str | None:
    if not config.PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            PEXELS_API,
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("photos"):
            photo = random.choice(data["photos"])
            return photo["src"]["large2x"]
    except Exception as e:
        logger.debug("Pexels search failed: %s", e)
    return None


def _search_unsplash(query: str) -> str | None:
    if not config.UNSPLASH_ACCESS_KEY:
        return None
    try:
        resp = requests.get(
            UNSPLASH_API,
            headers={"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"},
            params={"query": query, "per_page": 5, "orientation": "landscape"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            photo = random.choice(data["results"])
            return photo["urls"]["regular"]
    except Exception as e:
        logger.debug("Unsplash search failed: %s", e)
    return None


def _search_picsum(query: str) -> str:
    seed = re.sub(r"\s+", "-", query.strip()[:50])
    return f"https://picsum.photos/seed/{seed}/1200/630"


def find_image_for_topic(text: str) -> io.BytesIO | None:
    keywords = _extract_keywords(text)
    if not keywords:
        return None

    query = " ".join(keywords[:3])

    for attempt in range(3):
        url = None
        if attempt == 0:
            url = _search_pexels(query)
        elif attempt == 1:
            url = _search_pexels(keywords[0])
        elif attempt == 2:
            url = _search_picsum(query)

        if url:
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
                resp.raise_for_status()
                if "image" in resp.headers.get("content-type", ""):
                    return io.BytesIO(resp.content)
            except Exception as e:
                logger.debug("Image download failed: %s", e)
                continue

    try:
        url = _search_picsum(query)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        return io.BytesIO(resp.content)
    except Exception as e:
        logger.debug("Picsum fallback failed: %s", e)

    return None
