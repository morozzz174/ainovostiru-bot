import logging
from difflib import SequenceMatcher
import re
import time
from html import unescape
from urllib.parse import urljoin

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

# Some sites advertise a single site-wide logo as og:image, so every article
# would ship the publisher's watermark. Treat those as "no image" and let the
# publisher fall back to a themed photo or a generated poster.
_PLACEHOLDER_IMAGE_RE = re.compile(
    r"/(logo|logos|icon|icons|avatar|placeholder|banner|sprite|favicon|watermark)[^/]*"
    r"\.(?:jpe?g|png|gif|webp|svg)",
    re.I,
)


def _is_placeholder_image(url: str) -> bool:
    return bool(_PLACEHOLDER_IMAGE_RE.search(url or ""))

# How far into a feed to look, and how many relevant items to keep per source.
FEED_SCAN_LIMIT = 60
PER_FEED_LIMIT = 6
# HTML listings are longer than feeds; keep more but still bounded.
PER_HTML_LIMIT = 40


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
            if meta and meta.get("content") and not _is_placeholder_image(meta["content"]):
                return meta["content"]
        for img in soup.select("article img, .post-content img, .entry-content img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http") and not _is_placeholder_image(src):
                return src
    except Exception as e:
        logger.debug("Image fetch failed for %s: %s", url, e)
    return None


# MetalTorg and MetalBulletin keep the body behind a paywall: their pages show
# the headline plus a subscriber stub, so fetching them only wastes a request.
_PAYWALLED_HOSTS = ("metaltorg.ru", "metalbulletin.ru")
_PAYWALL_MARKERS = ("только подписчики", "доступ к полному тексту")
_BOILERPLATE_RE = re.compile(
    r"(подпиш|подробнее с тарифом|читайте также|смотрите также|источник:|фото:|"
    r"телеграм-канал|оформить подписку|коммент|реклама|\+7 ?\d|©|"
    r"все права защищены|материал подготовлен)",
    re.I,
)
_CONTENT_SELECTORS = (
    "article",
    "div.article-body",
    "div.article__body",
    "div.news-body",
    "div.news-text",
    "div.entry-content",
    "div.post-content",
    "div.text-content",
    "main",
)


def _page_paragraphs(url: str) -> list[str]:
    """Readable paragraphs of an article page, boilerplate removed."""
    try:
        resp = SESSION.get(url, timeout=12)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.debug("Body fetch failed for %s: %s", url, e)
        return []
    if any(marker in html.lower() for marker in _PAYWALL_MARKERS):
        return []

    soup = BeautifulSoup(html, "lxml")
    for bad in soup(
        ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "figure"]
    ):
        bad.decompose()

    best: list[str] = []
    for selector in _CONTENT_SELECTORS:
        for container in soup.select(selector):
            paras = []
            for p in container.find_all("p"):
                text = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
                if len(text) < 60 or _BOILERPLATE_RE.search(text):
                    continue
                paras.append(text)
            if sum(map(len, paras)) > sum(map(len, best)):
                best = paras
    return best


def enrich_description(article: Article, min_chars: int = 120, max_chars: int = 600) -> str:
    """Turn a bare headline into the opening sentences of the article.

    Feeds that carry a teaser already say enough, and paywalled outlets cannot
    give more, so only the remaining short descriptions cost a page fetch.
    """
    current = (article.description or "").strip()
    if len(current) >= min_chars:
        return current
    if any(host in article.url for host in _PAYWALLED_HOSTS):
        return current

    pieces: list[str] = []
    for paragraph in _page_paragraphs(article.url):
        if paragraph in current or paragraph.startswith(article.title[:40]):
            continue
        pieces.append(paragraph)
        if sum(map(len, pieces)) >= max_chars:
            break

    body = " ".join(pieces).strip()
    if len(body) < min_chars:
        return current
    if len(body) > max_chars:
        cut = body[:max_chars]
        stop = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        body = cut[: stop + 1] if stop >= min_chars else cut.rsplit(" ", 1)[0] + "…"
    return body


def _matched_keywords(text: str, keywords=None) -> set[str]:
    """Keywords found in a text, matched on a stem prefix.

    A plain substring test let "снижение" in a story about the central bank
    match "снизить", dragging unrelated finance pieces into a health channel.
    A stem keeps inflected Russian forms working, so "старения" still finds
    "старение".

    STEM_LEN is per-theme: 4 tolerates short stems but collides badly on long
    words ("компрессор"[:4] = "комп" matched "компания", "прокат"[:4] =
    "прок" matched "прокомментировал"). Domains where collisions showed up
    raise it to 6, which still covers every Russian inflection.
    """
    stem_len = getattr(config, "STEM_LEN", 4)
    # "рифлёный" and "рифленый" are the same word; without this a keyword
    # written with "е" misses every headline that spells it with "ё".
    text = text.lower().replace("ё", "е")
    words = set(re.findall(r"\w+", text, flags=re.UNICODE))
    found = set()
    for w in words:
        for kw in keywords or config.KEYWORDS:
            # 3-letter words matter: ММК, ТМК, ОМК, GPT are real keywords and
            # the old >= 4 guard silently dropped them.
            if len(w) >= 3 and w.startswith(kw[:stem_len]):
                found.add(kw)
                break
    return found


def _is_relevant(title: str, source_cfg: dict) -> bool:
    # Headlines only. Summaries in general news feeds mention skin, cells and
    # health while describing an unrelated subject - space launches, finance -
    # so matching on them pulled rocket and central bank stories into a
    # cosmetology channel.
    # General business feeds use the strict list, where "стал" cannot fire on
    # the verb "стало любопытство".
    words = (
        config.STRONG_KEYWORDS if source_cfg.get("strong") else config.KEYWORDS
    )
    return bool(_matched_keywords(title, words))


# RF and CIS markers: a story that mentions any of them is kept even when it
# also talks about China or Turkey (e.g. "экспорт стали в Китай").
_GEO_HOME = (
    "росси", "рф", "москв", "подмосков", "петербург", "ленинград",
    "урал", "сибир", "челябинск", "магнитогорск", "липецк", "череповец",
    "новолипецк", "тагил", "тольятти", "волгоград", "самар", "саратов",
    "ростов", "краснодар", "ставропол", "кавказ", "татарстан",
    "башкортостан", "башкири", "свердловск", "кемерово", "кузбасс",
    "красноярск", "иркутск", "новосибирск", "омск", "тюмен", "ханты",
    "ямал", "приморск", "дальневосточн", "сахалин", "арктик", "мурманск",
    "архангельск", "вологод", "тула", "белгород", "курск", "оренбург",
    "перм", "нижегородск", "ярослав", "твер", "смоленск", "калуга",
    "рязан", "воронеж", "пенза", "ульяновск", "киров", "хабаровск",
    "владивосток", "якут", "бурят", "хакас", "алтай", "дагестан",
    "чечн", "осети", "абхаз", "крым", "севастопол", "донбасс",
    "луганск", "донецк", "запорож", "херсон", "мариупол", "днепр",
    "киев", "харьков", "одесс", "львов", "украин", "белорус", "минск",
    "бмз", "беларус", "казахстан", "алматы", "астана", "шымкент",
    "караганда", "узбек", "ташкент", "таджик", "душанбе", "туркмен",
    "ашхабад", "киргиз", "кыргыз", "бишкек", "азербайджан", "баку",
    "армени", "ереван", "грузи", "тбилиси", "еаэс", "снг",
    "таможенн", "союзн", "евразийск",
    # Компании и площадки РФ/СНГ: их имена в заголовке и есть география.
    "чмк", "оэмк", "ммк", "тмк", "нлмк", "чрпз", "омк", "пмх", "евраз",
    "русал", "северстал", "мечел", "металлоинвест", "селигдар",
    "промсорт", "тулачермет", "цниичермет", "чермк", "ржд", "бутб",
    "металлоторг", "техинвестстрой", "норильск", "полюс", "русская сталь",
    "белта", "казмунайгаз", "укрметаллургпром", "интерпайп",
)

# Foreign markers used only to drop stories with no RF/CIS angle at all.
_GEO_FOREIGN = (
    "сша", "америк", "канад", "мексик", "бразил", "аргентин", "чили",
    "перу", "колумби", "кита", "кнр", "япони", "японск", "корея", "кореи",
    "корее", "корейск", "кореян", "ес",
    "тайван", "индии", "индия", "индийск", "вьетнам", "индонези",
    "малайзи", "таиланд", "филиппин", "австрал", "новозеланд", "европ",
    "евросоюз", "германи", "немецк", "франци", "французск", "итали",
    "итальянск", "испани", "португали", "великобритани", "британ",
    "англи", "швеци", "шведск", "финлянд", "финск", "норвеги", "дани",
    "нидерланд", "бельги", "швейцари", "австри", "польш", "польск",
    "чехи", "словаки", "венгри", "румыни", "болгари", "серби", "хорвати",
    "словени", "греци", "турци", "турецк", "иран", "ирак", "израил",
    "саудовск", "эмират", "египет", "юар", "нигери", "эфиопи",
    "пакистан", "бангладеш", "непал", "монголи", "миров", "окселёсунд",
    "барзингхаузен", "дюссельдорф", "global", "world",
    "worldwide",
    # Latin names of countries and majors that show up untranslated in
    # Russian industry copy ("Nippon Steel Slovakia", "Tenaris").
    "usa", "u.s", "america", "china", "chinese", "india", "indian",
    "japan", "japanese", "korea", "korean", "taiwan", "vietnam",
    "indonesia", "malaysia", "thailand", "australia", "brazil", "canada",
    "mexico", "europe", "european", "germany", "german", "poland",
    "polish", "turkey", "turkish", "france", "french", "italy", "italian",
    "spain", "britain", "british", "sweden", "swedish", "finland",
    "norway", "denmark", "netherlands", "belgium", "switzerland",
    "austria", "slovakia", "slovak", "czech", "romania", "hungary",
    "bulgaria", "serbia", "croatia", "greece", "egypt", "iran", "iraq",
    "israel", "saudi", "emirates", "nippon", "posco", "jfe", "hyundai",
    "baosteel", "baowu", "thyssenkrupp", "voestalpine", "outokumpu",
    "nucor", "cleveland-cliffs", "tenaris", "vale", "bhp", "rio tinto",
    "ssab", "stelco", "arcelormittal", "tharisa", "centinela",
    "antofagasta", "antaike", "jefferies", "deep yellow", "knauf", "wsa",
    "cme", "uk", "lme", "comex",
)

# Short markers and Latin names need word boundaries: "рф" as a plain
# substring matches "Дюссельдорфе", "ес" matches "лес" and "vale" matches
# "value". Long Cyrillic stems stay as substrings so inflections keep working.
def _marker_matcher(markers):
    words = tuple(m for m in markers if m.isascii() or len(m) <= 3)
    subs = tuple(m for m in markers if not m.isascii() and len(m) > 3)
    pattern = None
    if words:
        pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(m) for m in words) + r")\b",
            re.UNICODE,
        )
    return subs, pattern


_GEO_HOME_SUB, _GEO_HOME_RE = _marker_matcher(_GEO_HOME)
_GEO_FOREIGN_SUB, _GEO_FOREIGN_RE = _marker_matcher(_GEO_FOREIGN)


def _has_home(text: str) -> bool:
    return bool(_GEO_HOME_RE and _GEO_HOME_RE.search(text)) or any(
        marker in text for marker in _GEO_HOME_SUB
    )


def _has_foreign(text: str) -> bool:
    return bool(_GEO_FOREIGN_RE and _GEO_FOREIGN_RE.search(text)) or any(
        marker in text for marker in _GEO_FOREIGN_SUB
    )


def _geo_rank(title: str, description: str = "") -> int:
    """1 = RF/CIS, 0 = no geography, -1 = only foreign.

    The headline decides first: a teaser often mentions Russia only as a
    comparison, which kept "производство стали в Китае" because its summary
    ended with a Russian market remark. The summary is consulted only when
    the headline names no country at all.
    """
    head = title.lower().replace("ё", "е")
    if _has_home(head):
        return 1
    if _has_foreign(head):
        return -1
    body = description.lower().replace("ё", "е")
    if _has_home(body):
        return 1
    if _has_foreign(body):
        return -1
    return 0


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
    require_keyword = source_cfg.get("require_keyword", True)
    try:
        content = _fetch_feed(source_cfg["url"])
        if not content:
            return articles
        feed = feedparser.parse(content)
        for entry in feed.entries[:FEED_SCAN_LIMIT]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            desc = entry.get("summary") or entry.get("description") or ""
            if require_keyword and not _is_relevant(title, source_cfg):
                continue
            if len(articles) >= PER_FEED_LIMIT:
                break
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


def _html_fetch(source_cfg: dict) -> BeautifulSoup | None:
    url = source_cfg["url"]
    timeout = source_cfg.get("timeout", 25)
    last_error = None
    for attempt in range(2):
        try:
            resp = SESSION.get(url, timeout=timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.debug("Retrying %s: %s", source_cfg["name"], e)
    logger.warning("HTML fetch failed (%s): %s", source_cfg["name"], last_error)
    return None


def _image_from_item(item, source_cfg: dict) -> str | None:
    """Per-article image, either from a CSS style or an <img> tag."""
    base = source_cfg["url"]
    style_sel = source_cfg.get("image_style_selector")
    if style_sel:
        el = item.select_one(style_sel)
        if el:
            match = re.search(
                source_cfg.get("image_style_regex", r"url\('([^']+)'\)"),
                el.get("style", "") or "",
            )
            if match and not _is_placeholder_image(match.group(1)):
                return match.group(1)

    img_sel = source_cfg.get("image_selector")
    if img_sel:
        img = item.select_one(img_sel)
        if img:
            src = img.get("src") or img.get("data-src") or ""
            src = _absolute(base, src)
            if src.startswith("http") and not _is_placeholder_image(src):
                return src
    return None


def _absolute(base: str, url: str) -> str:
    """Resolve a relative href/src against the page it was found on."""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    return urljoin(base, url)


def _clean_title(text: str, source_cfg: dict) -> str:
    """Strip dates and view counters glued to headline text.

    Minpromtorg writes "19.10.2026 Заголовок", Rusmet writes
    "19 октября 2026 180 Заголовок". Without this the post would start with
    a date and a view count.
    """
    pattern = source_cfg.get("title_strip_regex")
    if pattern:
        text = re.sub(pattern, "", text, count=1)
    return text.strip()


def _link_matches(url: str, source_cfg: dict) -> bool:
    """Reject navigation links that sit next to real articles.

    Listings carry "Все новости раздела" anchors alongside stories, and a
    substring test alone cannot tell them apart from an article URL.
    """
    contains = source_cfg.get("link_contains")
    if contains and contains not in url:
        return False
    pattern = source_cfg.get("link_regex")
    if pattern and not re.search(pattern, url):
        return False
    return True


def _parse_html_block(source_cfg: dict, soup: BeautifulSoup) -> list[Article]:
    """Item containers, each with title link and an optional description.

    Used by MetallurgProm: every news item is a div.news-item holding its
    headline anchor and a div.entry-content-index with the teaser text.
    """
    articles = []
    require_keyword = source_cfg.get("require_keyword", False)
    title_sel = source_cfg.get("title_selector", "h3 a[href]")
    desc_sel = source_cfg.get("desc_selector")

    for item in soup.select(source_cfg["item_selector"])[:FEED_SCAN_LIMIT]:
        link_el = item.select_one(title_sel)
        if not link_el or not link_el.get("href"):
            continue
        url = _absolute(source_cfg["url"], link_el["href"])
        if not _link_matches(url, source_cfg):
            continue
        title = _clean_title(link_el.get_text(" ", strip=True), source_cfg)
        desc = ""
        if desc_sel:
            desc_el = item.select_one(desc_sel)
            if desc_el:
                desc = desc_el.get_text(" ", strip=True)
        if not title:
            continue
        if require_keyword and not _is_relevant(title, source_cfg):
            continue
        articles.append(
            Article(
                title=title,
                url=url,
                description=desc,
                source=source_cfg["name"],
                image_url=_image_from_item(item, source_cfg),
                lang=source_cfg["lang"],
            )
        )
        if len(articles) >= PER_HTML_LIMIT:
            break
    return articles


def _parse_html_pairs(source_cfg: dict, soup: BeautifulSoup) -> list[Article]:
    """Title links and description links that share the same href.

    Used by Metal Bulletin: each story appears twice - once as the headline
    anchor (a.mainnews / a.news) and once wrapped around the teaser text
    (a.normal_news). Both point at the same article URL, so pair them by href.
    """
    articles = []
    require_keyword = source_cfg.get("require_keyword", False)

    titles = {}
    for a in soup.select(source_cfg["title_selector"]):
        href = _absolute(source_cfg["url"], a.get("href") or "")
        if not _link_matches(href, source_cfg):
            continue
        text = _clean_title(a.get_text(" ", strip=True), source_cfg)
        if len(text) >= 20:
            titles.setdefault(href, text)

    descs = {}
    for a in soup.select(source_cfg["desc_selector"]):
        href = _absolute(source_cfg["url"], a.get("href") or "")
        if not _link_matches(href, source_cfg):
            continue
        text = a.get_text(" ", strip=True)
        if len(text) >= 20:
            descs.setdefault(href, text)

    for href, title in titles.items():
        desc = descs.get(href, "")
        if require_keyword and not _is_relevant(title, source_cfg):
            continue
        articles.append(
            Article(
                title=title,
                url=href,
                description=desc,
                source=source_cfg["name"],
                image_url=None,
                lang=source_cfg["lang"],
            )
        )
        if len(articles) >= PER_HTML_LIMIT:
            break
    return articles


def _parse_html_list(source_cfg: dict, soup: BeautifulSoup) -> list[Article]:
    """Headline links listed directly, with no container element.

    Minpromtorg renders its news as a flat list of anchors, so there is no
    per-item block to select.
    """
    articles = []
    require_keyword = source_cfg.get("require_keyword", False)
    seen: set[str] = set()
    for a in soup.select(source_cfg["title_selector"]):
        url = _absolute(source_cfg["url"], a.get("href") or "")
        if not url or url in seen or not _link_matches(url, source_cfg):
            continue
        title = _clean_title(a.get_text(" ", strip=True), source_cfg)
        if len(title) < 20:
            continue
        if require_keyword and not _is_relevant(title, source_cfg):
            continue
        seen.add(url)
        articles.append(
            Article(
                title=title,
                url=url,
                description="",
                source=source_cfg["name"],
                image_url=_image_from_item(a, source_cfg),
                lang=source_cfg["lang"],
            )
        )
        if len(articles) >= PER_HTML_LIMIT:
            break
    return articles


def _parse_html(source_key: str, source_cfg: dict) -> list[Article]:
    try:
        soup = _html_fetch(source_cfg)
        if soup is None:
            return []
        mode = source_cfg.get("mode", "block")
        if mode == "pairs":
            return _parse_html_pairs(source_cfg, soup)
        if mode == "list":
            return _parse_html_list(source_cfg, soup)
        return _parse_html_block(source_cfg, soup)
    except Exception as e:
        logger.warning("HTML parse error for %s (%s): %s", source_key, source_cfg["name"], e)
    return []


def _dedupe_similar(articles: list[Article]) -> list[Article]:
    """Drop the same story republished by several sources.

    MetalTorg, Metal Bulletin and MetallurgProm all carry the same mill
    press releases, and posting "ОЭМК отказался от иска" twice in one run
    looks broken. Keep the variant with the longer teaser so the post has
    real text.
    """
    kept: list[Article] = []
    for article in articles:
        title = article.title.lower()
        match = None
        for existing in kept:
            if SequenceMatcher(None, title, existing.title.lower()).ratio() >= 0.9:
                match = existing
                break
        if match is None:
            kept.append(article)
        elif len(article.description) > len(match.description):
            for i, existing in enumerate(kept):
                if existing is match:
                    kept[i] = article
                    break
    return kept


def collect_news() -> list[Article]:
    all_articles: list[Article] = []
    seen_urls: set[str] = set()

    for key, cfg in config.NEWS_SOURCES.items():
        logger.info("Fetching: %s (%s)", cfg["name"], key)
        parser = _parse_html if cfg.get("type") == "html" else _parse_rss
        for article in parser(key, cfg):
            if article.url and article.url not in seen_urls:
                seen_urls.add(article.url)
                all_articles.append(article)

    if getattr(config, "GEO_FILTER", False):
        before = len(all_articles)
        # Sources that mix in a lot of world-market copy only pass stories
        # that explicitly name RF/CIS; a neutral headline from them is more
        # likely a Chilean mine than a Russian mill.
        strict = {
            cfg["name"]
            for cfg in config.NEWS_SOURCES.values()
            if cfg.get("require_geo")
        }
        ranked = []
        for a in all_articles:
            rank = _geo_rank(a.title, a.description)
            if rank < 0:
                continue
            if rank == 0 and a.source in strict:
                continue
            ranked.append((a, rank))
        # RF/CIS headlines go first so a limited run never leads with a
        # neutral market piece while Astana or Chelyabinsk news waits.
        ranked.sort(key=lambda pair: -pair[1])
        all_articles = [a for a, _ in ranked]
        logger.info(
            "Geo filter (RF/CIS): kept %d of %d, %d regional",
            len(all_articles),
            before,
            sum(1 for _, r in ranked if r == 1),
        )

    all_articles = _dedupe_similar(all_articles)
    logger.info("Collected %d unique articles", len(all_articles))

    for article in all_articles[:]:
        if not article.image_url:
            img = _fetch_image_from_page(article.url)
            if img:
                article.image_url = img

    return all_articles
