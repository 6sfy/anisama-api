"""Moteur unifié — point d'entrée haut niveau."""
from .anime_sama import AnimeSama
from .franime import Franime

SOURCES = ("anime-sama", "franime")


class Engine:
    def __init__(self, sources=SOURCES):
        self.as_ = AnimeSama() if "anime-sama" in sources else None
        self.fr = Franime() if "franime" in sources else None

    # ── recherche ────────────────────────────────────────────
    def search(self, query, source=None, limit=30):
        """Cherche sur une source ou sur toutes. Retourne une liste plate."""
        out = []
        if source in (None, "anime-sama") and self.as_:
            out += self.as_.search(query, limit=limit)
        if source in (None, "franime") and self.fr:
            out += self.fr.search(query, limit=limit)
        # dédoublonnage par titre normalisé (garde le meilleur score)
        best = {}
        for r in out:
            key = "".join(c for c in (r["title"] or "").lower() if c.isalnum())
            if key not in best or r.get("score", 0) > best[key].get("score", 0):
                if key in best:
                    r["also_on"] = list({best[key]["source"], r["source"]})
                    r.setdefault("variants", []).append(best[key])
                best[key] = r
        return list(best.values())[:limit]

    # ── saisons ──────────────────────────────────────────────
    def seasons(self, source, slug):
        if source == "anime-sama":
            return self.as_.seasons(slug)
        if source == "franime":
            return self.fr.seasons(slug)
        raise ValueError(source)

    # ── épisodes ─────────────────────────────────────────────
    def episodes(self, source, slug, season_url=None, season_index=0):
        if source == "anime-sama":
            return self.as_.episodes(slug, season_url)
        if source == "franime":
            return self.fr.episodes(int(slug), season_index)
        raise ValueError(source)

    # ── résolution ───────────────────────────────────────────
    def resolve(self, source, slug, number, season_url=None, season_index=0, lang="vo"):
        if source == "anime-sama":
            return self.as_.resolve(slug, number, season_url)
        if source == "franime":
            return self.fr.resolve_number(int(slug), number, season_index, lang)
        raise ValueError(source)

    # ── helpers ──────────────────────────────────────────────
    def catalogue_franime(self):
        return self.fr.catalog() if self.fr else []

    def hosts(self, slug, season_url=None):
        return self.as_.hosts(slug, season_url) if self.as_ else {}
