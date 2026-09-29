import sqlite3
import datetime
import difflib
import re

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "has",
    "have", "had", "do", "does", "did", "will", "would", "can", "could", "may",
    "might", "that", "this", "it", "its", "new", "study", "studies", "scientists",
    "research", "says", "say", "said", "how", "what", "why", "more", "than",
    "и", "в", "на", "с", "по", "для", "от", "из", "до", "за", "о", "об", "при",
    "про", "что", "как", "так", "это", "этот", "уже", "еще", "ещё", "не", "но",
    "новый", "новая", "ученые", "учёные", "исследование", "изучение", "сказал",
}


def _title_words(title: str) -> set[str]:
    """Lowercase content words, used to spot retold headlines."""
    text = re.sub(r"<[^>]+>", " ", title.lower())
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return {w for w in text.split() if len(w) > 3 and w not in STOPWORDS}


def _text_ratio(a: str, b: str) -> float:
    """Character-level similarity, robust to word order and punctuation."""
    def norm(t: str) -> str:
        t = t.lower()
        t = "".join(ch if ch.isalnum() else " " for ch in t)
        return " ".join(t.split())

    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posted_articles (
                url TEXT PRIMARY KEY,
                title TEXT,
                posted_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def canonical_url(url: str) -> str:
        """Strip tracking noise so the same article hashes to one key.

        Feeds append utm_* campaign parameters, so the same story reached via
        two links looked like two different articles and got posted twice.
        """
        if not url:
            return ""
        url = url.strip()
        url = re.sub(r"[?&](utm_[^&]+|yclid|gclid|fbclid|_openstat|ref)=[^&]*", "", url, flags=re.I)
        url = re.sub(r"[?&]$", "", url)
        url = re.sub(r"[?&]{2,}", "?", url)
        return url.rstrip("?&/").lower()

    def is_posted(self, url: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM posted_articles WHERE url = ?", (self.canonical_url(url),)
        ).fetchone()
        conn.close()
        return row is not None

    def is_duplicate_title(self, title: str) -> bool:
        """Catch the same story republished under a different headline.

        No single text-similarity score separates a retelling from an unrelated
        story: "Researchers create a battery that charges in a minute" and
        "New battery prototype recharges in under 60 seconds" share almost no
        words. So require either a strong character-level match or a high
        share of shared content words, each tuned against false positives from
        merely related articles.
        """
        words = _title_words(title)
        if len(words) < 3:
            return False

        conn = self._get_conn()
        rows = conn.execute("SELECT title FROM posted_articles").fetchall()
        conn.close()

        for row in rows:
            other_raw = row["title"] or ""
            other = _title_words(other_raw)
            if len(other) < 3:
                continue
            shared = len(words & other) / min(len(words), len(other))
            if shared >= 0.45:
                return True
            if _text_ratio(title, other_raw) >= 0.60:
                return True
        return False

    def mark_posted(self, url: str, title: str):
        conn = self._get_conn()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO posted_articles (url, title, posted_at) VALUES (?, ?, ?)",
            (self.canonical_url(url), title, now),
        )
        conn.commit()
        conn.close()

    def get_posted_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM posted_articles").fetchone()
        conn.close()
        return row["cnt"]

    def cleanup_old(self, days: int = 30):
        cutoff = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        ).isoformat()
        conn = self._get_conn()
        conn.execute("DELETE FROM posted_articles WHERE posted_at < ?", (cutoff,))
        conn.commit()
        conn.close()
