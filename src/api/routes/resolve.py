import logging

from src.api.utils.http import send_json
from src.api.db.models import get_anime_episodes, save_episodes

logger = logging.getLogger("anisama-api")


def handle_resolve(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    source = (params.get("source", [""])[0] or "").strip()

    if not url:
        send_json(handler, {"error": "Missing 'url'"}, 400)
        return

    logger.info("Resolve: %s (%s)", url[:80], source)

    if source == "voiranime":
        from src.core import resolver
        result = resolver.resolve_voiranime_episode(url, "vostfr")
    elif source == "myfluneo":
        from src.core.scraper import myfluneo_resolve
        result = myfluneo_resolve(url)
    else:
        from src.core import resolver
        result = resolver.resolve_url(url)

    if result:
        send_json(handler, {"url": url, "resolved": result})
    else:
        send_json(handler, {"url": url, "resolved": {"url": url, "type": "raw"}})


def handle_resolve_episode(handler, params):
    source = (params.get("source", [None])[0] or "").strip()
    slug = (params.get("slug", [None])[0] or "").strip()
    num_str = (params.get("num", [None])[0] or "").strip()

    if not source or not slug or not num_str:
        send_json(handler, {"error": "Missing source, slug, or num"}, 400)
        return

    num = int(num_str)
    logger.info("Resolve episode: %s/%s EP%s", source, slug, num)

    # 1. Check SQLite for already-resolved URL
    eps = get_anime_episodes(slug=slug, source=source)
    if eps:
        for ep in eps:
            if ep.get("number") == num and ep.get("resolved_url"):
                send_json(handler, {"source": source, "slug": slug, "episode": num,
                            "url": ep["resolved_url"], "type": ep.get("resolved_type", ""), "cached": True, "referer": ep.get("resolved_referer", "")})
                return

    # 2. Resolve on demand
    result = None
    try:
        if source == "anime-sama":
            from src.core import resolver, scraper
            if eps:
                for ep in eps:
                    if ep.get("number") == num and ep.get("url"):
                        ep_url = ep["url"]
                        r = resolver.resolve_url(ep_url)
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "mp4"), "referer": ep_url}
                        break
            if not result:
                domain = scraper.find_active_domain()
                if domain:
                    cat_url = f"https://{domain}/catalogue/{slug}/"
                    seasons = scraper.get_anime_seasons(cat_url)
                    abs_offset = 0
                    for season in seasons:
                        ep_list = scraper.get_episodes(season["url"])
                        for e in ep_list:
                            abs_num = abs_offset + e["number"]
                            if abs_num == num:
                                mirrors = e.get("mirrors", {})
                                for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
                                    u = mirrors[k]
                                    r = resolver.resolve_url(u)
                                    if r and r.get("url") and r.get("type") != "raw":
                                        result = {"url": r["url"], "type": r["type"], "referer": u}
                                        break
                                break
                        if result:
                            break
                        abs_offset += len(ep_list)

        elif source == "myfluneo":
            from src.core.scraper import myfluneo_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        r = myfluneo_resolve(ep.get("url", f"https://myfluneo.eu/anime/{slug}/saison-1/episode-{num}"))
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "mp4")}
                            break

        elif source == "voiranime":
            from src.core import resolver
            result = resolver.resolve_voiranime_episode("", "vostfr")

        elif source == "animesultra":
            from src.core import scraper
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        r = scraper.animesultra_resolve(ep.get("url"))
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break

        elif source == "frenchanime":
            from src.core import scraper
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        r = scraper.frenchanime_resolve(ep.get("url"))
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break

        elif source == "animoflix":
            from src.core import scraper
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        r = scraper.animoflix_resolve(ep.get("url"))
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break
    except Exception as e:
        logger.error("Resolve error: %s", e)

    if result:
        # Save to DB for future
        if eps:
            for ep in eps:
                if ep.get("number") == num:
                    save_episodes(slug, slug, source,
                        [{"number": num, "url": ep.get("url", ""),
                          "resolved": result["url"], "resolved_type": result["type"]}])
                    break
        send_json(handler, {"source": source, "slug": slug, "episode": num,
                    "url": result["url"], "type": result["type"], "cached": False, "referer": result.get("referer", "")})
    else:
        send_json(handler, {"error": "Could not resolve"}, 404)
