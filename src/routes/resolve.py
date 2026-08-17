import logging

from src.helpers import send_json, is_safe_external_url
from src.db.models import get_anime_episodes, save_episodes

logger = logging.getLogger("anisama-api")


def handle_resolve(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    source = (params.get("source", [""])[0] or "").strip()

    if not url:
        send_json(handler, {"error": "Missing 'url'"}, 400)
        return
    if not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return

    logger.info("Resolve: %s (%s)", url[:80], source)

    if source == "voiranime":
        from anisama.resolver import resolve_voiranime_episode
        result = resolve_voiranime_episode(url, "vostfr")
    elif source == "myfluneo":
        from anisama.scraper.myfluneo import myfluneo_resolve
        result = myfluneo_resolve(url)
    else:
        from anisama.resolver import resolve_url
        result = resolve_url(url)

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

    try:
        num = int(num_str)
    except ValueError:
        send_json(handler, {"error": "Invalid 'num'"}, 400)
        return
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
            from anisama.resolver import resolve_url
            from anisama.scraper.base import find_active_domain
            from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
            if eps:
                for ep in eps:
                    if ep.get("number") == num and ep.get("url") and is_safe_external_url(ep["url"]):
                        ep_url = ep["url"]
                        r = resolve_url(ep_url)
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "mp4"), "referer": ep_url}
                        break
            if not result:
                domain = find_active_domain()
                if domain:
                    cat_url = f"https://{domain}/catalogue/{slug}/"
                    seasons = get_anime_seasons(cat_url)
                    abs_offset = 0
                    for season in seasons:
                        ep_list = get_episodes(season["url"])
                        for e in ep_list:
                            abs_num = abs_offset + e["number"]
                            if abs_num == num:
                                mirrors = e.get("mirrors", {})
                                for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
                                    u = mirrors[k]
                                    if not is_safe_external_url(u):
                                        continue
                                    r = resolve_url(u)
                                    if r and r.get("url") and r.get("type") != "raw":
                                        result = {"url": r["url"], "type": r["type"], "referer": u}
                                        break
                                break
                        if result:
                            break
                        abs_offset += len(ep_list)

        elif source == "myfluneo":
            from anisama.scraper.myfluneo import myfluneo_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        ep_url = ep.get("url") or f"https://myfluneo.eu/anime/{slug}/saison-1/episode-{num}"
                        if not is_safe_external_url(ep_url):
                            continue
                        r = myfluneo_resolve(ep_url)
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "mp4")}
                            break

        elif source == "voiranime":
            from anisama.resolver import resolve_voiranime_episode
            result = resolve_voiranime_episode("", "vostfr")

        elif source == "animesultra":
            from anisama.scraper.animesultra import animesultra_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num and is_safe_external_url(ep.get("url", "")):
                        r = animesultra_resolve(ep["url"])
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break

        elif source == "frenchanime":
            from anisama.scraper.frenchanime import frenchanime_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num and is_safe_external_url(ep.get("url", "")):
                        r = frenchanime_resolve(ep["url"])
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break

        elif source == "animoflix":
            from anisama.scraper.animoflix import animoflix_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num and is_safe_external_url(ep.get("url", "")):
                        r = animoflix_resolve(ep["url"])
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed")}
                            break

        elif source == "franime":
            from anisama.scraper.franime import franime_resolve
            eps_list = get_anime_episodes(slug=slug, source=source)
            if eps_list:
                for ep in eps_list:
                    if ep.get("number") == num:
                        ep_url = ep.get("url", "")
                        if not (ep_url.startswith("franime://") or is_safe_external_url(ep_url)):
                            continue
                        r = franime_resolve(ep_url)
                        if r and r.get("url"):
                            result = {"url": r["url"], "type": r.get("type", "embed"), "referer": r.get("referer", "")}
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
