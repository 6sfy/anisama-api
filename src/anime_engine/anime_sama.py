"""Anime-Sama (anime-sama.to) — extraction HTML/JS, liens d'embed directs.

Pipeline
    search(q)            POST /template-php/defaut/fetch.php   {query: q}
    seasons(slug)        GET  /catalogue/<slug>/               panneauAnime("nom","url")
    episodes(slug, s)    GET  /catalogue/<slug>/<url>/episodes.js
                         ->  var eps1=[...], eps2=[...], ...   (1 tableau = 1 lecteur)
    episode i            mirrors = {eps1: url, eps2: url, ...}

Les URLs de episodes.js sont des embeds directs (vidmoly/ansembed.net,
embed4me, sendvid, sibnet, uqload, smoothpre...), exploitables par yt-dlp.
"""
import re, time
from urllib.parse import urljoin
from .net import session, request

DOMAINS = ["anime-sama.to", "anime-sama.si", "anime-sama.tv",
           "anime-sama.org", "anime-sama.fr", "anime-sama.eu"]
STATUS_URL = "https://anime-sama.pw"   # page de statut officielle
HOSTS = re.compile(r"^/catalogue/([^/]+)/?$")
_SKIP = ("scan", "manhwa", "webtoon", "manhua", "manga", "novel", "light novel")


class AnimeSama:
    def __init__(self, domain=None):
        self.domain = domain or self._pick_domain()
        self.base = f"https://{self.domain}"
        self.s = session({"Accept-Language": "fr-FR,fr;q=0.9"})

    # ── infra ────────────────────────────────────────────────
    def _pick_domain(self):
        """Domaine actif. L'URL canonique est anime-sama.to.

        1. Page de statut officielle (anime-sama.pw) : son endpoint
           ?check=<domaine> teste le domaine CÔTÉ SERVEUR, donc fonctionne
           même quand notre IP est bloquée par Cloudflare.
        2. Essai direct en secours (notre IP peut peut-être passer).
        3. Fallback : anime-sama.to.
        """
        s = session({"Accept-Language": "fr-FR,fr;q=0.9"})
        # 1. statut serveur via anime-sama.pw
        for d in DOMAINS:
            try:
                r = s.get(f"{STATUS_URL}/?check={d}&_={int(time.time() * 1000)}",
                          timeout=6, headers={"Referer": f"{STATUS_URL}/"})
                if r.status_code == 200 and r.json().get("status") == "online":
                    return d
            except Exception:
                continue
        # 2. essai direct rapide
        for d in DOMAINS:
            try:
                r = s.get(f"https://{d}/", timeout=6)
                if r.status_code == 200 and len(r.text) > 5000:
                    return d
            except Exception:
                continue
        # 3. défaut canonique
        return DOMAINS[0]

    def _get(self, path):
        url = path if path.startswith("http") else self.base + path
        r = request(self.s, "GET", url, headers={"Referer": self.base + "/"})
        return r

    # ── recherche ────────────────────────────────────────────
    def search(self, query, limit=30):
        r = request(self.s, "POST",
                    f"{self.base}/template-php/defaut/fetch.php",
                    data={"query": query},
                    headers={"X-Requested-With": "XMLHttpRequest",
                             "Referer": self.base + "/"})
        if r.status_code != 200:
            return []
        out, seen = [], set()
        for m in re.finditer(
            r'<a[^>]+href="([^"]+)"[^>]*class="[^"]*asn-search-result[^"]*"(.*?)</a>',
            r.text, re.S):
            href, inner = m.group(1), m.group(2)
            t = re.search(r'<h3[^>]*>(.*?)</h3>', inner, re.S)
            title = re.sub(r"<[^>]+>", "", t.group(1)).strip() if t else ""
            title = re.sub(r"\s+", " ", title)
            if not title or href in seen:
                continue
            seen.add(href)
            slug = (HOSTS.search(href.replace(self.base, "")) or [None, ""])[1] \
                if "/catalogue/" in href else href.rstrip("/").split("/")[-1]
            out.append({"source": "anime-sama", "title": title,
                        "slug": slug, "url": urljoin(self.base + "/", href)})
            if len(out) >= limit:
                break
        return out

    # ── saisons ──────────────────────────────────────────────
    def seasons(self, slug):
        r = self._get(f"/catalogue/{slug}/")
        if r.status_code != 200:
            return []
        out, seen = [], set()
        pat = re.compile(
            r'panneau(?:Anime|Film|Scan|Visual)\s*\(\s*["\'](.*?)["\']\s*,\s*["\'](.*?)["\']\s*\)')
        for name, path in pat.findall(r.text):
            if name.lower() == "nom" or path.lower() == "url":
                continue
            if any(k in (name + " " + path).lower() for k in _SKIP):
                continue
            if name in seen:
                continue
            seen.add(name)
            out.append({"name": name,
                        "url": f"{self.base}/catalogue/{slug}/{path.strip('/')}/"})
        return out

    # ── épisodes ─────────────────────────────────────────────
    def episodes(self, slug, season_url=None, lecteurs_only=True):
        """Retourne [{number, mirrors:{lecteur_idx: url}}] + la liste des hôtes."""
        if season_url is None:
            ss = self.seasons(slug)
            if not ss:
                return []
            season_url = ss[0]["url"]
        if not season_url.endswith("/"):
            season_url += "/"
        r = self._get(season_url)
        if r.status_code != 200:
            return []
        m = re.search(r"<script[^>]+src=['\"]([^'\"]*episodes\.js[^'\"]*)['\"]", r.text)
        if not m:
            return []
        js_url = urljoin(season_url, m.group(1))
        jr = self._get(js_url)
        if jr.status_code != 200:
            return []

        blocks = {}
        for name, content in re.findall(
                r"var\s+(eps\d+)\s*=\s*\[(.*?)\]\s*;", jr.text, re.S):
            blocks[name] = re.findall(r"['\"](https?://[^'\"]+)['\"]", content)
        if not blocks:
            return []

        keys = sorted(blocks, key=lambda k: int(k[3:]))
        n = max(len(blocks[k]) for k in keys)
        eps = []
        for i in range(n):
            mirrors = {k: blocks[k][i] for k in keys if i < len(blocks[k])}
            if mirrors:
                eps.append({"number": i + 1, "mirrors": mirrors,
                            "referer": season_url})
        return eps

    # ── résolution ───────────────────────────────────────────
    def resolve(self, slug, number, season_url=None, prefer=None):
        """Retourne l'URL d'embed de l'épisode `number` (1-based)."""
        eps = self.episodes(slug, season_url)
        ep = next((e for e in eps if e["number"] == number), None)
        if not ep:
            return None
        order = sorted(ep["mirrors"], key=lambda k: int(k[3:]))
        if prefer:
            order = [k for k in order if prefer in ep["mirrors"][k]] or order
        k = order[0]
        return {"url": ep["mirrors"][k], "host": ep["mirrors"][k].split("/")[2],
                "lecteur": k, "referer": ep["referer"], "type": "embed"}

    def hosts(self, slug, season_url=None):
        """Liste les hôtes distincts rencontrés dans une saison."""
        eps = self.episodes(slug, season_url)
        seen = {}
        for e in eps:
            for k, u in e["mirrors"].items():
                seen.setdefault(u.split("/")[2], set()).add(k)
        return {h: sorted(v) for h, v in seen.items()}
