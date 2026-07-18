import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "anisama.db"

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
    conn.commit()
    conn.close()
