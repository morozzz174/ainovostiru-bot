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
OPENVERSE_API = "https://api.openverse.org/v1/images/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


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
            params={"query": query, "per_page": 5, "orientation": config.IMAGE_ORIENTATION},
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
            params={"query": query, "per_page": 5, "orientation": config.IMAGE_ORIENTATION},
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


RU_TO_EN = {
    "искусственн": "artificial intelligence",
    "интеллект": "artificial intelligence",
    "нейросет": "neural network",
    "машинн": "machine learning",
    "алгоритм": "algorithm",
    "модел": "technology",
    "физик": "physics laboratory",
    "сверхпровод": "superconductor",
    "материал": "materials science",
    "энерг": "energy",
    "двигател": "engine",
    "космос": "space",
    "астроном": "astronomy",
    "планет": "planet",
    "телескоп": "telescope",
    "ракет": "rocket launch",
    "биолог": "biology",
    "медицин": "medicine",
    "здоров": "health",
    "генет": "genetics",
    "днк": "dna",
    "мозг": "brain",
    "клетк": "cell biology",
    "археолог": "archaeology",
    "истори": "history",
    "папирус": "ancient papyrus",
    "памятник": "ancient monument",
    "раскопк": "excavation",
    "учен": "scientists",
    "исследовател": "research laboratory",
    "наук": "science",
    "открыти": "discovery",
    "робот": "robot",
    "программ": "software",
    "разработ": "software developer",
    "компан": "technology company",
    "компьют": "computer",
    "процессор": "processor",
    "сервер": "data center",
    "телефон": "smartphone",
    "интернет": "internet",
    "безопасност": "cybersecurity",
    "шифр": "encryption",
    "квант": "quantum computing",
    "рынок": "stock market",
    "экономик": "economy",
    "инвест": "investment",
    "климат": "climate",
    "эколог": "ecology",
    "космическ": "space",
    "игру": "gaming",
    "фильм": "cinema",
    "музык": "music",
    "спорт": "sports",
    "автомобил": "car",
    "самолет": "aircraft",
    "еда": "food",
}


def _english_queries(keywords: list[str]) -> list[str]:
    """Openverse has almost no Russian coverage, so map stems to English."""
    queries = []
    for word in keywords:
        for stem, english in RU_TO_EN.items():
            if word.startswith(stem):
                if english not in queries:
                    queries.append(english)
                break
    return queries[:3]


def _search_openverse(query: str) -> tuple[str, str] | None:
    try:
        resp = requests.get(
            OPENVERSE_API,
            params={
                "q": query,
                "page_size": 6,
                "license_type": "commercial",
                "mature": "false",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        photo = random.choice(results)
        url = photo.get("url")
        if not url:
            return None
        creator = (photo.get("creator") or "").strip()
        license_name = (photo.get("license") or "").lower()
        if license_name == "cc0":
            label = "CC0"
        elif license_name.startswith("cc"):
            label = "CC " + license_name[2:].upper()
        elif license_name:
            label = license_name.upper()
        else:
            label = ""
        parts = [p for p in (creator, label) if p]
        credit = " · ".join(parts)
        return url, credit
    except Exception as e:
        logger.debug("Openverse search failed: %s", e)
    return None


def _search_picsum(query: str) -> str:
    seed = re.sub(r"\s+", "-", query.strip()[:50])
    return f"https://picsum.photos/seed/{seed}/1200/630"


def _download(url: str) -> io.BytesIO | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        resp.raise_for_status()
        if "image" in resp.headers.get("content-type", ""):
            return io.BytesIO(resp.content)
    except Exception as e:
        logger.debug("Image download failed for %s: %s", url[:60], e)
    return None


def find_image_with_credit(text: str) -> tuple[io.BytesIO | None, str]:
    """Return a photo for the topic plus a short attribution line.

    picsum.photos answers 403 for datacenter and cloud IPs, which is where the
    bot runs, so Openverse (WordPress, CC licensed, no key) is the primary
    source. Attribution matters for CC-BY images, so the credit is returned
    instead of being dropped.
    """
    keywords = _extract_keywords(text)
    if not keywords:
        return None, ""

    candidates = []
    for word in keywords[:3]:
        candidates.append(_search_pexels(word) or _search_unsplash(word))

    for query in _english_queries(keywords):
        found = _search_openverse(query)
        if found:
            candidates.append(found)

    for entry in candidates:
        if not entry:
            continue
        url, credit = entry
        image = _download(url)
        if image:
            return image, credit

    for query in _english_queries(keywords) + [" ".join(keywords[:3]), keywords[0]]:
        found = _search_openverse(query)
        if not found:
            continue
        image = _download(found[0])
        if image:
            return image, found[1]

    for query in (" ".join(keywords[:3]), keywords[0]):
        image = _download(_search_picsum(query))
        if image:
            return image, ""

    return None, ""


def find_image_for_topic(text: str) -> io.BytesIO | None:
    image, _ = find_image_with_credit(text)
    return image
