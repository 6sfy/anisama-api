from src.api.utils.http import send_json


def handle(handler, params):
    title = (params.get("title", [None])[0] or "").strip()
    if not title:
        send_json(handler, {"error": "Missing 'title'"}, 400)
        return

    try:
        import httpx
        ql = """
        query($s:String){Page(perPage:1){media(search:$s,type:ANIME){title{romaji english}
        averageScore status episodes duration studios{nodes{name}} genres description(asHtml:false)
        seasonYear source format}}}
        """
        r = httpx.post("https://graphql.anilist.co",
            json={"query": ql, "variables": {"s": title}}, timeout=8)
        if r.status_code == 200:
            data = r.json().get("data", {}).get("Page", {}).get("media", [])
            if data:
                send_json(handler, data[0])
                return
    except Exception:
        pass
    send_json(handler, {"error": "Not found"}, 404)
