#!/usr/bin/env python3
import http.server
import logging
import os
import socketserver
import sys
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from src.api.routes import ROUTES, LEGACY_PREFIXES
from src.api.routes.legacy import handle as legacy_handle
from src.api.db.connection import init_db
from src.api.db.models import import_catalog, get_indexed_count
from src.api.db.indexer import BackgroundIndexer
from src.core import cache as cache_mod
from src.core import scraper

_project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_project_root))

STATIC_DIR = _project_root / "src" / "web"
CACHE_DIR = _project_root / "api_cache"
CACHE_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("anisama-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)


class APIHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Origin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        logger.info("%s - %s", self.client_address[0], format % args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

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
            from src.api.utils.http import send_json
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
            domain = scraper.find_active_domain()
            if domain:
                cache_mod.download_combined_catalog(domain, enrich=False)
                cat_len = len(cache_mod.load_catalog())
                logger.info("Scraped {n} entries".format(n=cat_len))
        import_catalog()
        indexed, with_eps = get_indexed_count()

    indexer = BackgroundIndexer()
    indexer.start()
    logger.info("Background indexer started")

    server = socketserver.TCPServer((host, port), APIHandler)
    logger.info("=" * 60)
    logger.info("anisama Central API v2 — v1.1.0")
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
