import os

from src.helpers import send_json, playwright_available, source_counts
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
    indexed, _with_eps = get_indexed_count()
    counts = source_counts(cat)
    sources = [{**d, "count": counts.get(d["id"], 0)} for d in advertised_sources()]
    send_json(handler, {"sources": sources, "total": len(cat), "indexed": indexed})
