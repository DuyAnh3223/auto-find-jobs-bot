import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from monitor.core import Post, Settings, content_hash, now_iso


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
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS scan_checks (
                    group_url TEXT PRIMARY KEY, group_name TEXT NOT NULL,
                    checked_at TEXT NOT NULL, severity TEXT NOT NULL,
                    reason TEXT NOT NULL, read_count INTEGER,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1);
            """)
            # Retire only legacy limit-only warnings, preserving actual reading errors.
            db.execute("""UPDATE scan_checks SET resolved=1
                WHERE severity='warning' AND reason IN (?, ?)""", (
                "Chạm giới hạn bài; có thể còn bài phía dưới",
                "Hết lượt cuộn; chưa xác nhận đã đọc hết",
            ))
            columns = {row[1] for row in db.execute("PRAGMA table_info(posts)")}
            for name, definition in {
                "content_hash": "TEXT NOT NULL DEFAULT ''",
                "bot_status": "TEXT NOT NULL DEFAULT 'suitable'",
                "user_decision": "TEXT",
            }.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE posts ADD COLUMN {name} {definition}")
            db.execute("CREATE INDEX IF NOT EXISTS posts_content_hash ON posts(content_hash)")
            # Backfill hashes for databases created by the original V1.
            for row in db.execute(
                "SELECT id, content FROM posts WHERE content_hash='' OR content_hash IS NULL"
            ).fetchall():
                db.execute("UPDATE posts SET content_hash=? WHERE id=?", (content_hash(row[1]), row[0]))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_scan_check(self, group, severity, reason, read_count=None):
        with self.connect() as db:
            if severity == "info":
                # A successful bounded read clears its pending marker, not old unreviewed errors.
                db.execute("UPDATE scan_checks SET resolved=1 WHERE group_url=? AND severity='pending'",
                           (group.url,))
                return
            db.execute("""INSERT INTO scan_checks
                (group_url, group_name, checked_at, severity, reason, read_count)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(group_url) DO UPDATE SET
                group_name=excluded.group_name, checked_at=excluded.checked_at,
                severity=excluded.severity, reason=excluded.reason,
                read_count=excluded.read_count, resolved=0, revision=scan_checks.revision+1
                WHERE excluded.severity != 'pending' OR scan_checks.resolved=1
                """, (group.url, group.name, now_iso(), severity, reason, read_count))

    def scan_checks(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM scan_checks WHERE resolved=0 ORDER BY checked_at DESC, group_name"
            )]

    def resolve_scan_check(self, url, revision):
        with self.connect() as db:
            db.execute("UPDATE scan_checks SET resolved=1 WHERE group_url=? AND revision=?",
                       (url, revision))

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
        digest = post.content_hash or content_hash(post.content)
        with self.connect() as db:
            old = db.execute(
                "SELECT content_hash, user_decision FROM posts WHERE url=?", (post.url,)
            ).fetchone()
            cursor = db.execute(
                """
                INSERT INTO posts (url,group_name,group_url,content,keywords,detected_at,
                    last_seen_at,posted_at,posted_time_raw,content_hash,bot_status,user_decision)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
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
                    digest,
                    post.bot_status,
                    None,
                ),
            )
            inserted = cursor.rowcount == 1
            if not inserted:
                # Preserve first detection, refresh edited content and current matches.
                decision = old[1] if old and old[0] == digest else None
                db.execute(
                    """UPDATE posts SET content=?, keywords=?, last_seen_at=?,
                    posted_at=COALESCE(?,posted_at), posted_time_raw=?, group_name=?,
                    content_hash=?, bot_status=?, user_decision=? WHERE url=?""",
                    (
                        post.content,
                        json.dumps(post.keywords, ensure_ascii=False),
                        now_iso(),
                        post.posted_at,
                        post.posted_time_raw,
                        post.group_name,
                        digest,
                        post.bot_status,
                        decision,
                        post.url,
                    ),
                )
        return inserted

    def set_user_decision(self, digest: str, decision: str | None):
        if decision not in {None, "suitable", "skipped"}:
            raise ValueError("Quyết định không hợp lệ")
        with self.connect() as db:
            db.execute("UPDATE posts SET user_decision=? WHERE content_hash=?", (decision, digest))

    @staticmethod
    def _effective_status(rows):
        decisions = {row["user_decision"] for row in rows if row["user_decision"]}
        if "skipped" in decisions:
            return "skipped"
        if "suitable" in decisions:
            return "suitable"
        statuses = {row["bot_status"] for row in rows}
        if "suitable" in statuses:
            return "suitable"
        if "review" in statuses:
            return "review"
        return "unsuitable"

    @staticmethod
    def _evaluation_status(rows):
        statuses = {row["bot_status"] for row in rows}
        if "suitable" in statuses:
            return "suitable"
        if "review" in statuses:
            return "review"
        return "unsuitable"

    def grouped_posts(self, search="", category="suitable", limit=None, offset=0):
        """Return one display/export row per exact content hash."""
        clause, params = self.search_clause(search)
        with self.connect() as db:
            raw = [
                dict(row)
                for row in db.execute(
                    f"SELECT * FROM posts {clause} ORDER BY detected_at DESC, id DESC", params
                ).fetchall()
            ]
        groups = {}
        for row in raw:
            groups.setdefault(row["content_hash"] or content_hash(row["content"]), []).append(row)
        result = []
        for digest, rows in groups.items():
            status = self._effective_status(rows)
            if category != "all" and status != category:
                continue
            first = rows[0].copy()
            first["id"] = digest
            first["content_hash"] = digest
            first["status"] = status
            first["evaluation"] = self._evaluation_status(rows)
            first["user_decision"] = "skipped" if status == "skipped" else None
            first["group_name"] = ", ".join(dict.fromkeys(row["group_name"] for row in rows))
            first["group_url"] = rows[0]["group_url"]
            first["source_group_urls"] = [row["group_url"] for row in rows]
            first["url"] = rows[0]["url"]
            first["source_urls"] = [row["url"] for row in rows]
            first["source_groups"] = [row["group_name"] for row in rows]
            keywords = []
            for row in rows:
                for keyword in json.loads(row["keywords"]):
                    if keyword not in keywords:
                        keywords.append(keyword)
            first["keywords"] = json.dumps(keywords, ensure_ascii=False)
            result.append(first)
        result.sort(key=lambda row: (row["detected_at"], row["id"]), reverse=True)
        from monitor.tracking import source_key

        applications = self.applications()
        with self.connect() as db:
            known_sources = {
                source_key(row["url"]): row["content_hash"]
                for row in db.execute("SELECT url,content_hash FROM posts")
            }
        for row in result:
            urls = {source_key(url) for url in row["source_urls"]}
            linked = [
                app
                for app in applications
                if app.get("source_url")
                and (
                    source_key(app["source_url"]) in urls
                    or known_sources.get(source_key(app["source_url"])) == row["content_hash"]
                )
            ]
            row["application_ids"] = [app["id"] for app in linked]
            row["application_status"] = " / ".join(dict.fromkeys(app["status"] for app in linked))
            row["processing"] = (
                "skipped" if row["user_decision"] == "skipped" else "tracked" if linked else "unprocessed"
            )
        return result[offset : offset + limit] if limit is not None else result

    def grouped_count(self, search="", category="suitable"):
        return len(self.grouped_posts(search, category))

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

    def save_application(self, value, application_id=None):
        from monitor.tracking import validate_application

        value = validate_application(value)
        timestamp = now_iso()
        with self.connect() as db:
            payload = json.dumps(value, ensure_ascii=False)
            if application_id is None:
                return db.execute(
                    "INSERT INTO applications(value,created_at,updated_at) VALUES (?,?,?)",
                    (payload, timestamp, timestamp),
                ).lastrowid
            cursor = db.execute(
                "UPDATE applications SET value=?, updated_at=? WHERE id=?",
                (payload, timestamp, application_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Hồ sơ không còn tồn tại. Hãy tải lại danh sách.")
        return application_id

    def applications(self):
        with self.connect() as db:
            return [
                {
                    **json.loads(row["value"]),
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in db.execute("SELECT * FROM applications ORDER BY updated_at DESC, id DESC")
            ]

    def delete_application(self, application_id):
        with self.connect() as db:
            db.execute("DELETE FROM applications WHERE id=?", (application_id,))

    def restore_application(self, application):
        """Restore a session-undo snapshot with its original identifier and timestamps."""
        from monitor.tracking import validate_application

        value = validate_application(application)
        with self.connect() as db:
            db.execute(
                "INSERT INTO applications(id,value,created_at,updated_at) VALUES (?,?,?,?)",
                (
                    application["id"],
                    json.dumps(value, ensure_ascii=False),
                    application["created_at"],
                    application["updated_at"],
                ),
            )
