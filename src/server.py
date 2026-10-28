#!/usr/bin/env python3
"""Anisama API server — HTTP server with JSON endpoints."""

import errno
import hmac
import html
import http.server
import json
import logging
import os
import re
import socketserver
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

load_dotenv()

from src import __version__ as API_VERSION
from src.routes import ROUTES, POST_ROUTES, LEGACY_PREFIXES
from src.routes.legacy import handle as legacy_handle
from src.db.connection import init_db
from src.db.models import import_catalog, get_indexed_count
from src.db.indexer import BackgroundIndexer
from src.helpers import send_json, send_internal_error
from anisama import cache as cache_mod
from anisama.scraper.base import find_active_domain

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

STATIC_DIR = Path(__file__).resolve().parent / "web"
CACHE_DIR = _project_root / "api_cache"
CACHE_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("anisama-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)

# ── Security knobs ──

def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# Max simultaneous in-flight requests (rest rejected with 503)
MAX_CONCURRENCY = _env_int("ANISAMA_MAX_CONCURRENCY", 20)

# Rate limits: requests per IP per window, independent budget per class.
# 0 disables a class (e.g. ANISAMA_RATE_LIMIT_RESOLVE=0 on an open mirror).
RATE_LIMIT_WINDOW = _env_int("ANISAMA_RATE_LIMIT_WINDOW", 60)
RATE_LIMITS = {
    "light": _env_int("ANISAMA_RATE_LIMIT_GLOBAL", 60),
    "heavy": _env_int("ANISAMA_RATE_LIMIT_HEAVY", 20),
    "resolve": _env_int("ANISAMA_RATE_LIMIT_RESOLVE", 5),
}
HEAVY_PATHS = ("/api/v2/search", "/api/v2/episodes", "/api/v2/resolve",
               "/api/v2/seasons", "/api/v2/hosts", "/api/v2/info",
               "/api/resolve", "/api/episodes")
RESOLVE_PATHS = ("/api/v2/resolve-episode",)

# Optional bearer token. When ANISAMA_API_TOKEN is set, expensive endpoints
# require `Authorization: Bearer <token>` (or `X-API-Key`). Unset = public.
API_TOKEN = (os.environ.get("ANISAMA_API_TOKEN") or "").strip()
AUTH_PATHS = ("/api/v2/episodes", "/api/v2/resolve", "/api/v2/resolve-episode",
              "/api/v2/seasons", "/api/v2/hosts", "/api/episodes", "/api/resolve")

# Behind Cloudflare, set ANISAMA_TRUST_PROXY=1 so rate limiting applies to the
# real client (CF-Connecting-IP) instead of the shared Cloudflare edge IP.
TRUST_PROXY = (os.environ.get("ANISAMA_TRUST_PROXY") or "0").strip() == "1"

# CORS: same-origin needs no header. Default whitelist = prod domain + local.
CORS_ORIGINS = (os.environ.get("ANISAMA_CORS_ORIGINS") or "").strip()
CORS_DEFAULT_ORIGINS = (
    "https://anisama.sexcaller.lol",
    "http://localhost:20100",
    "http://127.0.0.1:20100",
)
_LOCAL_ORIGIN_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")

_SENSITIVE_PARAM_RE = re.compile(r"(?i)([?&]url=)[^&\s\"]+")


def _redact_sensitive(msg):
    """Mask url= query values in log lines (video URLs are privacy-sensitive)."""
    return _SENSITIVE_PARAM_RE.sub(r"\1REDACTED", msg)


def _cors_origin_allowed(origin):
    if not origin:
        return False
    if CORS_ORIGINS == "*":
        return True
    allowed = ([o.strip().rstrip("/") for o in CORS_ORIGINS.split(",") if o.strip()]
               if CORS_ORIGINS else list(CORS_DEFAULT_ORIGINS))
    normalized = origin.rstrip("/")
    return normalized in allowed or bool(_LOCAL_ORIGIN_RE.match(normalized))


class RateLimiter:
    """Per-IP sliding-window rate limiter (thread-safe, in-memory).

    Each IP keeps an independent budget per request class
    (light / heavy / resolve), so cheap requests never eat the heavy quota.
    """

    def __init__(self, limits, window):
        self.limits = limits
        self.window = window
        self._hits = {}
        self._lock = threading.Lock()

    def check(self, ip, tier="light"):
        now = time.time()
        limit = self.limits.get(tier, self.limits.get("light", 0))
        if limit <= 0:
            return True, 0, 0
        with self._lock:
            buckets = self._hits.get(ip)
            if buckets is None:
                buckets = {name: deque() for name in self.limits}
                self._hits[ip] = buckets
            bucket = buckets.setdefault(tier, deque())
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            allowed = len(bucket) < limit
            if allowed:
                bucket.append(now)
            remaining = max(0, limit - len(bucket))
            reset = int(self.window - (now - bucket[0])) + 1 if bucket else self.window
            self._maybe_prune(now)
            return allowed, remaining, max(1, reset)

    def _maybe_prune(self, now):
        """Drop idle IPs so spoofed/rotating addresses cannot grow memory forever."""
        if len(self._hits) < 4096:
            return
        stale = [ip for ip, buckets in self._hits.items()
                 if all(not b or now - b[-1] > self.window for b in buckets.values())]
        for ip in stale:
            self._hits.pop(ip, None)


RATE_LIMITER = RateLimiter(RATE_LIMITS, RATE_LIMIT_WINDOW)
CONCURRENCY = threading.BoundedSemaphore(MAX_CONCURRENCY)

_ERROR_NAMES = {
    400: "bad_request", 401: "unauthorized", 403: "forbidden",
    404: "not_found", 405: "method_not_allowed", 408: "request_timeout",
    413: "payload_too_large", 414: "uri_too_long", 415: "unsupported_media_type",
    429: "rate_limited", 500: "internal_error", 501: "not_implemented",
    503: "server_busy",
}

_ERROR_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{code} — anisama</title>
<style>body{{background:#0a0a0a;color:#eee;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
main{{text-align:center;padding:2rem}}h1{{font-size:3rem;margin:0 0 .5rem;color:#ff4500}}p{{color:#999;margin:.25rem 0}}a{{color:#ff4500}}</style>
</head><body><main><h1>{code}</h1><p>{title}.</p><p><a href="/">Back to the API documentation</a></p></main></body></html>"""

_CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    block_on_close = True
    allow_reuse_address = True


class APIHandler(http.server.SimpleHTTPRequestHandler):
    server_version = "anisama-api"
    sys_version = ""

    def version_string(self):
        return self.server_version

    def __init__(self, *args, **kwargs):
        self.request_id = uuid.uuid4().hex[:16]
        self._status_code = 200
        self._csp = None
        self._cache_control = "no-store"
        self._rate_limit = None
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def send_response(self, code, message=None):
        self._status_code = code
        super().send_response(code, message)

    def end_headers(self):
        origin = self.headers.get("Origin") if getattr(self, "headers", None) else None
        if origin:
            self.send_header("Vary", "Origin")
            if _cors_origin_allowed(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, Accept, Origin, Authorization, X-API-Key",
                )
                self.send_header("Access-Control-Max-Age", "600")

        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Strict-Transport-Security",
                         "max-age=31536000; includeSubDomains; preload")
        self.send_header("X-Request-ID", self.request_id)
        self.send_header("Cache-Control", self._cache_control)
        if self._csp:
            self.send_header("Content-Security-Policy", self._csp)
        if self._rate_limit:
            limit, remaining, reset = self._rate_limit
            self.send_header("RateLimit-Limit", str(limit))
            self.send_header("RateLimit-Remaining", str(remaining))
            self.send_header("RateLimit-Reset", str(reset))
        if self._status_code == 429:
            self.send_header("Retry-After", str(RATE_LIMIT_WINDOW))
        super().end_headers()

    # ── request context ──

    def _client_ip(self):
        if TRUST_PROXY:
            cf = self.headers.get("CF-Connecting-IP")
            if cf:
                return cf.strip()
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0]

    def _authorized(self, path):
        if not API_TOKEN:
            return True
        if not any(path.startswith(p) for p in AUTH_PATHS):
            return True
        auth = (self.headers.get("Authorization") or "").strip()
        supplied = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not supplied:
            supplied = (self.headers.get("X-API-Key") or "").strip()
        return bool(supplied) and hmac.compare_digest(supplied, API_TOKEN)

    def _check_access(self, path, tier):
        allowed, remaining, reset = RATE_LIMITER.check(self._client_ip(), tier)
        self._rate_limit = (RATE_LIMITS.get(tier, RATE_LIMITS["light"]), remaining, reset)
        if not allowed:
            send_json(self, {"error": "rate_limited", "request_id": self.request_id}, 429)
            return False
        if not self._authorized(path):
            send_json(self, {"error": "unauthorized", "request_id": self.request_id}, 401,
                      headers={"WWW-Authenticate": 'Bearer realm="anisama"'})
            return False
        return True

    # ── methods ──

    def do_OPTIONS(self):
        self.request_id = uuid.uuid4().hex[:16]
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        self.request_id = uuid.uuid4().hex[:16]
        if not CONCURRENCY.acquire(blocking=False):
            send_json(self, {"error": "server_busy", "request_id": self.request_id}, 503)
            return
        try:
            self._handle_post()
        finally:
            CONCURRENCY.release()

    def _handle_post(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        tier = "resolve" if any(path.startswith(p) for p in RESOLVE_PATHS) else "heavy"
        if not self._check_access(path, tier):
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 65536:
            send_json(self, {"error": "bad_request", "request_id": self.request_id}, 400)
            return
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise TypeError("not an object")
        except Exception:
            send_json(self, {"error": "invalid_json", "request_id": self.request_id}, 400)
            return

        handler = POST_ROUTES.get(path)
        if not handler:
            send_json(self, {"error": "not_found", "request_id": self.request_id}, 404)
            return
        try:
            handler(self, data)
        except Exception as exc:
            send_internal_error(self, exc, logger, path)

    def do_GET(self):
        self.request_id = uuid.uuid4().hex[:16]
        if not CONCURRENCY.acquire(blocking=False):
            send_json(self, {"error": "server_busy", "request_id": self.request_id}, 503)
            return
        try:
            self._handle_get()
        finally:
            CONCURRENCY.release()

    def _handle_get(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if any(path.startswith(p) for p in RESOLVE_PATHS):
            tier = "resolve"
        elif any(path.startswith(p) for p in HEAVY_PATHS):
            tier = "heavy"
        else:
            tier = "light"
        if not self._check_access(path, tier):
            return

        try:
            handler = ROUTES.get(path)
            if handler:
                handler(self, params)
            elif path in LEGACY_PREFIXES:
                legacy_handle(self, path, params)
            else:
                super().do_GET()
        except Exception as exc:
            send_internal_error(self, exc, logger, path)

    # ── static assets / unified error pages ──

    def send_head(self):
        path = urlparse(self.path).path
        is_api = path == "/api" or path.startswith("/api/")
        if path in ("/", "/index.html") or path.lower().endswith((".html", ".htm")):
            self._csp = _CSP_DOCS
        if not is_api and not path.startswith("/player"):
            self._cache_control = "public, max-age=3600"
        return super().send_head()

    def send_error(self, code, message=None, explain=None):
        path = getattr(self, "path", "") or ""
        if path == "/api" or path.startswith("/api/") or code == 429:
            send_json(self, {
                "error": _ERROR_NAMES.get(code, "error"),
                "request_id": self.request_id,
            }, code)
            return
        self._send_error_page(code)

    def _send_error_page(self, code):
        self._cache_control = "no-store"
        self._csp = _CSP_DOCS
        body = None
        if code == 404:
            try:
                body = (STATIC_DIR / "404.html").read_bytes()
            except OSError:
                body = None
        if body is None:
            title = _ERROR_NAMES.get(code, "error").replace("_", " ").title()
            body = _ERROR_HTML.format(code=code, title=html.escape(title)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if getattr(self, "command", "GET") != "HEAD":
            self.wfile.write(body)

    def log_message(self, format, *args):
        msg = _redact_sensitive(format % args)
        if len(msg) > 250:
            msg = msg[:250] + "..."
        logger.info("%s - %s [%s]", self.client_address[0], msg, self.request_id)


def bind_server(host, port):
    """ThreadedHTTPServer, avec repli sur 0.0.0.0 si HOST n'est pas local.

    Dans un conteneur Docker/Pterodactyl, l'IP publique n'est pas assignée
    à une interface : bind() échoue (EADDRNOTAVAIL) et il faut écouter sur
    le wildcard, le mapping de port du panel s'occupe du reste.
    """
    try:
        return ThreadedHTTPServer((host, port), APIHandler)
    except OSError as exc:
        unavailable = exc.errno in (errno.EADDRNOTAVAIL, 10049) or \
            getattr(exc, "winerror", None) == 10049
        if host in ("0.0.0.0", "::", "") or not unavailable:
            raise
        logger.warning(
            "HOST=%s n'est pas une interface locale du conteneur (%s) — repli sur 0.0.0.0",
            host, exc,
        )
        return ThreadedHTTPServer(("0.0.0.0", port), APIHandler)


def resolve_bind_address():
    """Adresse d'écoute : SERVER_PORT (Pterodactyl) > PORT > 20100.

    Sur Pterodactyl, seul le port alloué (SERVER_PORT) est mappé vers
    l'extérieur : c'est obligatoirement celui-ci qu'il faut écouter.
    """
    host = os.environ.get("HOST") or "0.0.0.0"
    port = os.environ.get("SERVER_PORT") or os.environ.get("PORT") or "20100"
    return host, int(port)


def main():
    host, port = resolve_bind_address()
    if os.environ.get("PORT") and os.environ.get("SERVER_PORT") \
            and os.environ["PORT"] != os.environ["SERVER_PORT"]:
        logger.warning(
            "PORT=%s ignoré : SERVER_PORT=%s (allocation Pterodactyl) est prioritaire",
            os.environ["PORT"], os.environ["SERVER_PORT"],
        )

    if os.environ.get("ANISAMA_FAST_ENGINE", "1") != "0":
        from src import fast_engine
        try:
            fast_engine.engine()
            logger.info("Fast engine: ACTIF (anime-sama + franime, embeds directs)")
        except Exception as exc:
            logger.warning("Fast engine: indisponible au démarrage (%s) — fallback historique", exc)
    else:
        logger.info("Fast engine: DÉSACTIVÉ (ANISAMA_FAST_ENGINE=0)")

    init_db()
    added = import_catalog()
    indexed, with_eps = get_indexed_count()
    logger.info("SQLite: {i} anime in DB, {a} added, {e} with episodes".format(i=indexed, a=added, e=with_eps))

    cat_len = len(cache_mod.load_catalog())
    if cat_len == 0:
        logger.info("Catalog empty, trying GitHub catalog...")
        gh = cache_mod.fetch_github_catalog()
        if gh:
            cat_len = len(gh)
            logger.info("GitHub catalog: {n} entries".format(n=cat_len))
        else:
            logger.info("GitHub failed, scraping from scratch...")
            domain = find_active_domain()
            if domain:
                cache_mod.download_combined_catalog(domain, enrich=False)
                cat_len = len(cache_mod.load_catalog())
                logger.info("Scraped {n} entries".format(n=cat_len))
        import_catalog()
        indexed, with_eps = get_indexed_count()

    indexer = BackgroundIndexer()
    indexer.start()
    logger.info("Background indexer started")

    def _daily_scrape():
        while True:
            time.sleep(86400)
            try:
                logger.info("Daily scrape: checking for new entries...")
                domain = find_active_domain()
                if not domain:
                    continue
                before = len(cache_mod.load_catalog())
                cache_mod.download_combined_catalog(domain, enrich=False)
                after = len(cache_mod.load_catalog())
                added = import_catalog()
                logger.info("Daily scrape: {before} -> {after} entries ({new} new in catalog, {db} new in DB)".format(
                    before=before, after=after, new=after-before, db=added))
            except Exception as exc:
                logger.error("Daily scrape error: {e}".format(e=exc))

    threading.Thread(target=_daily_scrape, daemon=True).start()
    logger.info("Daily scraper started (every 24h)")

    server = bind_server(host, port)
    host, port = server.server_address[0], server.server_address[1]

    logger.info("=" * 60)
    logger.info("anisama Central API v2 — v%s", API_VERSION)
    logger.info("Listening on http://{h}:{p}".format(h=host, p=port))
    logger.info("Rate limits: %s", RATE_LIMITS)
    logger.info("Auth token: %s", "ACTIF" if API_TOKEN else "désactivée")
    logger.info("Trust proxy (CF-Connecting-IP): %s", "oui" if TRUST_PROXY else "non")
    logger.info("Endpoints:")
    logger.info("  GET /api/v2/search?q=QUERY")
    logger.info("  GET /api/v2/catalog?source=SOURCE&page=1&limit=50&q=QUERY")
    logger.info("  GET /api/v2/stats")
    logger.info("  GET /api/v2/episodes?source=SOURCE&slug=SLUG")
    logger.info("  GET /api/v2/resolve?url=URL&source=SOURCE")
    logger.info("  GET /api/v2/resolve-episode?source=SOURCE&slug=SLUG&num=NUM")
    logger.info("  GET /api/v2/sources")
    logger.info("  GET /api/v2/info?title=TITLE")
    logger.info("  GET /api/v2/seasons?source=SOURCE&slug=SLUG   (fast engine)")
    logger.info("  GET /api/v2/hosts?slug=SLUG&season_url=URL    (fast engine)")
    logger.info("  GET /api/v2/engine                            (fast engine status)")
    logger.info("  GET /health                                   (liveness probe)")
    logger.info("  GET /player?url=URL&title=TITLE")
    logger.info("Catalog: {n} entries".format(n=len(cache_mod.load_catalog())))
    logger.info("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
