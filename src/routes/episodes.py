import logging
import time

from src.helpers import (send_json, send_internal_error, is_safe_external_url,
                         playwright_available)
from src.db.models import get_anime_episodes, save_episodes
from src import fast_engine
from anisama import cache as cache_mod

logger = logging.getLogger("anisama-api")


def handle(handler, params):
    source = (params.get("source", [None])[0] or "").strip()
    slug = (params.get("slug", [None])[0] or "").strip()
    url = (params.get("url", [None])[0] or "").strip()
    season = 1
    try:
        season = max(1, int((params.get("season", ["1"])[0] or "1")))
    except ValueError:
        pass

    if not source:
        send_json(handler, {"error": "Missing 'source'"}, 400)
        return
    if source == "catalog":
        source = "anime-sama"
    if url and not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return
    if source in ("myfluneo", "animoflix") and not playwright_available():
        logger.warning("Episodes: source %s indisponible (Playwright absent)", source)
        send_json(handler, {"error": "source_unavailable", "source": source}, 501)
        return

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

    # ── Fast path : moteur anime_engine (embeds directs, zéro bs4/playwright) ──
    if fast_engine.enabled() and source in ("anime-sama", "franime"):
        try:
            t0 = time.time()
            episodes = fast_engine.fast_episodes(source, slug, url or None,
                                                 season=season if source == "franime" else 1)
            if episodes:
                title = slug.replace("-", " ").title()
                for e in cache_mod.load_catalog():
                    if e.get("slug", "").lower() == slug.lower():
                        title = e.get("title", title)
                        break
                save_episodes(title, slug, source, episodes)
                numbers = [{"number": e["number"],
                            "season": e.get("season", ""),
                            "lang": e.get("lang", "vostfr")} for e in episodes]
                logger.info("  -> Fast engine: %d episodes en %.2fs", len(numbers), time.time() - t0)
                send_json(handler, {"source": source, "slug": slug, "total": len(numbers),
                            "episodes": numbers, "cached": False, "engine": True})
                return
            logger.info("  -> Fast engine: 0 episode, fallback pipeline historique")
        except Exception as exc:
            logger.warning("  -> Fast engine KO (%s), fallback pipeline historique", exc)

    # ── Pipeline historique ──
    try:
        if source == "anime-sama":
            episodes = _ep_animesama(url, slug)
        elif source == "myfluneo":
            episodes = _ep_myfluneo(url or "https://myfluneo.eu/anime/{s}".format(s=slug))
        elif source == "voiranime":
            episodes = _ep_voiranime(url, slug)
        elif source == "animesultra":
            episodes = _ep_animesultra(url)
        elif source == "frenchanime":
            episodes = _ep_frenchanime(url)
        elif source == "animoflix":
            episodes = _ep_animoflix(url)
        elif source == "franime":
            episodes = _ep_franime(url, slug)
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
        send_internal_error(handler, e, logger, "episodes")


_NON_ANIME_SEASON_HINTS = ("/scan", "scan_", "/manhwa", "/webtoon", "/manhua",
                           "/manga", "/novel", "/light-novel")


def _ep_animesama(url, slug=None):
    from anisama.scraper.base import find_active_domain
    from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
    if not url:
        domain = find_active_domain()
        if not domain or not slug:
            return []
        url = "https://{d}/catalogue/{s}/".format(d=domain, s=slug)
    seasons = get_anime_seasons(url)
    all_eps = []
    abs_offset = 0
    for season in seasons:
        # Le catalogue expose aussi les scans/one-shots : on ne les compte pas
        # dans la numérotation des épisodes.
        if any(h in (season.get("url") or "").lower() for h in _NON_ANIME_SEASON_HINTS):
            continue
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


def _ep_voiranime(url, slug=None):
    """Saisons (« sagas ») puis épisodes. Les numéros sont déjà globaux."""
    from anisama.scraper.voiranime import voiranime_get_seasons, voiranime_get_episodes
    if not url:
        if not slug:
            return []
        # Le site a migré de /anime/<slug> vers /<slug>/.
        url = "https://voiranime.rip/{s}/".format(s=slug)
    seasons = voiranime_get_seasons(url)
    by_number = {}
    for season in seasons[:40]:
        for e in voiranime_get_episodes(season["url"]):
            number = e.get("number")
            if not number or number in by_number:
                continue
            by_number[number] = {
                "number": number,
                "season": season.get("name", ""),
                "url": e.get("url", ""),
                "langs": sorted(e.get("langs", [])),
            }
    return [by_number[n] for n in sorted(by_number)]


def _ep_animesultra(url):
    from anisama.scraper.animesultra import animesultra_episodes
    return animesultra_episodes(url)


def _ep_frenchanime(url):
    from anisama.scraper.frenchanime import frenchanime_episodes
    return frenchanime_episodes(url)


def _ep_animoflix(url):
    from anisama.scraper.animoflix import animoflix_episodes
    return animoflix_episodes(url)


def _ep_franime(url, slug):
    from anisama.scraper.franime import franime_episodes
    base = url or "franime://{s}/1/1".format(s=slug)
    return franime_episodes(base)
