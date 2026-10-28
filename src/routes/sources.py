import os

from src.helpers import send_json, playwright_available
from src.db.models import get_indexed_count
from anisama import cache as cache_mod

# Sources advertised by the API. A source is only listed when it can actually
# serve requests: MyFluneo / AnimoFlix need Playwright. Voiranime is enabled by
# default (new /<slug>/ URL scheme) and can be hidden with
# ANISAMA_ENABLE_VOIRANIME=0.
SOURCE_DEFS = (
    {"id": "anime-sama", "name": "Anime-Sama", "url": "https://anime-sama.to"},
    {"id": "myfluneo", "name": "MyFluneo", "url": "https://myfluneo.eu"},
    {"id": "voiranime", "name": "Voiranime", "url": "https://voiranime.rip"},
    {"id": "franime", "name": "FRAnime", "url": "https://franime.fr"},
    {"id": "animesultra", "name": "AnimesUltra", "url": "https://ww.animesultra.org"},
    {"id": "frenchanime", "name": "French-Anime", "url": "https://french-anime.com"},
    {"id": "animoflix", "name": "AnimoFlix", "url": "https://animoflix.to"},
)


def source_available(source_id):
    if source_id in ("myfluneo", "animoflix"):
        return playwright_available()
    if source_id == "voiranime":
        return (os.environ.get("ANISAMA_ENABLE_VOIRANIME") or "1").strip() != "0"
    return True


def advertised_sources():
    return [dict(d) for d in SOURCE_DEFS if source_available(d["id"])]


def handle(handler, _params):
    cat = cache_mod.load_catalog()
    indexed, with_eps = get_indexed_count()
    src_counts = {}
    for e in cat:
        s = e.get("source", "catalog")
        src_counts[s] = src_counts.get(s, 0) + 1
        for a in e.get("alt_source", []):
            src_counts[f"alt:{a}"] = src_counts.get(f"alt:{a}", 0) + 1

    sources = []
    for d in advertised_sources():
        if d["id"] == "anime-sama":
            count = src_counts.get("catalog", 0) + src_counts.get("alt:anime-sama", 0)
        else:
            count = src_counts.get(d["id"], 0) + src_counts.get(f"alt:{d['id']}", 0)
        sources.append({**d, "count": count})

    send_json(handler, {"sources": sources, "total": len(cat), "indexed": indexed, "with_episodes": with_eps})
