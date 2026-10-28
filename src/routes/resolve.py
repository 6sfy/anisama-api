import logging
import re
import time

from src.helpers import (send_json, send_internal_error, is_safe_external_url,
                         playwright_available)
from src.db.models import get_anime_episodes, save_episodes
from src import fast_engine

logger = logging.getLogger("anisama-api")

RESOLVED_TTL = {"m3u8": 300, "embed": 600, "mp4": 604800, "webm": 604800, "raw": 3600}
DEFAULT_TTL = 300


def _merge_existing_resolutions(slug, source, entries):
    """Préserve les URLs déjà résolues quand on réécrit la liste d'épisodes.

    save_episodes() fait un INSERT OR REPLACE : sans cette fusion, résoudre
    l'épisode 1 écraserait la résolution déjà en cache de l'épisode 5.
    """
    previous = {e.get("number"): e for e in (get_anime_episodes(slug=slug, source=source) or [])}
    for item in entries:
        prev = previous.get(item.get("number"))
        if not prev:
            continue
        if not item.get("resolved") and prev.get("resolved_url"):
            item.update({
                "resolved": prev.get("resolved_url", ""),
                "resolved_type": prev.get("resolved_type", ""),
                "resolved_referer": prev.get("resolved_referer", ""),
                "resolved_at": prev.get("resolved_at"),
            })
        if not item.get("season") and prev.get("season"):
            item["season"] = prev["season"]
        if not item.get("url") and prev.get("url"):
            item["url"] = prev["url"]
    return entries


def _voiranime_lang(raw):
    """API lang ('vo' par défaut) -> segment d'URL Voiranime."""
    lang = (raw or "vo").strip().lower()
    if lang in ("vf", "vf2"):
        return lang
    return "vostfr"


def _voiranime_lang_url(url, lang):
    """.../episode-1/vostfr/ -> .../episode-1/vf/ (sans casser les URLs inconnues)."""
    if not url:
        return url
    return re.sub(r"/(?:vostfr|vf2?)/?$", "/{l}/".format(l=lang), url)


def _to_direct(result):
    """Voiranime renvoie l'iframe du lecteur : tenter le flux HLS direct."""
    if not result or not result.get("url"):
        return result
    if result.get("type") != "raw":
        return result
    from anisama.resolver import resolve_url
    try:
        direct = resolve_url(result["url"])
    except Exception:
        return result
    if direct and direct.get("url") and direct.get("type") not in (None, "raw"):
        return direct
    # Sibnet & co. ne se résolvent pas sans navigateur : l'URL reste l'iframe
    # du lecteur, donc « embed » (jouable dans /player), pas « raw ».
    if result.get("url") and result.get("type") == "raw":
        return {**result, "type": "embed"}
    return result


def handle_resolve(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    source = (params.get("source", [""])[0] or "").strip()
    lang = (params.get("lang", ["vo"])[0] or "vo").strip()

    if not url:
        send_json(handler, {"error": "Missing 'url'"}, 400)
        return
    if not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return

    logger.info("Resolve: %s (%s)", url[:80], source)

    if source in ("myfluneo", "animoflix") and not playwright_available():
        send_json(handler, {"error": "source_unavailable", "source": source}, 501)
        return

    try:
        if source == "voiranime":
            from anisama.resolver import resolve_voiranime_episode, resolve_url
            page_lang = _voiranime_lang(lang)
            result = resolve_voiranime_episode(url, page_lang)
            if not result:
                result = resolve_url(url)
            result = _to_direct(result)
        elif source == "myfluneo":
            from anisama.scraper.myfluneo import myfluneo_resolve
            result = myfluneo_resolve(url)
        else:
            from anisama.resolver import resolve_url
            result = resolve_url(url)
    except Exception as exc:
        send_internal_error(handler, exc, logger, "resolve")
        return

    if result:
        send_json(handler, {"url": url, "resolved": result})
    else:
        send_json(handler, {"url": url, "resolved": {"url": url, "type": "raw"}})


def handle_resolve_episode_submit(handler, data):
    """Write-back: store a client-resolved URL so future API calls are instant."""
    source = (data.get("source") or "").strip()
    slug = (data.get("slug") or "").strip()
    url = (data.get("url") or "").strip()
    rtype = (data.get("type") or "mp4").strip()[:20]
    referer = (data.get("referer") or "").strip()

    try:
        num = int(data.get("num"))
    except (TypeError, ValueError):
        send_json(handler, {"error": "Invalid 'num'"}, 400)
        return
    if not source or not slug:
        send_json(handler, {"error": "Missing source or slug"}, 400)
        return
    if not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return
    if referer and not is_safe_external_url(referer):
        referer = ""

    existing_url = ""
    eps = get_anime_episodes(slug=slug, source=source)
    if eps:
        for ep in eps:
            if ep.get("number") == num:
                existing_url = ep.get("url", "")
                break
    page_url = existing_url or referer or url
    save_episodes(slug, slug, source, [{
        "number": num,
        "url": page_url,
        "resolved": url,
        "resolved_type": rtype,
        "resolved_referer": referer,
        "resolved_at": time.time(),
    }])
    logger.info("Resolution submitted: %s/%s EP%s (%s)", source, slug, num, rtype)
    send_json(handler, {"status": "ok"}, 201)


def handle_resolve_episode(handler, params):
    source = (params.get("source", [None])[0] or "").strip()
    slug = (params.get("slug", [None])[0] or "").strip()
    num_str = (params.get("num", [None])[0] or "").strip()
    fresh = (params.get("fresh", [None])[0] or "").strip() == "1"
    lang = (params.get("lang", ["vo"])[0] or "vo").strip()
    season = 1
    try:
        season = max(1, int((params.get("season", ["1"])[0] or "1")))
    except ValueError:
        pass

    if not source or not slug or not num_str:
        send_json(handler, {"error": "Missing source, slug, or num"}, 400)
        return

    try:
        num = int(num_str)
    except ValueError:
        send_json(handler, {"error": "Invalid 'num'"}, 400)
        return
    logger.info("Resolve episode: %s/%s EP%s%s", source, slug, num, " (fresh)" if fresh else "")

    # Voiranime : une seule ligne par numéro en DB (pas de clé langue).
    # On ne met en cache que la VOSTFR pour ne pas écraser la VF et inversement.
    vn_lang = _voiranime_lang(lang) if source == "voiranime" else None
    cacheable = not (source == "voiranime" and vn_lang != "vostfr")

    # 1. Check SQLite for an already-resolved URL (fresh=1 bypasses the cache)
    eps = None
    if not fresh and cacheable:
        eps = get_anime_episodes(slug=slug, source=source)
        if eps:
            for ep in eps:
                if ep.get("number") == num and ep.get("resolved_url"):
                    ttl = RESOLVED_TTL.get(ep.get("resolved_type", ""), DEFAULT_TTL)
                    resolved_at = ep.get("resolved_at") or 0
                    if time.time() - resolved_at <= ttl:
                        rtype = ep.get("resolved_type", "")
                        # Les anciennes lignes Voiranime stockaient l'iframe en
                        # « raw » : c'est un embed jouable, pas un fichier.
                        if source == "voiranime" and rtype == "raw":
                            rtype = "embed"
                        send_json(handler, {"source": source, "slug": slug, "episode": num,
                                    "url": ep["resolved_url"], "type": rtype, "cached": True, "referer": ep.get("resolved_referer", "")})
                        return
            logger.info("Cached resolution expired for %s/%s EP%s", source, slug, num)

    if source in ("myfluneo", "animoflix") and not playwright_available():
        send_json(handler, {"error": "source_unavailable", "source": source}, 501)
        return

    # 2. Fast path : moteur anime_engine
    #    anime-sama -> embed DIRECT depuis episodes.js (pas de resolve_url lent)
    #    franime    -> indexes 0-based corrects (l'ancien pipeline renvoyait 404)
    if fast_engine.enabled() and source in ("anime-sama", "franime"):
        try:
            t0 = time.time()
            r = fast_engine.fast_resolve(source, slug, num,
                                         season=season if source == "franime" else 1,
                                         lang=lang)
            if r and r.get("url") and is_safe_external_url(r["url"], max_len=16384):
                # Sauvegarde la liste complète d'épisodes (pas seulement celui
                # résolu), sinon /episodes ne renverrait qu'une seule entrée.
                entries = []
                try:
                    for e in fast_engine.fast_episodes(
                            source, slug, season=season if source == "franime" else 1):
                        item = {
                            "number": e.get("number"),
                            "season": e.get("season", ""),
                            "url": e.get("url", ""),
                            "lang": e.get("lang", "vostfr"),
                        }
                        if e.get("number") == num:
                            item.update({
                                "resolved": r["url"],
                                "resolved_type": r.get("type", "embed"),
                                "resolved_referer": r.get("referer", ""),
                                "resolved_at": time.time(),
                            })
                        entries.append(item)
                except Exception:
                    entries = []
                if not any(x.get("number") == num for x in entries):
                    entries.append({
                        "number": num,
                        "url": (f"franime://{slug}/{season}/{num}"
                                if source == "franime" else ""),
                        "resolved": r["url"],
                        "resolved_type": r.get("type", "embed"),
                        "resolved_referer": r.get("referer", ""),
                        "resolved_at": time.time(),
                    })
                save_episodes(slug, slug, source,
                              _merge_existing_resolutions(slug, source, entries))
                logger.info("  -> Fast engine OK en %.2fs (%s)", time.time() - t0, r.get("type"))
                send_json(handler, {"source": source, "slug": slug, "episode": num,
                            "url": r["url"], "type": r.get("type", "embed"),
                            "cached": False, "referer": r.get("referer", ""),
                            "engine": True})
                return
            logger.info("  -> Fast engine: rien trouve, fallback pipeline historique")
        except Exception as exc:
            logger.warning("  -> Fast engine KO (%s), fallback pipeline historique", exc)

    # 3. Resolve on demand (pipeline historique)
    result = None
    save_url = ""
    try:
        eps = get_anime_episodes(slug=slug, source=source)
        if source == "anime-sama":
            from anisama.resolver import resolve_url
            from anisama.scraper.base import find_active_domain
            from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
            from src.routes.episodes import _NON_ANIME_SEASON_HINTS
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
                        if any(h in (season.get("url") or "").lower()
                               for h in _NON_ANIME_SEASON_HINTS):
                            continue
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

        elif source == "voiranime":
            from anisama.resolver import resolve_url, resolve_voiranime_episode
            from src.routes.episodes import _ep_voiranime

            page_lang = vn_lang or "vostfr"
            if not eps:
                all_eps = _ep_voiranime("", slug)
                if all_eps:
                    save_episodes(slug, slug, source,
                                  _merge_existing_resolutions(slug, source, all_eps))
                    eps = get_anime_episodes(slug=slug, source=source)
            ep_page = ""
            for ep in (eps or []):
                if ep.get("number") == num and ep.get("url"):
                    ep_page = ep["url"]
                    break
            if ep_page:
                save_url = ep_page
                page_url = _voiranime_lang_url(ep_page, page_lang)
                r = resolve_voiranime_episode(page_url, page_lang)
                if r:
                    r = _to_direct(r)
                    result = {"url": r["url"], "type": r.get("type", "embed"),
                              "referer": page_url}

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
    except Exception:
        logger.exception("Resolve error")

    if result:
        # Save to DB for future
        if cacheable:
            saved = False
            if eps:
                for ep in eps:
                    if ep.get("number") == num:
                        save_episodes(slug, slug, source,
                            [{"number": num, "url": ep.get("url", ""),
                              "season": ep.get("season", ""),
                              "resolved": result["url"], "resolved_type": result["type"],
                              "resolved_referer": result.get("referer", ""),
                              "lang": vn_lang or ep.get("lang") or "vostfr",
                              "resolved_at": time.time()}])
                        saved = True
                        break
            if not saved:
                save_episodes(slug, slug, source,
                    [{"number": num, "url": save_url,
                      "resolved": result["url"], "resolved_type": result["type"],
                      "resolved_referer": result.get("referer", ""),
                      "lang": vn_lang or "vostfr",
                      "resolved_at": time.time()}])
        send_json(handler, {"source": source, "slug": slug, "episode": num,
                    "url": result["url"], "type": result["type"], "cached": False, "referer": result.get("referer", "")})
    else:
        send_json(handler, {"error": "Could not resolve"}, 404)
