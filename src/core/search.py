import re
import unicodedata

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from src.core import scraper
from src.config import VOIRANIME_DOMAIN, VOIRANIME_HEADERS, REQUEST_TIMEOUT


def norm(title):
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = re.sub(r'[\\/:*?"<>|]', " ", t)
    t = re.sub(r"[^\w\s\-&#']", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean(txt):
    t = txt.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def terms(txt):
    return set(clean(txt).split())


def _norm_title(t):
    """Normalize title for dedup comparison."""
    return re.sub(r"[^a-z0-9]", "", clean(t))


def search_anime(query, catalog, domain=None, limit=10):
    """Legacy search — used by places expecting the old signature."""
    return search_combined(query, catalog, domain=domain, limit=limit)


def search_voiranime(query):
    url = f"https://{VOIRANIME_DOMAIN}/template-php/defaut/fetch.php"
    try:
        r = httpx.post(url, data={"query": query}, headers=VOIRANIME_HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", class_="va-search-result"):
        link = a.get("href", "").strip()
        title_el = a.find("span", class_="va-search-result-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or not link:
            continue
        if not link.startswith("http"):
            link = f"https://{VOIRANIME_DOMAIN}{link}"
        results.append({"title": title, "link": link, "score": 100, "source": "voiranime"})
    return results


def search_combined(query, catalog, domain, limit=10):
    """
    Intelligent search across all sources.
    - Deduplicates by normalized title (not just link)
    - Prioritizes: catalog > online
    - No source tags in result (handled at display level)
    """
    q = clean(query)
    if not q:
        return []

    seen_titles = {}  # normalized title -> best result index
    results = []

    def _add(r):
        """Add result, deduplicating by normalized title."""
        key = _norm_title(r.get("title", ""))
        if not key:
            return
        if key in seen_titles:
            idx = seen_titles[key]
            existing = results[idx]
            # Keep the one with the higher score, or catalog source
            src_rank = {"catalog": 0, "online": 1, "voiranime": 2}
            cur_rank = src_rank.get(existing.get("source", ""), 3)
            new_rank = src_rank.get(r.get("source", ""), 3)
            if r.get("score", 0) > existing.get("score", 0) or new_rank < cur_rank:
                results[idx] = r
            # Merge alt sources
            alt = existing.get("alt_source", [])
            if r.get("source") and r["source"] not in alt:
                alt.append(r["source"])
            results[idx]["alt_source"] = alt
            # If the new result has anime_id, prefer it
            if r.get("anime_id") and not existing.get("anime_id"):
                results[idx]["anime_id"] = r["anime_id"]
            if r.get("link") and not existing.get("link"):
                results[idx]["link"] = r["link"]
        else:
            seen_titles[key] = len(results)
            results.append(r)

    # 1. Catalog search (highest priority, best quality)
    if catalog:
        qt = terms(query)
        scored = []
        for anime in catalog:
            title = anime.get("title", "")
            link = anime.get("link", "")
            c = clean(title)
            if not c:
                continue

            s = fuzz.token_set_ratio(q, c)
            bonus = 0

            tt = terms(title)
            common = qt & tt
            bonus = len(common) * 8

            for qw in qt:
                for tw in tt:
                    if len(qw) >= 3 and (qw in tw or tw in qw):
                        bonus = max(bonus, 6)

            ll = link.lower()
            for qw in qt:
                if qw in ll and len(qw) >= 3:
                    bonus = max(bonus, 10)

            for alt in anime.get("alt_titles", []):
                ac = clean(alt)
                if not ac:
                    continue
                ascore = fuzz.token_set_ratio(q, ac)
                if ascore > s:
                    s = ascore
                if ac == q:
                    s = 100
                    bonus = 40
                    break
                at = terms(alt)
                extra = qt & at
                if extra:
                    bonus = max(bonus, len(extra) * 5)
            else:
                bonus = min(bonus, 40)

            final = min(100, s + bonus)
            if final >= 40:
                entry = {
                    "title": anime["title"],
                    "link": link,
                    "score": final,
                    "source": "catalog",
                    "anime_id": anime.get("anime_id", ""),
                    "alt_source": anime.get("alt_source", []),
                    "genres": anime.get("genres", []),
                }
                scored.append(entry)

        scored.sort(key=lambda x: x["score"], reverse=True)
        for r in scored[:limit * 2]:  # Take more candidates than needed
            _add(r)

    # 2. Anime-Sama online search (live fallback)
    if domain:
        try:
            for r in scraper.search_online(domain, query):
                entry = {
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "score": r.get("score", 85),
                    "source": "online",
                    "anime_id": "",
                }
                _add(entry)
        except Exception:
            pass

    # 3. Voiranime search (final fallback)
    try:
        for r in search_voiranime(query):
            _add({
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "score": r.get("score", 80),
                "source": "voiranime",
                "anime_id": "",
            })
    except Exception:
        pass

    # Sort: highest score first
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
