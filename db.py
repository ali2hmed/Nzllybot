"""A small SQLite file (bot.db) for user languages and already-sent posts."""

import json
import sqlite3
import time


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self._upgrade_users()
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                lang TEXT,  -- empty until they pick a language
                first_seen INTEGER NOT NULL DEFAULT 0,  -- Unix time; 0 = before stats were added
                last_seen INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS chats (  -- groups and channels the bot has been used in
                id INTEGER PRIMARY KEY,
                type TEXT, title TEXT,
                first_seen INTEGER NOT NULL, last_seen INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (  -- one row per download / countdown, for /stats
                time INTEGER NOT NULL, user_id INTEGER, kind TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_time ON events (time);
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS sent (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
        """)
        with self.conn:
            if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'users_old'").fetchone():
                self.conn.execute("INSERT OR IGNORE INTO users (id, lang) SELECT id, lang FROM users_old")
                self.conn.execute("DROP TABLE users_old")
            self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('stats_since', ?)", (str(int(time.time())),))
        self._seen = {}  # id -> when we last wrote last_seen

    def get_lang(self, user_id):
        row = self.conn.execute("SELECT lang FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None

    def set_lang(self, user_id, lang):
        now = int(time.time())
        with self.conn:
            self.conn.execute(
                "INSERT INTO users (id, lang, first_seen, last_seen) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET lang = excluded.lang",
                (user_id, lang, now, now),
            )

    # ---------- stats ----------

    def _upgrade_users(self):
        """bot.db files from before /stats had users(id, lang NOT NULL) only.
        Move them aside here; they're copied into the new table right after it's created."""
        columns = [row[1] for row in self.conn.execute("PRAGMA table_info(users)")]
        if columns and "first_seen" not in columns:
            with self.conn:
                self.conn.execute("ALTER TABLE users RENAME TO users_old")

    def _recently_seen(self, key, now):
        # Write at most once a minute per person or chat, not on every message.
        if now - self._seen.get(key, 0) < 60:
            return True
        self._seen[key] = now
        return False

    def seen_user(self, user_id):
        now = int(time.time())
        if self._recently_seen(user_id, now):
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO users (id, first_seen, last_seen) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET last_seen = excluded.last_seen",
                (user_id, now, now),
            )

    def seen_chat(self, chat_id, kind, title):
        now = int(time.time())
        if self._recently_seen(chat_id, now):
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO chats VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE "
                "SET type = excluded.type, title = excluded.title, last_seen = excluded.last_seen",
                (chat_id, kind, title, now, now),
            )

    def add_event(self, user_id, kind):
        with self.conn:
            self.conn.execute("INSERT INTO events VALUES (?, ?, ?)", (int(time.time()), user_id, kind))

    def stats(self):
        now = int(time.time())
        day, week = now - 86400, now - 7 * 86400

        def count(sql, *args):
            return self.conn.execute(sql, args).fetchone()[0]

        events = {}
        for kind, total, today, this_week in self.conn.execute(
            "SELECT kind, COUNT(*), SUM(time >= ?), SUM(time >= ?) FROM events GROUP BY kind", (day, week)
        ):
            events[kind] = (total, today, this_week)
        return {
            "users": count("SELECT COUNT(*) FROM users"),
            "new_day": count("SELECT COUNT(*) FROM users WHERE first_seen >= ?", day),
            "new_week": count("SELECT COUNT(*) FROM users WHERE first_seen >= ?", week),
            "active_day": count("SELECT COUNT(*) FROM users WHERE last_seen >= ?", day),
            "active_week": count("SELECT COUNT(*) FROM users WHERE last_seen >= ?", week),
            "ar": count("SELECT COUNT(*) FROM users WHERE lang = 'ar'"),
            "en": count("SELECT COUNT(*) FROM users WHERE lang = 'en'"),
            "groups": count("SELECT COUNT(*) FROM chats WHERE type IN ('group', 'supergroup')"),
            "channels": count("SELECT COUNT(*) FROM chats WHERE type = 'channel'"),
            "since": int(self.conn.execute("SELECT value FROM meta WHERE key = 'stats_since'").fetchone()[0]),
            "events": events,
        }

    def get_sent(self, key):
        """Telegram file ids of a post we already uploaded once."""
        row = self.conn.execute("SELECT data FROM sent WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_sent(self, key, data):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO sent VALUES (?, ?)", (key, json.dumps(data)))
