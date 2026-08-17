import logging

from src.helpers import send_json
from src.db.models import get_anime_episodes, save_episodes
from anisama import cache as cache_mod

logger = logging.getLogger("anisama-api")


def handle(handler, params):
    source = (params.get("source", [None])[0] or "").strip()
    slug = (params.get("slug", [None])[0] or "").strip()
    url = (params.get("url", [None])[0] or "").strip()

    if not source:
        send_json(handler, {"error": "Missing 'source'"}, 400)
        return
    if source == "catalog":
        source = "anime-sama"

    logger.info("Episodes: source=%s slug=%s", source, slug)

    eps = get_anime_episodes(slug=slug, source=source)
    if eps is not None and len(eps) > 0:
        logger.info("  -> Cache HIT (%d episodes)", len(eps))
        numbers = [{"number": e.get("number", e.get("id", i+1)),
                    "season": e.get("season", ""),
                    "lang": e.get("lang", "vostfr")} for i, e in enumerate(eps)]
        send_json(handler, {"source": source, "slug": slug, "total": len(numbers),
                    "episodes": numbers, "cached": True})
        return

    logger.info("  -> Cache MISS, fetching episode list...")
    try:
        if source == "anime-sama":
            episodes = _ep_animesama(url or "https://anime-sama.to/catalogue/{s}/".format(s=slug))
        elif source == "myfluneo":
            episodes = _ep_myfluneo(url or "https://myfluneo.eu/anime/{s}".format(s=slug))
        elif source == "voiranime":
            episodes = _ep_voiranime(url)
        elif source == "animesultra":
            episodes = _ep_animesultra(url)
        elif source == "frenchanime":
            episodes = _ep_frenchanime(url)
        elif source == "animoflix":
            episodes = _ep_animoflix(url)
        else:
            send_json(handler, {"error": "Unknown source: {s}".format(s=source)}, 400)
            return

        if episodes:
            title = slug.replace("-", " ").title()
            for e in cache_mod.load_catalog():
                if e.get("slug", "").lower() == slug.lower():
                    title = e.get("title", title)
                    break
            save_episodes(title, slug, source, episodes)

        numbers = [{"number": e.get("number", i+1),
                    "season": e.get("season", ""),
                    "lang": e.get("lang", "vostfr")} for i, e in enumerate(episodes)]

        send_json(handler, {"source": source, "slug": slug, "total": len(numbers),
                    "episodes": numbers, "cached": False})

    except Exception as e:
        logger.error("Episode fetch error: %s", e)
        send_json(handler, {"error": str(e), "source": source, "slug": slug}, 500)


def _ep_animesama(url):
    from anisama.scraper.base import find_active_domain
    from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
    domain = find_active_domain()
    if not domain:
        return []
    seasons = get_anime_seasons(url)
    all_eps = []
    abs_offset = 0
    for season in seasons:
        eps = get_episodes(season["url"])
        for e in eps:
            all_eps.append({
                "number": abs_offset + e["number"],
                "season": season.get("name", ""),
                "url": e.get("url", ""),
                "mirrors": list(e.get("mirrors", {}).values()),
            })
        abs_offset += len(eps)
    return all_eps


def _ep_myfluneo(url):
    from anisama.scraper.myfluneo import myfluneo_episodes
    return myfluneo_episodes(url)


def _ep_voiranime(url):
    from anisama.scraper.voiranime import voiranime_get_seasons, voiranime_get_episodes
    seasons = voiranime_get_seasons(url)
    all_eps = []
    for season in seasons[:3]:
        eps = voiranime_get_episodes(season["url"])
        for e in eps:
            all_eps.append({
                "number": e["number"],
                "season": season.get("name", ""),
                "url": e["url"],
                "langs": list(e.get("langs", [])),
            })
    return all_eps


def _ep_animesultra(url):
    from anisama.scraper.animesultra import animesultra_episodes
    return animesultra_episodes(url)


def _ep_frenchanime(url):
    from anisama.scraper.frenchanime import frenchanime_episodes
    return frenchanime_episodes(url)


def _ep_animoflix(url):
    from anisama.scraper.animoflix import animoflix_episodes
    return animoflix_episodes(url)
