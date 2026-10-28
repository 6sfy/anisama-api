import re
from collections import Counter

from src.helpers import send_json, source_counts
from src.db.models import get_indexed_count
from anisama import cache as cache_mod

_FORMAT_GENRES = {
    "anime",
    "animes",
    "film",
    "films",
    "scan",
    "scans",
    "voirdrama",
    "top anime",
    "top animes",
    "manga",
    "manhwa",
    "manhua",
    "webtoon",
}


def _entry_genres(entry):
    raw = entry.get("genres")
    if not raw:
        raw = entry.get("genre")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set)):
        return []

    genres = []
    for value in raw:
        for part in re.split(r"[,/;]", str(value)):
            name = part.strip()
            if name and name.lower() not in _FORMAT_GENRES:
                genres.append(name)
    return genres


def handle(handler, _params):
    cat = cache_mod.load_catalog()
    indexed, _with_eps = get_indexed_count()
    src_counts = source_counts(cat)

    genre_counts = Counter()
    lang_counts = Counter()
    years = []

    for e in cat:
        for g in _entry_genres(e):
            genre_counts[g] += 1

        title = e.get("title", "")
        if title.lower().endswith(" vf"):
            lang_counts["vf"] += 1
        elif title.lower().endswith(" vostfr"):
            lang_counts["vostfr"] += 1
        else:
            lang_counts["vostfr"] += 1  # default

        yr = e.get("year", "")
        if yr and str(yr).isdigit():
            years.append(int(yr))

    top_genres = [{"name": name, "count": count} for name, count in genre_counts.most_common(15)]

    year_range = {}
    if years:
        year_range = {"min": min(years), "max": max(years)}

    source_total = sum(src_counts.values()) or 1
    by_source = {
        src: {
            "count": count,
            "percentage": round(count * 100 / source_total, 1),
        }
        for src, count in src_counts.most_common()
    }

    send_json(handler, {
        "total": len(cat),
        "indexed": indexed,
        "by_source": by_source,
        "top_genres": top_genres,
        "languages": dict(lang_counts.most_common()),
        "year_range": year_range,
    })
