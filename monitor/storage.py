import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from monitor.core import Post, Settings, now_iso


class Store:
    """Short, per-operation connections: no SQLite connection crosses GUI/worker threads."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK(id = 1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    group_name TEXT NOT NULL,
                    group_url TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    posted_at TEXT,
                    posted_time_raw TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS posts_detected ON posts(detected_at DESC, id DESC);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def load_settings(self) -> Settings:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE id=1").fetchone()
        return Settings.from_dict(json.loads(row[0])) if row else Settings()

    def save_settings(self, settings: Settings):
        settings.validate()
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",
                (json.dumps(settings.to_dict(), ensure_ascii=False),),
            )

    def save_post(self, post: Post) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO posts (url,group_name,group_url,content,keywords,detected_at,
                    last_seen_at,posted_at,posted_time_raw) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(url) DO NOTHING
            """,
                (
                    post.url,
                    post.group_name,
                    post.group_url,
                    post.content,
                    json.dumps(post.keywords, ensure_ascii=False),
                    post.detected_at,
                    now_iso(),
                    post.posted_at,
                    post.posted_time_raw,
                ),
            )
            inserted = cursor.rowcount == 1
            if not inserted:
                # Preserve first detection, refresh edited content and current matches.
                db.execute(
                    """UPDATE posts SET content=?, keywords=?, last_seen_at=?,
                    posted_at=COALESCE(?,posted_at), posted_time_raw=?, group_name=? WHERE url=?""",
                    (
                        post.content,
                        json.dumps(post.keywords, ensure_ascii=False),
                        now_iso(),
                        post.posted_at,
                        post.posted_time_raw,
                        post.group_name,
                        post.url,
                    ),
                )
        return inserted

    @staticmethod
    def search_clause(search):
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return (
            (
                "WHERE content LIKE ? ESCAPE '\\' OR group_name LIKE ? ESCAPE '\\' "
                "OR keywords LIKE ? ESCAPE '\\'",
                [f"%{escaped}%"] * 3,
            )
            if search
            else ("", [])
        )

    def posts(self, search="", limit=None, offset=0):
        clause, params = self.search_clause(search)
        query = f"SELECT * FROM posts {clause} ORDER BY detected_at DESC, id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        with self.connect() as db:
            return [dict(r) for r in db.execute(query, params).fetchall()]

    def count(self, search=""):
        clause, params = self.search_clause(search)
        with self.connect() as db:
            return db.execute(f"SELECT count(*) FROM posts {clause}", params).fetchone()[0]
