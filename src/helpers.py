"""API-specific HTTP and text helpers.

These are kept locally because they depend on the HTTP handler interface
(not part of the core anisama library).
"""

import json
import re


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
