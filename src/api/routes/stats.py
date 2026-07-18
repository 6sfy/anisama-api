from collections import Counter

from src.api.utils.http import send_json
from src.api.db.models import get_indexed_count
from src.core import cache as cache_mod


def handle(handler, _params):
    cat = cache_mod.load_catalog()
    indexed, with_eps = get_indexed_count()

    src_counts = Counter()
    genre_counts = Counter()
    lang_counts = Counter()
    years = []

    for e in cat:
        raw = e.get("source", "catalog")
        src = "anime-sama" if raw == "catalog" else raw
        src_counts[src] += 1

        for g in e.get("genres", []):
            if g:
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

    by_source = {
        src: {
            "count": count,
            "percentage": round(count / len(cat) * 100, 1) if cat else 0,
        }
        for src, count in src_counts.most_common()
    }

    send_json(handler, {
        "total": len(cat),
        "indexed": indexed,
        "with_episodes": with_eps,
        "by_source": by_source,
        "top_genres": top_genres,
        "languages": dict(lang_counts.most_common()),
        "year_range": year_range,
    })
