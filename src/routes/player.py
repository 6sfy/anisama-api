import html
import json

from src.helpers import send_json, is_safe_external_url


def handle(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    title = (params.get("title", ["Anime"])[0] or "Anime").strip()

    if not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return

    safe_title = html.escape(title[:200])
    safe_url_attr = html.escape(url, quote=True)
    safe_url_js = json.dumps(url)
    html_page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe_title} — anisama</title>
    <meta http-equiv="Content-Security-Policy" content="default-src 'self' https: data:; frame-src *; style-src 'unsafe-inline'; script-src 'self'">
    <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#000;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;flex-direction:column;min-height:100vh}}
    .h{{padding:12px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #222;background:#0a0a0a}}
    .h a{{color:#ff4500;text-decoration:none;font-size:13px}}
    .h span{{color:#ff4500;font-weight:600;font-size:14px}}
    .p{{flex:1;display:flex;align-items:center;justify-content:center;background:#000;padding:20px}}
    .p iframe{{width:100%;max-width:1280px;aspect-ratio:16/9;border:none;border-radius:8px}}
    .i{{padding:12px 20px;border-top:1px solid #222;font-size:12px;color:#666;background:#0a0a0a}}
    .i button{{background:#222;border:none;color:#fff;padding:4px 12px;border-radius:4px;cursor:pointer;margin-left:8px;font-size:12px}}
    </style></head><body>
    <div class="h"><a href="/">&larr;</a><span>{safe_title}</span></div>
    <div class="p"><iframe src="{safe_url_attr}" allowfullscreen allow="autoplay;encrypted-media" referrerpolicy="no-referrer"></iframe></div>
    <div class="i"><span>Source: {html.escape(url[:60])}...</span><button onclick="navigator.clipboard.writeText({safe_url_js})">Copy</button></div>
    </body></html>"""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(html_page.encode("utf-8"))