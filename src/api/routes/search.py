from rapidfuzz import fuzz
import time

from src.api.utils.http import send_json
from src.api.utils.text import norm, base_title
from src.core import cache as cache_mod

_alt_cache = {}
_alt_cache_time = 0


def _get_alt_results(q):
    global _alt_cache, _alt_cache_time
    now = time.time()
    if now - _alt_cache_time > 900:
        try:
            from src.core.scraper import animesultra_catalog, frenchanime_catalog, animoflix_catalog
            _alt_cache["animesultra"] = animesultra_catalog()
            _alt_cache["frenchanime"] = frenchanime_catalog()
            _alt_cache["animoflix"] = animoflix_catalog()
            _alt_cache_time = now
        except Exception:
            pass

    out = []
    try:
        from src.core.scraper import animesultra_search, frenchanime_search, animoflix_search
        out.extend(animesultra_search(q, _alt_cache.get("animesultra")))
        out.extend(frenchanime_search(q, _alt_cache.get("frenchanime")))
        out.extend(animoflix_search(q, _alt_cache.get("animoflix")))
    except Exception:
        pass
    return out


def _calc_score(query, title, alt_titles=None):
    if not query or not title:
        return 0

    q = query.lower().strip()
    t = title.lower().strip()
    qn = norm(query)
    tn = norm(title)

    if q == t or qn == tn:
        return 100

    pr = fuzz.partial_ratio(q, t)
    tsr = fuzz.token_set_ratio(q, t)
    score = max(pr, tsr)

    q_tokens = set(q.split())
    t_tokens = set(t.split())
    extra = len(t_tokens - q_tokens)
    if extra > 0:
        score -= extra * 12

    if t.startswith(q + " "):
        score += 20

    if alt_titles:
        for alt in alt_titles:
            a = alt.lower().strip()
            alt_score = max(fuzz.partial_ratio(q, a), fuzz.token_set_ratio(q, a))
            a_tokens = set(a.split())
            alt_extra = len(a_tokens - q_tokens)
            if alt_extra > 0:
                alt_score -= alt_extra * 12
            if alt_score > score:
                score = alt_score
            if norm(alt) == qn:
                score = 100
                break

    return max(0, min(100, int(score)))


def handle(handler, params):
    q = (params.get("q", [None])[0] or "").strip()
    if not q:
        send_json(handler, {"error": "Missing 'q'"}, 400)
        return

    cat = cache_mod.load_catalog()
    qn = norm(q)
    results = {}  # key: normalized base title -> merged result

    for entry in cat:
        title = entry.get("title", "")
        tn = norm(title)
        if not tn:
            continue

        score = _calc_score(q, title, entry.get("alt_titles", []))
        if score < 50:
            continue

        # Deduplicate by base title (strip VF/VOSTFR)
        base_title_str, lang = base_title(title)
        base_key = norm(base_title_str)
        if not base_key:
            continue

        source = entry.get("source", "catalog")
        alt_sources = entry.get("alt_source", [source]) if entry.get("alt_source") else [source]

        if base_key in results:
            existing = results[base_key]
            if score > existing["score"]:
                existing["score"] = score
                existing["link"] = entry.get("link", "")
                existing["slug"] = entry.get("slug", "") or entry.get("link", "").rstrip("/").split("/")[-1]
                link = entry.get("link", "")
                if "myfluneo" in link:
                    existing["primary_source"] = "myfluneo"
                elif "voiranime" in link:
                    existing["primary_source"] = "voiranime"
                else:
                    existing["primary_source"] = "anime-sama"
            for s in alt_sources:
                if s not in existing["sources"]:
                    existing["sources"].append(s)
            if lang and lang not in existing.get("langs", []):
                existing.setdefault("langs", []).append(lang)
        else:
            langs = [lang] if lang else ["vostfr"]
            link = entry.get("link", "")
            if "myfluneo" in link:
                primary = "myfluneo"
            elif "voiranime" in link:
                primary = "voiranime"
            else:
                primary = "anime-sama"
            results[base_key] = {
                "title": base_title_str,
                "link": entry.get("link", ""),
                "slug": entry.get("slug", "") or entry.get("link", "").rstrip("/").split("/")[-1],
                "score": score,
                "sources": list(alt_sources),
                "primary_source": primary,
                "genres": entry.get("genres", []),
                "langs": langs,
            }

    for r in _get_alt_results(q):
        base_key = norm(r["title"])
        if not base_key:
            continue
        if base_key in results:
            existing = results[base_key]
            if r["score"] > existing["score"]:
                existing["score"] = r["score"]
                existing["link"] = r["link"]
                existing["slug"] = r.get("slug", "")
                existing["primary_source"] = r["source"]
            if r["source"] not in existing.get("sources", []):
                existing.setdefault("sources", []).append(r["source"])
        else:
            results[base_key] = {
                "title": r["title"],
                "link": r["link"],
                "slug": r.get("slug", ""),
                "score": r["score"],
                "sources": [r["source"]],
                "primary_source": r["source"],
                "genres": [],
                "langs": ["vostfr"],
            }

    out = sorted(results.values(), key=lambda x: (-x["score"], x["title"]))
    send_json(handler, {"query": q, "count": len(out), "results": out[:20]})


def do_search_internal(q):
    cat = cache_mod.load_catalog()
    results = []
    seen = set()
    for entry in cat:
        title = entry.get("title", "")
        score = _calc_score(q, title, entry.get("alt_titles", []))
        if score < 50:
            continue
        key = entry.get("link", title)
        if key in seen:
            continue
        seen.add(key)
        alt_sources = entry.get("alt_source", [entry.get("source", "catalog")])
        primary = "anime-sama"
        for s in alt_sources:
            if s == "myfluneo":
                primary = "myfluneo"
                break
            if s == "voiranime":
                primary = s
        results.append({"title": title, "link": entry.get("link", ""), "slug": entry.get("slug", ""),
                       "score": score, "sources": alt_sources, "primary_source": primary})
    results.sort(key=lambda x: (-x["score"], x["title"]))
    return {"query": q, "count": len(results), "results": results[:20]}
