import logging
import threading
import time

from src.db.models import save_episodes, get_anime_episodes
from src.db.connection import get_db


class BackgroundIndexer:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._queue = []
        self._lock = threading.Lock()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def enqueue(self, title, slug, source, link=""):
        with self._lock:
            self._queue.append((title, slug, source, link))

    def _run(self):
        logger = logging.getLogger("anisama-indexer")
        while not self._stop.is_set():
            item = None
            with self._lock:
                if self._queue:
                    item = self._queue.pop(0)
            if item:
                title, slug, source, link = item
                logger.info("Indexing: %s (%s)", title, source)
                try:
                    self._index_one(title, slug, source, link)
                except Exception as e:
                    logger.error("Index error %s: %s", title, e)
            else:
                self._seed_from_catalog()
                if not self._queue:
                    time.sleep(5)

    def _seed_from_catalog(self):
        try:
            from anisama import cache as cache_mod
            cat = cache_mod.load_catalog()
            conn = get_db()
            for entry in cat:
                slug = entry.get("slug", "") or entry.get("link", "").rstrip("/").split("/")[-1]
                source = entry.get("source", "catalog")
                row = conn.execute("SELECT id FROM anime WHERE slug = ? AND source = ?", (slug, source)).fetchone()
                if not row:
                    self.enqueue(entry.get("title", ""), slug, source, entry.get("link", ""))
            conn.close()
        except Exception:
            pass

    def _index_one(self, title, slug, source, link):
        if source == "myfluneo":
            from anisama.scraper.myfluneo import myfluneo_episodes, myfluneo_resolve
            url = link or "https://myfluneo.eu/anime/{s}".format(s=slug)
            eps = myfluneo_episodes(url)
            for ep in eps[:5]:
                try:
                    r = myfluneo_resolve(ep["url"])
                    if r and r.get("url"):
                        ep["resolved"] = r["url"]
                        ep["resolved_type"] = r.get("type", "")
                except Exception:
                    pass
            save_episodes(title, slug, "myfluneo", eps)

        elif source in ("catalog", "anime-sama"):
            from anisama.scraper.base import find_active_domain
            from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
            from anisama.resolver import resolve_url
            domain = find_active_domain()
            if domain:
                url = link or "https://{d}/catalogue/{s}/".format(d=domain, s=slug)
                seasons = get_anime_seasons(url)
                all_eps = []
                abs_offset = 0
                from concurrent.futures import ThreadPoolExecutor, as_completed
                for season in seasons:
                    eps = get_episodes(season["url"])
                    for e in eps:
                        all_eps.append({
                            "number": abs_offset + e["number"],
                            "season": season.get("name", ""),
                            "url": e.get("url", ""),
                            "mirrors": e.get("mirrors", {}),
                        })
                    abs_offset += len(eps)

                def resolve_one(ep):
                    mirrors = ep.get("mirrors", {})
                    if mirrors:
                        for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
                            u = mirrors[k]
                            try:
                                r = resolve_url(u)
                                if r and r.get("url") and r.get("type") != "raw":
                                    ep["resolved"] = r["url"]
                                    ep["resolved_type"] = r.get("type", "")
                                    return
                            except Exception:
                                pass
                    ep["resolved"] = ""
                    ep["resolved_type"] = ""

                with ThreadPoolExecutor(max_workers=5) as pool:
                    futures = {pool.submit(resolve_one, ep): ep for ep in all_eps[:10]}
                    for f in as_completed(futures):
                        pass

                save_episodes(title, slug, "anime-sama", all_eps)

        elif source == "voiranime":
            pass
