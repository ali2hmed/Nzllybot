"""A small SQLite file (bot.db) for user languages and already-sent posts."""

import json
import sqlite3


class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sent (
                key TEXT PRIMARY KEY,
                data TEXT NOT NULL
            );
        """)

    def get_lang(self, user_id):
        row = self.conn.execute("SELECT lang FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None

    def set_lang(self, user_id, lang):
        with self.conn:
            self.conn.execute(
                "INSERT INTO users VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET lang = excluded.lang",
                (user_id, lang),
            )

    def get_sent(self, key):
        """Telegram file ids of a post we already uploaded once."""
        row = self.conn.execute("SELECT data FROM sent WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_sent(self, key, data):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO sent VALUES (?, ?)", (key, json.dumps(data)))
