"""Garde-fous sécurité — erreurs opaques, rate limiting, CORS, 404 unifié."""

import http.client
import io
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import server as srv
from src.helpers import is_safe_external_url, send_internal_error


class FakeHandler:
    command = "GET"
    request_id = "test-request-id"

    def __init__(self):
        self.status = None
        self.headers = {}
        self.client_address = ("127.0.0.1", 12345)
        self.wfile = io.BytesIO()

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.headers[key] = value

    def end_headers(self):
        pass


def test_internal_error_is_opaque():
    handler = FakeHandler()
    try:
        raise ValueError("unknown url type: '/'")
    except ValueError as exc:
        send_internal_error(handler, exc)

    raw = handler.wfile.getvalue().decode("utf-8")
    assert json.loads(raw) == {"error": "internal_error", "request_id": "test-request-id"}
    assert "unknown url" not in raw
    assert "ValueError" not in raw


def test_rate_limiter_tiers_are_independent():
    limiter = srv.RateLimiter({"light": 3, "heavy": 1, "resolve": 1}, 60)

    for _ in range(3):
        assert limiter.check("1.2.3.4", "light")[0]
    allowed, remaining, reset = limiter.check("1.2.3.4", "light")
    assert not allowed
    assert remaining == 0
    assert reset >= 1

    assert limiter.check("1.2.3.4", "heavy")[0]
    assert not limiter.check("1.2.3.4", "heavy")[0]

    assert limiter.check("5.6.7.8", "light")[0]


def test_rate_limiter_zero_disables_tier():
    limiter = srv.RateLimiter({"light": 0}, 60)
    for _ in range(10):
        assert limiter.check("1.2.3.4", "light")[0]


def test_client_ip_trusted_proxy(monkeypatch):
    from src.limits import client_ip

    monkeypatch.setenv("ANISAMA_TRUST_PROXY", "auto")
    handler = FakeHandler()
    handler.client_address = ("10.0.0.5", 1234)
    handler.headers = {"CF-Connecting-IP": "203.0.113.9"}
    assert client_ip(handler) == "203.0.113.9"

    # A public peer not in Cloudflare/custom ranges cannot spoof the header.
    handler.client_address = ("8.8.8.8", 1234)
    handler.headers = {"CF-Connecting-IP": "203.0.113.9"}
    assert client_ip(handler) == "8.8.8.8"

    monkeypatch.setenv("ANISAMA_TRUST_PROXY", "1")
    assert client_ip(handler) == "203.0.113.9"

    monkeypatch.setenv("ANISAMA_TRUST_PROXY", "0")
    assert client_ip(handler) == "8.8.8.8"


def test_client_ip_xff_and_invalid_values(monkeypatch):
    from src.limits import client_ip

    monkeypatch.setenv("ANISAMA_TRUST_PROXY", "auto")
    handler = FakeHandler()
    handler.client_address = ("127.0.0.1", 1234)
    handler.headers = {"X-Forwarded-For": "198.51.100.7, 10.0.0.2"}
    assert client_ip(handler) == "198.51.100.7"

    handler.headers = {"CF-Connecting-IP": "not-an-ip",
                       "X-Forwarded-For": "198.51.100.8"}
    assert client_ip(handler) == "198.51.100.8"


def test_cors_origin_whitelist(monkeypatch):
    monkeypatch.setattr(srv, "CORS_ORIGINS", "")
    assert srv._cors_origin_allowed("https://anisama.sexcaller.lol")
    assert srv._cors_origin_allowed("http://localhost:3000")
    assert not srv._cors_origin_allowed("https://evil.example")

    monkeypatch.setattr(srv, "CORS_ORIGINS", "https://foo.example")
    assert srv._cors_origin_allowed("https://foo.example")
    assert not srv._cors_origin_allowed("https://bar.example")

    monkeypatch.setattr(srv, "CORS_ORIGINS", "*")
    assert srv._cors_origin_allowed("https://evil.example")


def test_ssrf_guard_blocks_local_targets():
    assert not is_safe_external_url("file:///etc/passwd")
    assert not is_safe_external_url("javascript:alert(1)")
    assert not is_safe_external_url("http://127.0.0.1:8080/")
    assert not is_safe_external_url("http://[::1]/")
    assert not is_safe_external_url("http://169.254.169.254/latest/meta-data/")


def test_anime_sama_wins_search_tie():
    from src.routes.search import _merge_alt_result

    results = {
        "naruto": {
            "title": "Naruto",
            "link": "https://voiranime.rip/naruto/",
            "slug": "naruto",
            "score": 100,
            "sources": ["myfluneo"],
            "primary_source": "voiranime",
            "genres": [],
            "langs": ["vostfr"],
        }
    }
    _merge_alt_result(results, {
        "source": "anime-sama",
        "title": "Naruto",
        "link": "https://anime-sama.to/catalogue/naruto/",
        "slug": "naruto",
        "score": 100,
    })
    merged = results["naruto"]
    assert merged["primary_source"] == "anime-sama"
    assert merged["link"].startswith("https://anime-sama.to/")
    assert "anime-sama" in merged["sources"]


def test_source_counts_normalize_and_include_alts():
    from src.helpers import source_counts

    catalog = [
        {"source": None, "alt_source": ["voiranime", "franime"]},
        {"source": "voiranime", "alt_source": ["franime"]},
        {"source": "franime"},
    ]
    counts = source_counts(catalog)
    assert counts["anime-sama"] == 1
    assert counts["voiranime"] == 2
    assert counts["franime"] == 3


def test_sources_and_stats_share_counts(monkeypatch):
    from src.routes import sources, stats

    catalog = [
        {"source": None, "alt_source": ["voiranime", "franime"]},
        {"source": "voiranime", "alt_source": ["franime"]},
        {"source": "franime"},
    ]
    monkeypatch.setattr(sources.cache_mod, "load_catalog", lambda: catalog)
    monkeypatch.setattr(sources, "get_indexed_count", lambda: (len(catalog), 0))
    monkeypatch.setattr(stats, "get_indexed_count", lambda: (len(catalog), 0))

    src_handler = FakeHandler()
    sources.handle(src_handler, {})
    src_body = json.loads(src_handler.wfile.getvalue())

    stats_handler = FakeHandler()
    stats.handle(stats_handler, {})
    stats_body = json.loads(stats_handler.wfile.getvalue())

    src_counts = {s["id"]: s["count"] for s in src_body["sources"]}
    stats_counts = {k: v["count"] for k, v in stats_body["by_source"].items()}
    for source_id, count in src_counts.items():
        assert stats_counts.get(source_id, 0) == count


def test_episodes_cache_miss_is_rate_limited(monkeypatch):
    from src.routes import episodes
    from src.limits import RateLimiter

    monkeypatch.setattr(episodes, "EPISODE_LIMITER", RateLimiter({"episodes": 1}, 60))
    monkeypatch.setattr(episodes, "EPISODE_LIMIT", 1)
    monkeypatch.setattr(episodes, "get_anime_episodes", lambda **k: [])
    monkeypatch.setattr(episodes.fast_engine, "enabled", lambda: False)
    monkeypatch.setattr(episodes, "_ep_animesama", lambda url, slug=None: [])

    params = {"source": ["anime-sama"], "slug": ["missing"]}
    first = FakeHandler()
    episodes.handle(first, params)
    assert first.status == 200

    second = FakeHandler()
    episodes.handle(second, params)
    assert second.status == 429
    assert json.loads(second.wfile.getvalue())["error"] == "rate_limited"


def test_episodes_cache_hit_does_not_consume_limit(monkeypatch):
    from src.routes import episodes
    from src.limits import RateLimiter

    cached = [{"number": 1, "season": "S1", "lang": "vostfr"}]
    limiter = RateLimiter({"episodes": 1}, 60)
    monkeypatch.setattr(episodes, "EPISODE_LIMITER", limiter)
    monkeypatch.setattr(episodes, "EPISODE_LIMIT", 1)
    monkeypatch.setattr(episodes, "get_anime_episodes", lambda **k: cached)

    for _ in range(2):
        handler = FakeHandler()
        episodes.handle(handler, {"source": ["anime-sama"], "slug": ["cached"]})
        assert handler.status == 200

    limit, remaining, _reset = limiter.peek("127.0.0.1", "episodes")
    assert limit == 1
    assert remaining == 1


def test_rate_limiter_peek_does_not_consume():
    limiter = srv.RateLimiter({"light": 2}, 60)
    assert limiter.check("1.2.3.4", "light")[1] == 1
    before = limiter.peek("1.2.3.4", "light")
    after = limiter.peek("1.2.3.4", "light")
    assert before == after
    assert after[1] == 1


def test_stats_percentages_sum_to_100(monkeypatch):
    from src.routes import stats

    catalog = [
        {"source": "voiranime", "alt_source": ["franime"]},
        {"source": "franime"},
    ]
    monkeypatch.setattr(stats.cache_mod, "load_catalog", lambda: catalog)
    monkeypatch.setattr(stats, "get_indexed_count", lambda: (len(catalog), 0))

    handler = FakeHandler()
    stats.handle(handler, {})
    body = json.loads(handler.wfile.getvalue())
    total_pct = sum(v["percentage"] for v in body["by_source"].values())
    assert abs(total_pct - 100.0) < 0.2


def test_engine_status_is_minimal():
    from src.routes import engine as engine_route

    handler = FakeHandler()
    engine_route.handle_status(handler, {})
    body = json.loads(handler.wfile.getvalue())
    assert set(body) == {"engine", "enabled"}


def test_media_url_detection():
    from src.helpers import is_media_url, media_type

    assert is_media_url("https://cdn.example/hls/index.m3u8?t=abc")
    assert is_media_url("https://cdn.example/video.mp4?sig=1")
    assert media_type("https://cdn.example/video.mp4") == "mp4"
    assert not is_media_url("https://cdn.staticmoly.me/deskademeta.php?cv=x")


def test_extract_media_from_embed_page(monkeypatch):
    from src import helpers

    class FakeResponse:
        status_code = 200
        text = '<script>var src="https://cdn.example/hls/master.m3u8?t=abc";</script>'

    monkeypatch.setattr(helpers.requests, "get", lambda *a, **k: FakeResponse())
    assert helpers.extract_media_from_url("https://embed.example/x") == \
        "https://cdn.example/hls/master.m3u8?t=abc"


def test_catalog_invalid_pagination_returns_400():
    from src.routes import catalog

    handler = FakeHandler()
    catalog.handle(handler, {"page": ["abc"]})
    assert handler.status == 400
    assert json.loads(handler.wfile.getvalue())["error"] == "invalid_page_or_limit"


def test_unavailable_sources_return_501_not_traceback(monkeypatch):
    from src.routes import episodes, resolve

    monkeypatch.setattr(episodes, "playwright_available", lambda: False)
    monkeypatch.setattr(resolve, "playwright_available", lambda: False)

    handler = FakeHandler()
    episodes.handle(handler, {"source": ["myfluneo"], "slug": ["naruto"]})
    assert handler.status == 501
    assert json.loads(handler.wfile.getvalue())["error"] == "source_unavailable"

    handler = FakeHandler()
    resolve.handle_resolve(handler, {"url": ["https://example.com/x"], "source": ["myfluneo"]})
    assert handler.status == 501
    assert json.loads(handler.wfile.getvalue())["error"] == "source_unavailable"


def test_voiranime_uses_new_slug_url(monkeypatch):
    from src.routes import episodes
    import anisama.scraper.voiranime as vn

    seen = {}

    def fake_seasons(url):
        seen["url"] = url
        return [{"name": "Saga 1", "url": "https://voiranime.rip/one-piece/saga-1/"}]

    def fake_episodes(url):
        return [
            {"number": 2, "url": "https://voiranime.rip/one-piece/saga-1/episode-2/vostfr/",
             "langs": {"vostfr", "vf"}},
            {"number": 1, "url": "https://voiranime.rip/one-piece/saga-1/episode-1/vostfr/",
             "langs": {"vostfr"}},
        ]

    monkeypatch.setattr(vn, "voiranime_get_seasons", fake_seasons)
    monkeypatch.setattr(vn, "voiranime_get_episodes", fake_episodes)

    eps = episodes._ep_voiranime(None, "one-piece")
    assert seen["url"] == "https://voiranime.rip/one-piece/"
    assert [e["number"] for e in eps] == [1, 2]
    assert eps[1]["langs"] == ["vf", "vostfr"]


def test_voiranime_lang_urls():
    from src.routes.resolve import _voiranime_lang, _voiranime_lang_url

    assert _voiranime_lang("vo") == "vostfr"
    assert _voiranime_lang("vf") == "vf"
    assert _voiranime_lang(None) == "vostfr"
    assert _voiranime_lang_url(
        "https://voiranime.rip/one-piece/saga-1/episode-1/vostfr/", "vf"
    ) == "https://voiranime.rip/one-piece/saga-1/episode-1/vf/"


def test_episode_list_rewrite_preserves_cached_resolutions(monkeypatch):
    from src.routes import resolve

    monkeypatch.setattr(resolve, "get_anime_episodes", lambda **k: [
        {"number": 1, "url": "page-1", "season": "S1",
         "resolved_url": "https://cdn/ep1.m3u8", "resolved_type": "m3u8",
         "resolved_referer": "ref-1", "resolved_at": 123.0},
    ])
    entries = [{"number": 1}, {"number": 2, "resolved": "https://cdn/ep2.mp4"}]
    out = resolve._merge_existing_resolutions("slug", "source", entries)
    assert out[0]["resolved"] == "https://cdn/ep1.m3u8"
    assert out[0]["resolved_type"] == "m3u8"
    assert out[0]["season"] == "S1"
    assert out[0]["url"] == "page-1"
    assert out[1]["resolved"] == "https://cdn/ep2.mp4"


def test_voiranime_unresolved_iframe_is_embed(monkeypatch):
    from src.routes import resolve
    import anisama.resolver as resolver_mod

    monkeypatch.setattr(resolve, "is_safe_external_url", lambda *a, **k: True)
    monkeypatch.setattr(
        resolver_mod, "resolve_voiranime_episode",
        lambda url, lang: {"url": "https://video.sibnet.ru/shell.php?videoid=1",
                           "type": "raw"},
    )
    monkeypatch.setattr(resolver_mod, "resolve_url",
                        lambda url: {"url": url, "type": "raw"})
    monkeypatch.setattr(resolve, "extract_media_from_url", lambda url: None)

    handler = FakeHandler()
    resolve.handle_resolve(handler, {
        "source": ["voiranime"],
        "url": ["https://voiranime.rip/x/s/episode-1/vostfr/"],
        "lang": ["vo"],
    })
    body = json.loads(handler.wfile.getvalue())
    assert body["resolved"]["type"] == "embed"
    assert "sibnet" in body["resolved"]["url"]


def test_anime_sama_prefers_resolvable_mirror(monkeypatch):
    from src import fast_engine
    import anisama.resolver as resolver

    calls = []

    def fake_resolve(url):
        calls.append(url)
        if "ansembed" in url:
            return {"url": "https://cdn.example/stream.m3u8", "type": "m3u8"}
        return {"url": url, "type": "raw"}

    monkeypatch.setattr(resolver, "resolve_url", fake_resolve)

    r = fast_engine._resolve_best_mirror(
        ["https://uqload.vc/embed-1.html", "https://ansembed.net/embed-2.html"],
        "https://anime-sama.to/catalogue/x/saison1/vostfr/",
    )
    assert r["url"] == "https://cdn.example/stream.m3u8"
    assert r["type"] == "m3u8"
    # ansembed est testé en premier malgré sa position eps2
    assert calls[0].startswith("https://ansembed.net")


def test_best_mirror_extracts_media_when_resolver_returns_tracker(monkeypatch):
    from src import fast_engine
    import anisama.resolver as resolver

    monkeypatch.setattr(
        resolver, "resolve_url",
        lambda url: {"url": "https://cdn.staticmoly.me/deskademeta.php?cv=x",
                     "type": "mp4"},
    )
    monkeypatch.setattr(
        fast_engine, "extract_media_from_url",
        lambda url: "https://cdn.example/hls/master.m3u8?t=abc",
    )

    r = fast_engine._resolve_best_mirror(
        ["https://ansembed.net/embed-x.html"], "https://anime-sama.to/")
    assert r["url"] == "https://cdn.example/hls/master.m3u8?t=abc"
    assert r["type"] == "m3u8"


def test_to_direct_extracts_media_from_iframe(monkeypatch):
    from src.routes import resolve
    import anisama.resolver as resolver

    monkeypatch.setattr(
        resolver, "resolve_url",
        lambda url: {"url": "https://cdn.staticmoly.me/deskademeta.php?cv=x",
                     "type": "mp4"},
    )
    monkeypatch.setattr(
        resolve, "extract_media_from_url",
        lambda url: "https://cdn.example/hls/master.m3u8?t=abc",
    )

    r = resolve._to_direct({"url": "https://ansembed.net/embed-x.html", "type": "raw"})
    assert r["url"] == "https://cdn.example/hls/master.m3u8?t=abc"
    assert r["type"] == "m3u8"


def test_player_hls_uses_hlsjs(monkeypatch):
    from src.routes import player

    monkeypatch.setattr(player, "is_safe_external_url", lambda *a, **k: True)
    handler = FakeHandler()
    player.handle(handler, {"url": ["https://example.com/video.m3u8"],
                            "title": ["Test"]})
    html = handler.wfile.getvalue().decode("utf-8")
    assert handler.status == 200
    assert '<video id="video"' in html
    assert "hls.js@1.5.20" in html
    assert "media-src http: https: blob:" in handler._csp
    assert "nonce-" in handler._csp


def test_player_uses_ansembed_for_known_hls(monkeypatch):
    from src.routes import player

    monkeypatch.setattr(player, "is_safe_external_url", lambda *a, **k: True)
    handler = FakeHandler()
    player.handle(handler, {
        "url": ["https://prx-1476-ant.vmpx.online/hls2/03/02768/"
                "y18xw3fqcf6l_n/master.m3u8?t=x"],
        "title": ["Test"],
    })
    html = handler.wfile.getvalue().decode("utf-8")
    assert "https://ansembed.net/embed-y18xw3fqcf6l.html" in html
    assert '<video id="video"' not in html
    assert handler._referrer_policy == "strict-origin-when-cross-origin"
    assert player._ansembed_url(
        "https://cdn.staticmoly.me/deskademeta.php?cv=abc123&d=1") == \
        "https://ansembed.net/embed-abc123.html"


def test_player_non_hls_uses_iframe(monkeypatch):
    from src.routes import player

    monkeypatch.setattr(player, "is_safe_external_url", lambda *a, **k: True)
    handler = FakeHandler()
    player.handle(handler, {"url": ["https://example.com/embed"],
                            "title": ["Test"]})
    html = handler.wfile.getvalue().decode("utf-8")
    assert "<iframe" in html
    assert "hls.js" not in html


def test_voiranime_seasons_route(monkeypatch):
    from src.routes import engine as engine_route
    import anisama.scraper.voiranime as vn

    monkeypatch.setattr(
        vn, "voiranime_get_seasons",
        lambda url: [{"name": "Saison 1", "url": url + "saison-1/",
                      "langs": {"vf", "vostfr"}}],
    )
    handler = FakeHandler()
    engine_route.handle_seasons(handler, {"source": ["voiranime"], "slug": ["x"]})
    body = json.loads(handler.wfile.getvalue())
    assert handler.status == 200
    assert body["seasons"][0]["langs"] == ["vf", "vostfr"]


def test_anime_sama_skips_scan_seasons(monkeypatch):
    from src.anime_engine import anime_sama as AS

    class FakeResponse:
        status_code = 200
        text = (
            'panneauAnime("Saison 1", "saison1/vostfr");'
            'panneauAnime("Gaiden", "scan_one_shot/vf");'
        )

    a = AS.AnimeSama(domain="anime-sama.to")
    monkeypatch.setattr(a, "_get", lambda path: FakeResponse())
    assert [s["name"] for s in a.seasons("naruto")] == ["Saison 1"]


def test_sources_do_not_advertise_unavailable(monkeypatch):
    from src.routes import sources

    monkeypatch.setattr(sources, "playwright_available", lambda: False)
    monkeypatch.delenv("ANISAMA_ENABLE_VOIRANIME", raising=False)

    ids = [d["id"] for d in sources.advertised_sources()]
    assert "anime-sama" in ids
    assert "franime" in ids
    assert "myfluneo" not in ids
    assert "animoflix" not in ids
    assert "voiranime" in ids  # activée par défaut

    monkeypatch.setenv("ANISAMA_ENABLE_VOIRANIME", "0")
    assert "voiranime" not in [d["id"] for d in sources.advertised_sources()]

    monkeypatch.setenv("ANISAMA_ENABLE_VOIRANIME", "1")
    assert "voiranime" in [d["id"] for d in sources.advertised_sources()]


@pytest.fixture
def live_server():
    httpd = srv.ThreadedHTTPServer(("127.0.0.1", 0), srv.APIHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield base
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(5)


def _request(base, path, method="GET", headers=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(base + path, method=method, headers=headers or {})
    try:
        with opener.open(req, timeout=5) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def test_api_404_is_json_and_unified(live_server):
    status, headers, body = _request(live_server, "/api/v2/does-not-exist")
    assert status == 404
    assert headers["Content-Type"].startswith("application/json")
    payload = json.loads(body)
    assert payload["error"] == "not_found"
    assert payload["request_id"]
    assert headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_html_404_does_not_leak_python(live_server):
    status, headers, body = _request(live_server, "/does-not-exist")
    assert status == 404
    assert headers["Content-Type"].startswith("text/html")
    text = body.decode("utf-8")
    assert "Cette page n'existe pas" in text
    assert "Retour à la documentation" in text
    assert "Error code explanation" not in text
    assert "BaseHTTP" not in headers.get("Server", "")
    assert "Python" not in headers.get("Server", "")


def test_docs_have_csp_and_cache(live_server):
    status, headers, body = _request(live_server, "/")
    assert status == 200
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert "max-age" in headers["Cache-Control"]
    assert b"anisama" in body.lower()


def test_security_txt_is_served(live_server):
    status, headers, body = _request(live_server, "/.well-known/security.txt")
    assert status == 200
    assert b"Contact:" in body


def test_head_health_returns_headers_without_body(live_server):
    status, headers, body = _request(live_server, "/health", method="HEAD")
    assert status == 200
    assert body == b""
    assert headers["Content-Type"].startswith("application/json")


def test_head_api_route_returns_200(live_server):
    status, headers, body = _request(live_server, "/api/v2/engine", method="HEAD")
    assert status == 200
    assert body == b""
    assert headers["Content-Type"].startswith("application/json")


def test_robots_txt_blocks_api(live_server):
    status, headers, body = _request(live_server, "/robots.txt")
    assert status == 200
    assert headers["Content-Type"].startswith("text/plain")
    assert b"Disallow: /api/" in body


def test_api_health_is_not_cached(live_server):
    status, headers, body = _request(live_server, "/api/v2/health")
    assert status == 200
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body)["status"] == "ok"


def test_cors_preflight_whitelist(live_server):
    status, headers, _ = _request(
        live_server, "/api/v2/health", method="OPTIONS",
        headers={"Origin": "https://anisama.sexcaller.lol"},
    )
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == "https://anisama.sexcaller.lol"
    assert "Authorization" in headers["Access-Control-Allow-Headers"]

    status, headers, _ = _request(
        live_server, "/api/v2/health", method="OPTIONS",
        headers={"Origin": "https://evil.example"},
    )
    assert status == 204
    assert "Access-Control-Allow-Origin" not in headers


def test_bearer_token_protects_expensive_endpoints(live_server, monkeypatch):
    monkeypatch.setattr(srv, "API_TOKEN", "secret-token")

    status, headers, body = _request(live_server, "/api/v2/episodes?source=anime-sama&slug=x")
    assert status == 401
    assert headers["WWW-Authenticate"].startswith("Bearer")
    assert json.loads(body)["error"] == "unauthorized"

    # Health stays public.
    status, _, _ = _request(live_server, "/api/v2/health")
    assert status == 200


def _host_request(base, host):
    parsed = urlparse(base)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        conn.putrequest("GET", "/health", skip_host=True)
        conn.putheader("Host", host)
        conn.endheaders()
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_direct_ip_host_is_closed_without_response(live_server):
    with pytest.raises((http.client.RemoteDisconnected, ConnectionResetError, OSError)):
        _host_request(live_server, "203.0.113.10")


def test_allowed_host_still_responds(live_server):
    status, body = _host_request(live_server, "anisama.sexcaller.lol")
    assert status == 200
    assert json.loads(body)["status"] == "ok"


def test_rate_limit_is_per_client_ip(live_server, monkeypatch):
    monkeypatch.setenv("ANISAMA_TRUST_PROXY", "auto")
    monkeypatch.setattr(
        srv, "RATE_LIMITER",
        srv.RateLimiter({"light": 1, "heavy": 1, "resolve": 1}, 60),
    )
    first = {"CF-Connecting-IP": "198.51.100.10"}
    other = {"CF-Connecting-IP": "198.51.100.11"}

    status, _, _ = _request(live_server, "/api/v2/health", headers=first)
    assert status == 200
    status, _, _ = _request(live_server, "/api/v2/health", headers=first)
    assert status == 429
    status, _, _ = _request(live_server, "/api/v2/health", headers=other)
    assert status == 200


def test_origin_secret_required(live_server, monkeypatch):
    monkeypatch.setattr(srv, "ORIGIN_SECRET", "sekret")

    status, headers, body = _request(live_server, "/health")
    assert status == 403
    assert json.loads(body)["error"] == "forbidden"

    status, headers, body = _request(
        live_server, "/health", headers={"X-Origin-Secret": "sekret"})
    assert status == 200


def test_rate_limit_returns_429_and_headers(live_server, monkeypatch):
    monkeypatch.setattr(
        srv, "RATE_LIMITER",
        srv.RateLimiter({"light": 1, "heavy": 1, "resolve": 1}, 60),
    )
    status, headers, _ = _request(live_server, "/api/v2/health")
    assert status == 200
    assert headers["RateLimit-Remaining"] == "0"

    status, headers, body = _request(live_server, "/api/v2/health")
    assert status == 429
    assert headers["Retry-After"] == str(srv.RATE_LIMIT_WINDOW)
    assert json.loads(body)["error"] == "rate_limited"
