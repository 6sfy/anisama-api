import json


def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def get_param(params, key, default=None):
    val = params.get(key, [None])
    if isinstance(val, list):
        val = val[0] if val else None
    return (val or default or "").strip()
