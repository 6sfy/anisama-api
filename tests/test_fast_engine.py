"""Tests du fast engine côté API — offline, réseau du moteur mocké.

Couvre :
- fast_search : conversion + filtrage scan/manga
- fast_episodes : flatten anime-sama (numérotation absolue) + franime
- fast_resolve : embed direct anime-sama + franime (indexes 0-based)
- routes engine : /api/v2/seasons, /api/v2/hosts, /api/v2/engine
"""

import io
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import fast_engine
from src.anime_engine import anime_sama as AS
from src.anime_engine import franime as FR

CATALOGUE_HTML = """
<html><body>
<script>
panneauAnime("Avec Fillers", "saison1/vostfr");
panneauAnime("Sans Fillers", "saison1hs/vostfr");
</script>
<script src='https://anime-sama.to/catalogue/naruto/saison1/vostfr/episodes.js?filever=18916'></script>
</body></html>
"""

CATALOGUE_HTML_S2 = """
<html><body>
<script src='https://anime-sama.to/catalogue/naruto/saison1hs/vostfr/episodes.js?filever=18916'></script>
</body></html>
"""

EPISODES_JS_S1 = """
var eps1 = ['https://lpayer.embed4me.com/#sat5e', 'https://lpayer.embed4me.com/#z9j18'];
var eps2 = ['https://ansembed.net/embed-a1.html', 'https://ansembed.net/embed-b2.html'];
"""

EPISODES_JS_S2 = """
var eps1 = ['https://sendvid.com/abc'];
"""

SEARCH_HTML = """
<a href="https://anime-sama.to/catalogue/naruto/" class="asn-search-result">
  <h3 class="asn-search-result-title">Naruto</h3>
</a>
<a href="https://anime-sama.to/scan/naruto-scan/" class="asn-search-result">
  <h3 class="asn-search-result-title">Naruto Scan</h3>
</a>
"""

FRANIME_CATALOG = [{
    "id": 13051, "title": "Boruto: Naruto Next Generations", "titleO": "BORUTO",
    "titles": {"en_jp": "Boruto"}, "saisons": [
        {"title": "Saison 1", "episodes": [
            {"title": "Épisode 1", "lang": {"vo": {"lecteurs": ["vidmoly", "sibnet"]},
                                             "vf": {"lecteurs": ["vidmoly"]}}}]},
    ],
}]

FRANIME_SEASON = {"kitsuId": 13051, "episodes": [
    {"number": 1, "title": "Boruto Uzumaki !", "thumbnail": "", "airDate": "2017-04-05", "_id": "x1"},
]}


class FakeResponse:
    def __init__(self, text="", json_data=None, status_code=200):
        self.text = text
        self.status_code = status_code
        self.headers = {}
        self._json = json_data

    def json(self):
        return self._json if self._json is not None else json.loads(self.text or "{}")


@pytest.fixture
def offline_engine(monkeypatch):
    """Moteur avec réseau mocké : anime-sama offline + franime offline."""
    monkeypatch.setattr(AS.AnimeSama, "_pick_domain", lambda self: "anime-sama.to")

    def fake_as_request(sess, method, url, **kw):
        if "fetch.php" in url and method == "POST":
            return FakeResponse(SEARCH_HTML)
        if "episodes.js" in url:
            return FakeResponse(EPISODES_JS_S2 if "saison1hs" in url else EPISODES_JS_S1)
        if "/catalogue/" in url:
            return FakeResponse(CATALOGUE_HTML_S2 if "saison1hs" in url else CATALOGUE_HTML)
        return FakeResponse("<html></html>")

    monkeypatch.setattr(AS, "request", fake_as_request)

    fr = FR.Franime()
    monkeypatch.setattr(fr, "_get", lambda path: (
        FakeResponse(json_data=FRANIME_CATALOG) if path == "animes"
        else FakeResponse(json_data=FRANIME_SEASON)
        if path.startswith("anime-seasons/")
        else FakeResponse(text="https://franime.fr/watch2/?a=1&b=2")
    ))

    fast_engine._cache.clear()
    e = fast_engine.Engine()
    e.as_ = AS.AnimeSama()
    e.fr = fr
    monkeypatch.setattr(fast_engine, "engine", lambda: e)
    return e


def test_fast_search_filters_scans(offline_engine):
    out = fast_engine.fast_search("naruto")
    assert out, "au moins un résultat"
    titles = [r["title"] for r in out]
    assert "Naruto" in titles
    assert not any("scan" in t.lower() for t in titles), "les scans doivent être filtrés"
    assert all(set(r) >= {"title", "link", "slug", "score", "source"} for r in out)


def test_fast_search_scores_are_bounded(offline_engine):
    out = fast_engine.fast_search("boruto")
    assert out
    # Le score brut FRAnime (préfixe + bonus) peut dépasser 100 : il doit être borné.
    assert all(0 <= r["score"] <= 100 for r in out)
    franime = [r for r in out if r["source"] == "franime"]
    assert franime and all(r["score"] <= 100 for r in franime)


def test_clamp_score():
    assert fast_engine.clamp_score(143) == 100
    assert fast_engine.clamp_score(-5) == 0
    assert fast_engine.clamp_score("71") == 71
    assert fast_engine.clamp_score(None) == 0


class FakeHandler:
    def __init__(self):
        self.status = None
        self.headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        pass


def test_fast_search_anime_sama_relevance(monkeypatch):
    from src import fast_engine

    class FakeEngine:
        def search(self, q, limit=30):
            return [
                {"source": "anime-sama", "title": "Boruto",
                 "url": "https://anime-sama.to/catalogue/boruto/", "slug": "boruto"},
                {"source": "anime-sama", "title": "Naruto",
                 "url": "https://anime-sama.to/catalogue/naruto/", "slug": "naruto"},
            ]

    monkeypatch.setattr(fast_engine, "engine", lambda: FakeEngine())
    out = fast_engine._search_uncached("naruto", 10)
    scores = {r["title"]: r["score"] for r in out}
    assert scores["Naruto"] == 100
    assert scores["Boruto"] == 80


def test_search_route_clamps_engine_scores(monkeypatch):
    from src.routes import search as search_route

    monkeypatch.setattr(search_route.cache_mod, "load_catalog", lambda: [])
    monkeypatch.setattr(search_route, "_get_alt_results", lambda q: [])
    monkeypatch.setattr(search_route.fast_engine, "enabled", lambda: True)
    monkeypatch.setattr(search_route.fast_engine, "fast_search", lambda q: [
        {"title": "High Card", "link": "https://x", "slug": "high-card",
         "score": 143, "source": "franime"},
    ])
    monkeypatch.setattr(search_route.fast_engine, "fast_seasons", lambda *a, **k: [])

    handler = FakeHandler()
    search_route.handle(handler, {"q": ["hi"]})
    body = json.loads(handler.wfile.getvalue())
    assert body["results"][0]["score"] == 100


def test_resolve_bind_address_prefers_server_port(monkeypatch):
    from src.server import resolve_bind_address

    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("SERVER_PORT", "27202")
    monkeypatch.setenv("PORT", "20100")
    assert resolve_bind_address() == ("0.0.0.0", 27202)

    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.delenv("SERVER_PORT")
    assert resolve_bind_address() == ("127.0.0.1", 20100)

    monkeypatch.delenv("PORT")
    assert resolve_bind_address() == ("127.0.0.1", 20100)


def test_health_route():
    from src.routes import engine as engine_route

    handler = FakeHandler()
    engine_route.handle_health(handler, {})
    assert json.loads(handler.wfile.getvalue())["status"] == "ok"


def test_bind_server_falls_back_to_wildcard():
    from src.server import bind_server

    srv = bind_server("192.0.2.1", 0)  # TEST-NET-1 : jamais une interface locale
    try:
        assert srv.server_address[0] == "0.0.0.0"
    finally:
        srv.server_close()


def test_fast_episodes_animesama_flattened(offline_engine):
    eps = fast_engine.fast_episodes("anime-sama", "naruto")
    # saison 1 (2 eps) + saison 1hs (1 ep) -> numérotation absolue 1..3
    assert [e["number"] for e in eps] == [1, 2, 3]
    assert eps[0]["season_number"] == 1 and eps[2]["season_number"] == 1
    assert eps[0]["mirrors"] == ["https://lpayer.embed4me.com/#sat5e",
                                 "https://ansembed.net/embed-a1.html"]
    assert eps[0]["lang"] == "vostfr"
    assert eps[2]["season"].startswith("Sans")


def test_fast_episodes_franime(offline_engine):
    eps = fast_engine.fast_episodes("franime", "13051")
    assert len(eps) == 1
    assert eps[0]["number"] == 1
    assert eps[0]["url"] == "franime://13051/1/1"
    assert eps[0]["lang"] == "vostfr"
    assert eps[0]["lecteurs"]["vo"] == ["vidmoly", "sibnet"]


def test_fast_resolve_animesama(offline_engine):
    r = fast_engine.fast_resolve("anime-sama", "naruto", 3)  # ep 3 = saison 2
    assert r["url"] == "https://sendvid.com/abc"
    assert r["type"] == "embed"
    assert "saison1hs" in r["referer"]


def test_fast_resolve_franime(offline_engine):
    r = fast_engine.fast_resolve("franime", "13051", 1)
    assert r["url"] == "https://franime.fr/watch2/?a=1&b=2"
    assert r["referer"] == "https://franime.fr/"


def test_fast_seasons_and_hosts(offline_engine):
    ss = fast_engine.fast_seasons("anime-sama", "naruto")
    assert [s["name"] for s in ss] == ["Avec Fillers", "Sans Fillers"]
    hosts = fast_engine.fast_hosts("naruto")
    assert "lpayer.embed4me.com" in hosts and "ansembed.net" in hosts


def test_cache_ttl_hit(offline_engine):
    fast_engine.fast_search("naruto")
    n = fast_engine.cache_size()
    fast_engine.fast_search("naruto")  # 2e appel -> cache
    assert fast_engine.cache_size() == n
