from src.helpers import send_json, is_safe_external_url
from src.routes.search import do_search_internal
from src.routes.sources import advertised_sources
from anisama.resolver import resolve_url


def handle(handler, path, params):
    if path == "/api/search":
        _search(handler, params)
    elif path == "/api/episodes":
        send_json(handler, [])
    elif path == "/api/resolve":
        _resolve(handler, params)
    elif path == "/api/sources":
        send_json(handler, {"sources": [
            {**d, "lang": "VOSTFR/VF"} for d in advertised_sources()
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
    if url and is_safe_external_url(url):
        result = resolve_url(url)
        send_json(handler, result or {"url": url, "type": "raw"})
    elif url:
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
    else:
        send_json(handler, {"error": "Missing url"}, 400)
