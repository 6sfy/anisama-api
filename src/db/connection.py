import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "anisama.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS anime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'catalog',
    link TEXT,
    genres TEXT,
    alt_source TEXT DEFAULT '[]',
    created_at REAL DEFAULT (unixepoch()),
    UNIQUE(slug, source)
);

CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anime_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    url TEXT,
    resolved_url TEXT,
    resolved_type TEXT DEFAULT '',
    resolved_referer TEXT DEFAULT '',
    resolved_at REAL,
    lang TEXT DEFAULT 'vostfr',
    season TEXT DEFAULT '',
    updated_at REAL DEFAULT (unixepoch()),
    UNIQUE(anime_id, number),
    FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_anime_source ON anime(source);
CREATE INDEX IF NOT EXISTS idx_anime_title ON anime(title);
CREATE INDEX IF NOT EXISTS idx_episodes_anime ON episodes(anime_id);
"""


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()
    conn.close()


def migrate(conn):
    """Apply lightweight schema migrations for pre-existing databases."""
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(episodes)").fetchall()]
        if cols and "resolved_referer" not in cols:
            conn.execute("ALTER TABLE episodes ADD COLUMN resolved_referer TEXT DEFAULT ''")
        if cols and "resolved_at" not in cols:
            conn.execute("ALTER TABLE episodes ADD COLUMN resolved_at REAL")
    except Exception:
        pass
