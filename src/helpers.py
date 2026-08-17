"""API-specific HTTP and text helpers.

These are kept locally because they depend on the HTTP handler interface
(not part of the core anisama library).
"""

import ipaddress
import json
import re
import socket
from functools import lru_cache
from urllib.parse import urlparse


# ── HTTP response helpers ──

def send_json(handler, data, status=200):
    """Send a JSON response via the HTTP handler."""
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


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


def is_safe_external_url(url):
    """SSRF guard for URLs that the server will fetch.

    Allows only http(s) URLs whose hostname resolves exclusively to
    public IP addresses (blocks loopback, private ranges, link-local,
    multicast, and metadata endpoints).
    """
    if not url or len(url) > 2048:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False
    return _host_is_public(host)


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
