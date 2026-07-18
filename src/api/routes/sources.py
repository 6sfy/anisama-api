from src.api.utils.http import send_json
from src.api.db.models import get_indexed_count
from src.core import cache as cache_mod


def handle(handler, _params):
    cat = cache_mod.load_catalog()
    indexed, with_eps = get_indexed_count()
    src_counts = {}
    for e in cat:
        s = e.get("source", "catalog")
        src_counts[s] = src_counts.get(s, 0) + 1
        for a in e.get("alt_source", []):
            src_counts[f"alt:{a}"] = src_counts.get(f"alt:{a}", 0) + 1

    sources = [
        {"id": "anime-sama", "name": "Anime-Sama", "count": src_counts.get("catalog", 0), "url": "https://anime-sama.to"},
        {"id": "myfluneo", "name": "MyFluneo", "count": src_counts.get("myfluneo", 0) + src_counts.get("alt:myfluneo", 0), "url": "https://myfluneo.eu"},
        {"id": "voiranime", "name": "Voiranime", "count": src_counts.get("voiranime", 0) + src_counts.get("alt:voiranime", 0), "url": "https://voiranime.rip"},
        {"id": "animesultra", "name": "AnimesUltra", "count": src_counts.get("animesultra", 0) + src_counts.get("alt:animesultra", 0), "url": "https://ww.animesultra.org"},
        {"id": "frenchanime", "name": "French-Anime", "count": src_counts.get("frenchanime", 0) + src_counts.get("alt:frenchanime", 0), "url": "https://french-anime.com"},
        {"id": "animoflix", "name": "AnimoFlix", "count": src_counts.get("animoflix", 0) + src_counts.get("alt:animoflix", 0), "url": "https://animoflix.to"},
    ]
    send_json(handler, {"sources": sources, "total": len(cat), "indexed": indexed, "with_episodes": with_eps})
