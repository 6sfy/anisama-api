"""Fast Engine — backend rapide basé sur anime_engine (extraction directe).

Pourquoi ce module existe
-------------------------
Le pipeline historique (lib anisama) passe par BeautifulSoup + un resolver
qui fetch chaque page d'embed pour en extraire un flux direct : lent, fragile,
et souvent rempli d'URLs hls mortes. Le moteur anime_engine extrait les API
réelles d'Anime-Sama (episodes.js : URLs d'embed directes) et de FRAnime
(API JSON, indexes 0-based corrects) : 10 à 50x plus rapide, zéro dépendance
lourde (requests uniquement).

Ce module expose une façade thread-safe avec cache TTL mémoire et convertit
les sorties du moteur vers les formats de réponse de l'API v2, de sorte que
le CLI anisama continue de fonctionner sans aucun changement.

Désactivation / configuration
-----------------------------
    ANISAMA_FAST_ENGINE=0   désactive le fast path (fallback pipeline historique)
    ENGINE_PROXY=http://…   proxy sortant (utile si l'IP du serveur est bloquée
                            par Cloudflare côté anime-sama)
    ENGINE_TIMEOUT=25       timeout réseau du moteur (secondes)
"""

import logging
import os
import re
import threading
import time

from src.helpers import extract_media_from_url, is_media_url, media_type

logger = logging.getLogger("anisama-api")

try:
    from .anime_engine.engine import Engine
except ImportError:  # exécution hors package (python src/fast_engine.py)
    from src.anime_engine.engine import Engine

# ── État global ──────────────────────────────────────────────────

_lock = threading.RLock()
_engine = None
_cache = {}  # clé -> (expires_at, valeur)

TTL_SEARCH = 300        # résultats de recherche
TTL_SEASONS = 3600      # liste des saisons
TTL_EPISODES = 1800     # liste d'épisodes (+ miroirs)
TTL_RESOLVE = 600       # résolution d'un épisode (embed watch2/direct)
TTL_HOSTS = 1800        # hôtes d'une saison


def enabled():
    """Fast engine actif ? (ANISAMA_FAST_ENGINE=0 pour désactiver)."""
    return os.environ.get("ANISAMA_FAST_ENGINE", "1") != "0"


def engine():
    """Instance Engine partagée (lazy, thread-safe)."""
    global _engine
    with _lock:
        if _engine is None:
            _engine = Engine()
            logger.info("Fast engine prêt (anime-sama: %s / franime: %s)",
                        "oui" if _engine.as_ else "non",
                        "oui" if _engine.fr else "non")
        return _engine


def cache_size():
    with _lock:
        return len(_cache)


# ── Cache TTL ────────────────────────────────────────────────────

def _cache_get(key):
    with _lock:
        item = _cache.get(key)
        if item and item[0] > time.time():
            return item[1]
        if item:
            del _cache[key]
    return None


def _cache_set(key, value, ttl):
    with _lock:
        _cache[key] = (time.time() + ttl, value)


def _call(key, ttl, fn):
    """Retourne (valeur, depuis_cache). Les appels réseau du moteur sont
    sérialisés (requests.Session n'est pas garanti thread-safe) mais le
    cache fait que la plupart des requêtes ne bloquent jamais."""
    cached = _cache_get(key)
    if cached is not None:
        return cached, True
    with _lock:
        cached = _cache_get(key)
        if cached is not None:
            return cached, True
        value = fn()
        _cache_set(key, value, ttl)
        return value, False


# ── Helpers de conversion ────────────────────────────────────────

_SCAN_HINTS = ("/scan/", "/manga/", "/manhwa/", "/webtoon/", "/manhua/")


def clamp_score(score):
    """Borne un score à 0..100 (le CLI l'affiche comme un pourcentage)."""
    try:
        return max(0, min(100, round(float(score))))
    except (TypeError, ValueError):
        return 0


def _is_print_entry(r):
    """True si le résultat de recherche semble être un manga/scan (pas un anime)."""
    url = (r.get("url") or "").lower()
    if any(h in url for h in _SCAN_HINTS):
        return True
    title = (r.get("title") or "").lower().strip()
    return title.endswith((" scan", " scan vf"))


def _season_lang(season_url):
    u = (season_url or "").lower()
    if "/vf/" in u or u.endswith("/vf"):
        return "vf"
    return "vostfr"


# ── Recherche ────────────────────────────────────────────────────

def fast_search(q, limit=20):
    """Recherche via le moteur -> format résultats API v2.

    Sortie : liste [{title, link, slug, score, source}] (mêmes champs que
    les résultats « alt » du pipeline historique, consommés par
    routes/search.py).
    """
    key = f"search:{(q or '').lower().strip()}:{limit}"
    results, _ = _call(key, TTL_SEARCH, lambda: _search_uncached(q, limit))
    return results


def _title_score(q, title):
    qn = re.sub(r"[^a-z0-9]", "", (q or "").lower())
    tn = re.sub(r"[^a-z0-9]", "", (title or "").lower())
    if not qn or not tn:
        return 70
    if tn == qn:
        return 100
    if tn.startswith(qn) or qn in tn:
        return 95
    return 80


def _search_uncached(q, limit):
    e = engine()
    out = []
    try:
        raw = e.search(q, limit=max(limit * 2, 30))
    except Exception as exc:
        logger.warning("fast_search moteur: %s", exc)
        return out
    for r in raw:
        if _is_print_entry(r):
            continue
        src = r.get("source")
        if src == "anime-sama":
            out.append({
                "title": r.get("title") or "",
                "link": r.get("url") or "",
                "slug": r.get("slug") or "",
                "score": _title_score(q, r.get("title")),
                "source": "anime-sama",
            })
        elif src == "franime":
            aid = r.get("id") or r.get("slug")
            out.append({
                "title": r.get("title") or "",
                "link": f"https://franime.fr/anime/{aid}",
                "slug": str(aid),
                "score": clamp_score(r.get("score") or 80),
                "source": "franime",
            })
    return out[:limit]


# ── Saisons ──────────────────────────────────────────────────────

def fast_seasons(source, slug):
    """Saisons -> [{name, url, lang}] (anime-sama) ou [{index, title, episodes}] (franime)."""
    key = f"seasons:{source}:{slug}"
    seasons, _ = _call(key, TTL_SEASONS, lambda: _seasons_uncached(source, slug))
    return seasons


def _seasons_uncached(source, slug):
    e = engine()
    if source == "anime-sama":
        ss = e.as_.seasons(slug)
        return [{"name": s["name"], "url": s["url"], "lang": _season_lang(s["url"])}
                for s in ss]
    if source == "franime":
        return e.fr.seasons(int(slug))
    raise ValueError(source)


# ── Épisodes ─────────────────────────────────────────────────────

def fast_episodes(source, slug, url=None, season=1):
    """Épisodes -> liste compatible save_episodes().

    anime-sama : toutes saisons aplaties (numérotation absolue),
                 {number, season, lang, url, mirrors: [embed, …]}
    franime    : saison `season` (1-based, défaut 1, comme le pipeline
                 historique), {number, season, lang, url: franime://…}
    """
    key = f"episodes:{source}:{slug}:{url or ''}:{season}"
    eps, _ = _call(key, TTL_EPISODES, lambda: _episodes_uncached(source, slug, url, season))
    return eps


def _episodes_uncached(source, slug, url, season):
    e = engine()
    if source == "anime-sama":
        seasons = e.as_.seasons(slug)
        if url:
            filtered = [s for s in seasons if s["url"].rstrip("/") == url.rstrip("/")]
            seasons = filtered or seasons
        return _flatten_animesama(e, slug, seasons)
    if source == "franime":
        return _episodes_franime(e, slug, season)
    raise ValueError(source)


def _flatten_animesama(e, slug, seasons):
    all_eps = []
    offset = 0
    for s in seasons:
        eps = e.as_.episodes(slug, s["url"])
        for ep in eps:
            all_eps.append({
                "number": offset + ep["number"],      # numérotation absolue (API)
                "season_number": ep["number"],        # numéro dans la saison
                "season": s.get("name", ""),
                "lang": _season_lang(s["url"]),
                "url": "",
                "mirrors": list(ep.get("mirrors", {}).values()),
                "season_url": s["url"],
            })
        offset += len(eps)
    return all_eps


def _episodes_franime(e, slug, season):
    aid = int(slug)
    eps = e.fr.episodes(aid, season_index=season - 1)
    out = []
    for ep in eps:
        langs = ep.get("langs") or {}
        lang = "vostfr" if langs.get("vo") else ("vf" if langs.get("vf") else "vostfr")
        out.append({
            "number": ep["number"],
            "season": season,
            "lang": lang,
            "url": f"franime://{aid}/{season}/{ep['number']}",
            "title": ep.get("title") or "",
            "lecteurs": langs,
        })
    return out


# ── Résolution ───────────────────────────────────────────────────

def fast_resolve(source, slug, num, season=1, lang="vo"):
    """Résout un épisode -> {url, type, referer} ou None.

    anime-sama : le premier miroir episodes.js = URL d'embed DIRECTE
                 (vidmoly/embed4me/sibnet/… jouable par yt-dlp/mpv) — aucun
                 passage par le resolver lent.
    franime    : API JSON avec indexes 0-based corrects (le correctif clé
                 du moteur : l'ancien pipeline envoyait des numéros 1-based
                 et recevait 404 « Aucun lecteur disponible »).
    """
    key = f"resolve:{source}:{slug}:{num}:{season}:{lang}"
    result, _ = _call(key, TTL_RESOLVE, lambda: _resolve_uncached(source, slug, num, season, lang))
    return result


# Hosts connus pour exposer un flux résolvable (m3u8/mp4) — testés en priorité.
# Anime-Sama met désormais uqload en eps1 : irrésolvable via yt-dlp/generic,
# alors que ansembed/embed4me (eps2/eps3) exposent bien un HLS.
_MIRROR_PRIORITY = ("ansembed", "embed4me", "vidmoly", "sibnet", "sendvid",
                    "smoothpre", "vidhide", "streamwish", "oneupload", "minochinos")


def _mirror_rank(url):
    low = (url or "").lower()
    for i, host in enumerate(_MIRROR_PRIORITY):
        if host in low:
            return i
    return len(_MIRROR_PRIORITY)


def _resolve_best_mirror(mirrors, referer):
    """Résout les miroirs d'un épisode et renvoie le premier flux direct.

    Les lecteurs sont essayés dans l'ordre de préférence (ansembed, embed4me,
    …) plutôt que dans l'ordre brut eps1/eps2/eps3, puis on garde le premier
    embed comme repli si aucun flux direct n'est trouvé.
    """
    urls = [u for u in (mirrors or [])
            if isinstance(u, str) and u.startswith(("http://", "https://"))]
    if not urls:
        return None
    ordered = [u for _, u in sorted(enumerate(urls), key=lambda p: (_mirror_rank(p[1]), p[0]))]
    fallback = {"url": ordered[0], "type": "embed", "referer": referer}
    try:
        from anisama.resolver import resolve_url
    except Exception as exc:
        logger.warning("resolver indisponible: %s", exc)
        return fallback
    for mirror in ordered[:4]:
        try:
            r = resolve_url(mirror)
        except Exception as exc:
            logger.warning("resolve miroir %s: %s", mirror, exc)
            r = None
        direct = (r or {}).get("url")
        rtype = (r or {}).get("type")
        if direct and direct.startswith(("http://", "https://")):
            if is_media_url(direct):
                return {"url": direct, "type": media_type(direct) or rtype,
                        "referer": referer}
            if rtype == "embed" and direct != mirror:
                fallback = {"url": direct, "type": "embed", "referer": referer}
        # 2.1.6 renvoie parfois un tracker (staticmoly/deskademeta.php) :
        # extraire le vrai m3u8 directement depuis la page embed.
        media = extract_media_from_url(mirror)
        if media:
            return {"url": media, "type": media_type(media) or "embed",
                    "referer": referer}
    return fallback


def _resolve_uncached(source, slug, num, season, lang):
    e = engine()
    if source == "anime-sama":
        # Le numéro est ABSOLU (saisons aplaties) : localiser la saison via
        # la liste d'épisodes (déjà en cache), puis résoudre un miroir direct.
        eps = fast_episodes("anime-sama", slug)
        ep = next((x for x in eps if x["number"] == num), None)
        if not ep:
            return None
        return _resolve_best_mirror(ep.get("mirrors", []),
                                    ep.get("season_url") or "")
    if source == "franime":
        res = e.fr.resolve_number(int(slug), num, season_index=season - 1, lang=lang)
        if not res:
            return None
        return {"url": res["url"], "type": "embed",
                "referer": "https://franime.fr/"}
    raise ValueError(source)


# ── Hôtes ────────────────────────────────────────────────────────

def fast_hosts(slug, season_url=None):
    """Hôtes distincts d'une saison anime-sama -> {hote: [lecteurs]}."""
    key = f"hosts:{slug}:{season_url or ''}"
    hosts, _ = _call(key, TTL_HOSTS, lambda: (engine().as_.hosts(slug, season_url) or {}))
    return hosts
