import sqlite3
import datetime


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

    def is_posted(self, url: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM posted_articles WHERE url = ?", (url,)
        ).fetchone()
        conn.close()
        return row is not None

    def mark_posted(self, url: str, title: str):
        conn = self._get_conn()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO posted_articles (url, title, posted_at) VALUES (?, ?, ?)",
            (url, title, now),
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
