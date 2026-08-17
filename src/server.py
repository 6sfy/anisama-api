#!/usr/bin/env python3
"""Anisama API server — HTTP server with JSON endpoints."""

import http.server
import logging
import os
import re
import socketserver
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

load_dotenv()

from src.routes import ROUTES, LEGACY_PREFIXES
from src.routes.legacy import handle as legacy_handle
from src.db.connection import init_db
from src.db.models import import_catalog, get_indexed_count
from src.db.indexer import BackgroundIndexer
from src.helpers import send_json
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

# Max simultaneous in-flight requests (rest rejected with 503)
MAX_CONCURRENCY = 20

# Rate limit: requests per IP per window
RATE_LIMIT_GLOBAL = 120
RATE_LIMIT_HEAVY = 15  # expensive endpoints (resolve / episodes / scrape)
RATE_LIMIT_WINDOW = 60
HEAVY_PATHS = ("/api/v2/resolve", "/api/v2/resolve-episode", "/api/v2/episodes",
               "/api/resolve", "/api/episodes")

_SENSITIVE_PARAM_RE = re.compile(r"(?i)([?&]url=)[^&\s\"]+")


def _redact_sensitive(msg):
    """Mask url= query values in log lines (video URLs are privacy-sensitive)."""
    return _SENSITIVE_PARAM_RE.sub(r"\1REDACTED", msg)


class RateLimiter:
    """Per-IP sliding-window rate limiter (thread-safe, in-memory).
    Each IP keeps an independent budget per request class (light/heavy),
    so light requests never eat into the heavy quota.
    """

    def __init__(self, global_limit, heavy_limit, window):
        self.global_limit = global_limit
        self.heavy_limit = heavy_limit
        self.window = window
        self._hits = {}
        self._lock = threading.Lock()

    def check(self, ip, heavy=False):
        now = time.time()
        limit = self.heavy_limit if heavy else self.global_limit
        with self._lock:
            dq = self._hits.get(ip)
            if dq is None:
                dq = {True: deque(maxlen=4096), False: deque(maxlen=4096)}
                self._hits[ip] = dq
            bucket = dq[heavy]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


RATE_LIMITER = RateLimiter(RATE_LIMIT_GLOBAL, RATE_LIMIT_HEAVY, RATE_LIMIT_WINDOW)
CONCURRENCY = threading.BoundedSemaphore(MAX_CONCURRENCY)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    block_on_close = True
    allow_reuse_address = True


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "_status_code", 200) == 429:
            self.send_header("Retry-After", str(RATE_LIMIT_WINDOW))
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        msg = format % args
        msg = _redact_sensitive(msg)
        if len(msg) > 250:
            msg = msg[:250] + "..."
        logger.info("%s - %s", self.client_address[0], msg)

    def do_GET(self):
        if not CONCURRENCY.acquire(blocking=False):
            send_json(self, {"error": "Server busy, retry later"}, 503)
            return
        try:
            self._handle_get()
        finally:
            CONCURRENCY.release()

    def _handle_get(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        ip = self.client_address[0]
        heavy = any(path.startswith(p) for p in HEAVY_PATHS)
        if not RATE_LIMITER.check(ip, heavy=heavy):
            send_json(self, {"error": "Rate limit exceeded"}, 429)
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
            logger.exception("Error handling %s", self.path)
            send_json(self, {"error": str(exc)}, 500)


def main():
    port = int(os.environ.get("PORT", 20100))
    host = os.environ.get("HOST", "0.0.0.0")

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

    server = ThreadedHTTPServer((host, port), APIHandler)
    logger.info("=" * 60)
    logger.info("anisama Central API v2 — v2.0.0")
    logger.info("Listening on http://{h}:{p}".format(h=host, p=port))
    logger.info("Endpoints:")
    logger.info("  GET /api/v2/search?q=QUERY")
    logger.info("  GET /api/v2/catalog?source=SOURCE&page=1&limit=50&q=QUERY")
    logger.info("  GET /api/v2/stats")
    logger.info("  GET /api/v2/episodes?source=SOURCE&slug=SLUG")
    logger.info("  GET /api/v2/resolve?url=URL&source=SOURCE")
    logger.info("  GET /api/v2/resolve-episode?source=SOURCE&slug=SLUG&num=NUM")
    logger.info("  GET /api/v2/sources")
    logger.info("  GET /api/v2/info?title=TITLE")
    logger.info("  GET /player?url=URL&title=TITLE")
    logger.info("Catalog: {n} entries".format(n=len(cache_mod.load_catalog())))
    logger.info("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
