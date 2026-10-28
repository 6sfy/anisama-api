"""API-specific HTTP and text helpers.

These are kept locally because they depend on the HTTP handler interface
(not part of the core anisama library).
"""

import importlib.util
import ipaddress
import json
import re
import socket
import uuid
from functools import lru_cache
from urllib.parse import urlparse

import requests


# ── HTTP response helpers ──

def request_id(handler):
    """Stable per-request identifier, used in logs and error payloads."""
    rid = getattr(handler, "request_id", None)
    if not rid:
        rid = uuid.uuid4().hex[:16]
        handler.request_id = rid
    return rid


def send_json(handler, data, status=200, headers=None):
    """Send a JSON response via the HTTP handler."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    for key, value in (headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    if getattr(handler, "command", "GET") != "HEAD":
        handler.wfile.write(body)


def send_internal_error(handler, exc, logger=None, context=""):
    """Log the real exception server-side, return an opaque client error.

    Never expose Python exception text to clients: it leaks module names,
    dependency state, and internal code paths (reconnaissance aid).
    """
    rid = request_id(handler)
    if logger is not None:
        logger.exception("%s failed (request_id=%s): %s", context or "request", rid, exc)
    send_json(handler, {"error": "internal_error", "request_id": rid}, 500)


def playwright_available():
    """True when the optional Playwright dependency can be imported."""
    try:
        return importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        return False


def get_param(params, key, default=None):
    """Extract a single query parameter value from parsed query dict."""
    val = params.get(key, [None])
    if isinstance(val, list):
        val = val[0] if val else None
    return (val or default or "").strip()


# ── SSRF guard ──

@lru_cache(maxsize=1024)
def _host_is_public(host):
    """Resolve a hostname and return False if any A record is a private/reserved IP."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def is_safe_external_url(url, max_len=2048):
    """SSRF guard for URLs that the server will fetch.

    Allows only http(s) URLs whose hostname resolves exclusively to
    public IP addresses (blocks loopback, private ranges, link-local,
    multicast, and metadata endpoints).

    max_len : longueur max de l'URL. Les URLs watch2 de FRAnime (payload
    base64 a..o) font ~3-5k caractères — passer max_len=16384 pour ces
    URLs issues du moteur (source fiable, pas une entrée client).
    """
    if not url or len(url) > max_len:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    return _host_is_public(host)


# ── Media URL helpers ──

_MEDIA_TYPE_RE = re.compile(r"\.(m3u8|mp4|webm|mkv)(?:[?#]|$)", re.I)
_MEDIA_URL_PATTERN = r"https?://[^\"'<>\s]+?\.(?:{ext})(?:\?[^\"'<>\s]*)?"
_MEDIA_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def media_type(url):
    """Return the media extension of a URL (m3u8/mp4/webm/mkv) or None."""
    match = _MEDIA_TYPE_RE.search(url or "")
    return match.group(1).lower() if match else None


def is_media_url(url):
    """True when the URL looks like a direct playable media file/playlist."""
    return media_type(url) is not None


def extract_media_from_url(url, timeout=15):
    """Fetch an embed page and extract the first direct m3u8/mp4 URL.

    Some resolvers return an intermediate tracking/redirect endpoint
    (e.g. staticmoly deskademeta.php) instead of the real stream. The
    embed page itself often exposes the signed m3u8 in its HTML/JS.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    parsed = urlparse(url)
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": _MEDIA_UA,
                "Accept-Language": "fr-FR,fr;q=0.9",
                "Referer": "{s}://{n}/".format(s=parsed.scheme, n=parsed.netloc),
            },
        )
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.text:
        return None
    text = r.text[:2_000_000].replace("\\/", "/").replace("&amp;", "&")
    for ext in ("m3u8", "mp4", "webm", "mkv"):
        match = re.search(_MEDIA_URL_PATTERN.format(ext=ext), text, re.I)
        if match:
            return match.group(0)
    return None


# ── Text helpers ──

def norm(t):
    """Normalize a title by removing everything except a-z0-9."""
    return re.sub(r"[^a-z0-9]", "", t.lower().strip()) if t else ""


def base_title(t):
    """Strip VF/VOSTFR/VO language suffix from a title.

    Returns (base_title, lang) tuple.
    """
    if not t:
        return "", ""
    base = t.strip()
    lang = ""
    if re.search(r'\s+[Vv][Ff]\s*$', base):
        base = re.sub(r'\s+[Vv][Ff]\s*$', '', base)
        lang = "vf"
    elif re.search(r'\s+[Vv][Oo][Ss][Tt][Ff][Rr]\s*$', base):
        base = re.sub(r'\s+[Vv][Oo][Ss][Tt][Ff][Rr]\s*$', '', base)
        lang = "vostfr"
    elif re.search(r'\s+[Vv][Oo]\s*$', base):
        base = re.sub(r'\s+[Vv][Oo]\s*$', '', base)
        lang = "vo"
    return base.strip(), lang
