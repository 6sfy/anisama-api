from src.api.utils.http import send_json
from src.api.routes.search import do_search_internal
from src.core import resolver as resolver_mod


def handle(handler, path, params):
    if path == "/api/search":
        _search(handler, params)
    elif path == "/api/episodes":
        send_json(handler, [])
    elif path == "/api/resolve":
        _resolve(handler, params)
    elif path == "/api/sources":
        send_json(handler, {"sources": [
            {"id": "anime-sama", "name": "Anime-Sama", "lang": "VOSTFR/VF", "url": "https://anime-sama.to"},
            {"id": "voiranime", "name": "Voiranime", "lang": "VOSTFR/VF", "url": "https://voiranime.rip"},
            {"id": "myfluneo", "name": "MyFluneo", "lang": "VOSTFR/VF", "url": "https://myfluneo.eu"},
        ]})


def _search(handler, params):
    q = (params.get("q", [None])[0] or "").strip()
    if q:
        resp = do_search_internal(q)
        send_json(handler, [{"title": r["title"], "link": r["link"], "source": r["primary_source"],
                             "score": r["score"], "anime_id": r["slug"]} for r in resp.get("results", [])])
    else:
        send_json(handler, {"error": "Missing q"}, 400)


def _resolve(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    if url:
        result = resolver_mod.resolve_url(url)
        send_json(handler, result or {"url": url, "type": "raw"})
    else:
        send_json(handler, {"error": "Missing url"}, 400)
