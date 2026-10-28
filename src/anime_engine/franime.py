"""FRAnime (franime.fr) — API JSON publique.

    BASE = https://api.franime.fr/api/
    GET  /animes                                catalogue complet (~11 Mo, 2553 entrées)
    GET  /anime-seasons/{id}/{season}           episodes: number, title, thumbnail, airDate, _id
    GET  /anime/{id}/{sIdx}/{epIdx}/{lang}/{lIdx}
                                                -> https://franime.fr/watch2/?a=...&b=...&o=...

ATTENTION aux indices : ce sont des INDEX 0-based, pas des numéros.
    sIdx  = position de la saison dans animes[].saisons[]
    epIdx = position de l'episode dans saisons[sIdx].episodes[]
    lIdx  = position dans episodes[epIdx].lang[lang].lecteurs[]

La réponse finale est une URL watch2 dont les 15 parametres (a..o) sont un
blob binaire encode en base64 : la resolution en embed direct necessite le
navigateur (le decodeur est dans le bundle de la route /watch2).
"""
import json, re, time
from .net import session, request

API = "https://api.franime.fr/api/"
HEADERS = {"Accept": "application/json, text/plain, */*",
           "Origin": "https://franime.fr",
           "Referer": "https://franime.fr/"}


class Franime:
    def __init__(self):
        self.s = session(HEADERS)
        self._cat = None

    # ── infra ────────────────────────────────────────────────
    def _get(self, path):
        """GET avec retry sur challenge Cloudflare TRANSITOIRE (403).

        En rafale, l'API renvoie parfois un challenge CF au lieu du JSON :
        un backoff court suffit (contrairement à anime-sama où un 403 est
        un blocage IP durable). Les 429/5xx sont déjà gérés dans net.py.
        """
        r = request(self.s, "GET", API + path)
        for attempt in range(2):
            if r.status_code != 403:
                break
            time.sleep(1.5 * (attempt + 1))
            r = request(self.s, "GET", API + path)
        return r

    # ── catalogue ────────────────────────────────────────────
    def catalog(self, refresh=False):
        if self._cat is None or refresh:
            r = self._get("animes")
            if r.status_code != 200:
                raise RuntimeError(f"catalog HTTP {r.status_code}")
            self._cat = r.json()
        return self._cat

    def search(self, query, limit=30):
        q = query.lower().strip()
        out = []
        for a in self.catalog():
            title = (a.get("title") or a.get("titleO") or "").lower()
            alt = (a.get("titles") or {}).get("en_jp", "").lower()
            score = 0
            if q and q in title:
                score = 100 - abs(len(title) - len(q)) + (50 if title.startswith(q) else 0)
            elif q and q in alt:
                score = 80 - abs(len(alt) - len(q))
            if score > 0:
                out.append({"source": "franime", "id": a["id"],
                            "title": a.get("title") or a.get("titleO"),
                            "title_original": a.get("titleO"),
                            "status": a.get("status"), "nsfw": a.get("nsfw", False),
                            "seasons": len(a.get("saisons") or []),
                            "slug": str(a["id"]),
                            "url": f"https://franime.fr/anime/{a['id']}",
                            "score": score})
        out.sort(key=lambda x: x["score"], reverse=True)
        return out[:limit]

    # ── saisons / épisodes ───────────────────────────────────
    def seasons(self, anime_id):
        a = next((x for x in self.catalog() if x["id"] == int(anime_id)), None)
        if not a:
            return []
        return [{"index": i, "number": i + 1,
                 "title": (s.get("title") or f"Saison {i+1}"),
                 "episodes": len(s.get("episodes") or [])}
                for i, s in enumerate(a.get("saisons") or [])]

    def episodes(self, anime_id, season_index=0):
        r = self._get(f"anime-seasons/{anime_id}/{season_index + 1}")
        if r.status_code != 200:
            return []
        eps = r.json().get("episodes", [])
        try:
            a = next((x for x in self.catalog() if x["id"] == int(anime_id)), None)
        except Exception:
            # catalogue bloqué (CF) : on dégrade sans les lecteurs plutôt
            # que de casser episodes/resolve (le resolve n'en a pas besoin)
            a = None
        saisons = (a or {}).get("saisons") or []
        lecteurs = []
        if season_index < len(saisons):
            src_eps = saisons[season_index].get("episodes") or []
            if src_eps:
                lang = src_eps[0].get("lang") or {}
                lecteurs = {k: v.get("lecteurs", []) for k, v in lang.items()}
        out = []
        for i, e in enumerate(eps):
            out.append({"number": e.get("number", i + 1),
                        "index": i,
                        "title": e.get("title", ""),
                        "thumbnail": e.get("thumbnail"),
                        "air_date": e.get("airDate"),
                        "id": e.get("_id"),
                        "langs": ({k: v.get("lecteurs", []) for k, v in (e.get("lang") or {}).items()}
                                  if e.get("lang") else lecteurs)})
        return out

    # ── résolution ───────────────────────────────────────────
    def resolve(self, anime_id, season_index=0, episode_index=0,
                lang="vo", lecteur_index=0):
        """URL watch2 pour un épisode. lang: 'vo' (VOSTFR) ou 'vf'."""
        r = self._get(f"anime/{anime_id}/{season_index}/{episode_index}/{lang}/{lecteur_index}")
        if r.status_code != 200:
            return None
        body = r.text.strip()
        if not body.startswith("http"):
            try:
                d = r.json()
                body = d if isinstance(d, str) else (d.get("url") or "")
            except Exception:
                return None
        m = re.match(r"https://franime\.fr/watch2/\?", body)
        return {"url": body, "type": "watch2" if m else "embed",
                "watchable_in_iframe": True,
                "anime_id": anime_id, "season_index": season_index,
                "episode_index": episode_index, "lang": lang,
                "lecteur_index": lecteur_index}

    def resolve_number(self, anime_id, episode_number, season_index=0, lang="vo"):
        eps = self.episodes(anime_id, season_index)
        ep = next((e for e in eps if e["number"] == episode_number), None)
        if not ep:
            return None
        lecteurs = (ep.get("langs") or {}).get(lang) or []
        for i in range(max(1, len(lecteurs))):
            res = self.resolve(anime_id, season_index, ep["index"], lang, i)
            if res:
                res["lecteur"] = lecteurs[i] if i < len(lecteurs) else i
                return res
        return None
