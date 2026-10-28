"""Endpoints exposant directement le moteur anime_engine.

    GET /api/v2/seasons?source=SOURCE&slug=SLUG    saisons (moteur)
    GET /api/v2/hosts?slug=SLUG&season_url=URL     hôtes d'une saison anime-sama
    GET /api/v2/engine                             état du fast engine
"""

import logging
import time

from src.helpers import send_json, send_internal_error, is_safe_external_url
from src import fast_engine

logger = logging.getLogger("anisama-api")


def handle_seasons(handler, params):
    source = (params.get("source", ["anime-sama"])[0] or "anime-sama").strip()
    slug = (params.get("slug", [None])[0] or "").strip()

    if not slug:
        send_json(handler, {"error": "Missing 'slug'"}, 400)
        return
    if source not in ("anime-sama", "franime", "voiranime"):
        send_json(handler, {"error": "Unknown source: {s}".format(s=source)}, 400)
        return

    try:
        t0 = time.time()
        if source == "voiranime":
            from anisama.scraper.voiranime import voiranime_get_seasons
            seasons = [
                {"name": s.get("name", ""), "url": s.get("url", ""),
                 "langs": sorted(s.get("langs", []))}
                for s in voiranime_get_seasons("https://voiranime.rip/{s}/".format(s=slug))
            ]
        else:
            seasons = fast_engine.fast_seasons(source, slug)
        logger.info("Seasons: %s/%s -> %d (%.2fs)", source, slug, len(seasons), time.time() - t0)
        send_json(handler, {"source": source, "slug": slug, "total": len(seasons),
                    "seasons": seasons, "engine": source != "voiranime"})
    except Exception as exc:
        send_internal_error(handler, exc, logger, "seasons")


def handle_hosts(handler, params):
    slug = (params.get("slug", [None])[0] or "").strip()
    season_url = (params.get("season_url", [None])[0] or "").strip()

    if not slug:
        send_json(handler, {"error": "Missing 'slug'"}, 400)
        return
    if season_url and not is_safe_external_url(season_url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return

    try:
        hosts = fast_engine.fast_hosts(slug, season_url or None)
        send_json(handler, {"slug": slug, "hosts": hosts, "engine": True})
    except Exception as exc:
        send_internal_error(handler, exc, logger, "hosts")


def handle_health(handler, _params):
    """Liveness probe — ne touche ni au cache ni au réseau."""
    send_json(handler, {"status": "ok", "service": "anisama-api"})


def handle_status(handler, _params):
    send_json(handler, {
        "engine": "anime_engine",
        "enabled": fast_engine.enabled(),
    })
