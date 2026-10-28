import base64
import html
import json
import os
import re

from src.helpers import send_json, is_safe_external_url, media_type


def _ansembed_url(url):
    """Derive the ansembed player page from an Anime-Sama/Voiranime HLS URL.

    The server-generated m3u8 token is often bound to the resolver's IP/ASN;
    the iframe player resolves the stream from the visitor's browser instead.
    """
    match = re.search(r"/([A-Za-z0-9_-]+)_n/(?:master|index[^/]*)\.m3u8", url, re.I)
    if not match:
        match = re.search(r"[?&]cv=([A-Za-z0-9_-]+)", url)
    return "https://ansembed.net/embed-{i}.html".format(i=match.group(1)) if match else None


def handle(handler, params):
    url = (params.get("url", [None])[0] or "").strip()
    title = (params.get("title", ["Anime"])[0] or "Anime").strip()

    if not is_safe_external_url(url):
        send_json(handler, {"error": "Invalid or unsafe URL"}, 400)
        return

    safe_title = html.escape(title[:200])
    safe_url_attr = html.escape(url, quote=True)
    safe_url_js = json.dumps(url).replace("</", "<\\/")
    is_hls = media_type(url) == "m3u8"
    embed_url = _ansembed_url(url)
    iframe_policy = ' referrerpolicy="strict-origin-when-cross-origin"'
    iframe = ('<iframe src="{u}" allowfullscreen '
              'allow="autoplay;encrypted-media"{p}></iframe>')

    if embed_url:
        player = iframe.format(u=html.escape(embed_url, quote=True), p=iframe_policy)
        hls_script = ""
    elif is_hls:
        player = '<video id="video" controls playsinline></video>'
        hls_script = ('<script src="https://cdn.jsdelivr.net/npm/'
                      'hls.js@1.5.20/dist/hls.min.js"></script>')
    else:
        player = iframe.format(u=safe_url_attr, p=iframe_policy)
        hls_script = ""

    nonce = base64.b64encode(os.urandom(16)).decode()
    csp = (
        "default-src 'none'; script-src 'nonce-{n}' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline'; frame-src http: https:; "
        "img-src http: https: data:; media-src http: https: blob:; "
        "connect-src http: https:; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'self'"
    ).format(n=nonce)
    meta_csp = csp.replace("; frame-ancestors 'self'", "")

    html_page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{safe_title} — anisama</title>
    <meta http-equiv="Content-Security-Policy" content="{meta_csp}">
    <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#000;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;flex-direction:column;min-height:100vh}}
    .h{{padding:12px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid #222;background:#0a0a0a}}
    .h a{{color:#ff4500;text-decoration:none;font-size:13px}}
    .h span{{color:#ff4500;font-weight:600;font-size:14px}}
    .p{{flex:1;display:flex;align-items:center;justify-content:center;background:#000;padding:20px}}
    .p iframe,.p video{{width:100%;max-width:1280px;aspect-ratio:16/9;border:none;border-radius:8px;background:#000}}
    .i{{padding:12px 20px;border-top:1px solid #222;font-size:12px;color:#666;background:#0a0a0a}}
    .i button{{background:#222;border:none;color:#fff;padding:4px 12px;border-radius:4px;cursor:pointer;margin-left:8px;font-size:12px}}
    </style></head><body>
    <div class="h"><a href="/">&larr;</a><span>{safe_title}</span></div>
    <div class="p">{player}</div>
    <div class="i"><span>Source: {html.escape(url[:60])}...</span><button id="copyBtn">Copy</button></div>
    {hls_script}
    <script nonce="{nonce}">
    (function(){{
      var src = {safe_url_js};
      var copy = document.getElementById('copyBtn');
      if (copy) copy.addEventListener('click', function(){{ navigator.clipboard.writeText(src); }});
      var video = document.getElementById('video');
      if (!video) return;
      function native(){{ video.src = src; video.play().catch(function(){{}}); }}
      if (window.Hls && Hls.isSupported()) {{
        var hls = new Hls({{ enableWorker: false }});
        hls.loadSource(src);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, function(){{ video.play().catch(function(){{}}); }});
        hls.on(Hls.Events.ERROR, function(_, data){{ if (data && data.fatal) {{ hls.destroy(); native(); }} }});
      }} else {{ native(); }}
    }})();
    </script>
    </body></html>"""
    handler._csp = csp
    handler._referrer_policy = "strict-origin-when-cross-origin"
    handler._cache_control = "no-store"
    body = html_page.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    if getattr(handler, "command", "GET") != "HEAD":
        handler.wfile.write(body)
