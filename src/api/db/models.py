import json
import time

from src.api.db.connection import get_db


def import_catalog():
    from src.core import cache as cache_mod
    cat = cache_mod.load_catalog()
    conn = get_db()
    cur = conn.cursor()
    count = 0
    for entry in cat:
        title = entry.get("title", "")
        slug = entry.get("slug", "") or entry.get("link", "").rstrip("/").split("/")[-1]
        source = entry.get("source", "catalog")
        link = entry.get("link", "")
        genres = json.dumps(entry.get("genres", []))
        alt_source = json.dumps(entry.get("alt_source", []))
        try:
            cur.execute(
                "INSERT OR IGNORE INTO anime (title, slug, source, link, genres, alt_source) VALUES (?, ?, ?, ?, ?, ?)",
                (title, slug, source, link, genres, alt_source),
            )
            count += cur.rowcount
        except Exception:
            pass
    conn.commit()
    conn.close()
    return count


def get_anime_episodes(anime_title=None, slug=None, source=None):
    conn = get_db()
    cur = conn.cursor()
    if slug and source:
        cur.execute(
            "SELECT id FROM anime WHERE slug = ? AND source = ?",
            (slug, source),
        )
    elif anime_title:
        cur.execute(
            "SELECT id FROM anime WHERE title LIKE ? LIMIT 1",
            (f"%{anime_title}%",),
        )
    else:
        conn.close()
        return None

    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    anime_id = row["id"]
    cur.execute(
        "SELECT number, url, resolved_url, resolved_type, lang, season FROM episodes WHERE anime_id = ? ORDER BY number",
        (anime_id,),
    )
    eps = [dict(e) for e in cur.fetchall()]
    conn.close()
    return eps if eps else []


def save_episodes(anime_title, slug, source, episodes):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM anime WHERE slug = ? AND source = ?", (slug, source))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO anime (title, slug, source) VALUES (?, ?, ?)",
            (anime_title, slug, source),
        )
        anime_id = cur.lastrowid
    else:
        anime_id = row["id"]

    now = time.time()
    for ep in episodes:
        num = ep.get("number", 0)
        url = ep.get("url", "")
        resolved = ep.get("resolved", "")
        rtype = ep.get("resolved_type", "")
        lang = ep.get("lang", "vostfr")
        season = ep.get("season", "")
        cur.execute(
            "INSERT OR REPLACE INTO episodes (anime_id, number, url, resolved_url, resolved_type, lang, season, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (anime_id, num, url, resolved, rtype, lang, season, now),
        )
    conn.commit()
    conn.close()
    return len(episodes)


def get_indexed_count():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as c FROM anime").fetchone()
    indexed = row["c"] if row else 0
    row2 = conn.execute("SELECT COUNT(DISTINCT anime_id) as c FROM episodes").fetchone()
    with_eps = row2["c"] if row2 else 0
    conn.close()
    return indexed, with_eps
