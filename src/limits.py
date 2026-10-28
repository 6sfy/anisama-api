"""Shared per-IP rate limiting and proxy-aware client address."""

import os
import threading
import time
from collections import deque


def env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


RATE_LIMIT_WINDOW = env_int("ANISAMA_RATE_LIMIT_WINDOW", 60)


class RateLimiter:
    """Per-IP sliding-window rate limiter (thread-safe, in-memory).

    Each IP keeps an independent budget per request class, so cheap
    requests never eat into an expensive quota.
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
        if len(self._hits) < 4096:
            return
        stale = [ip for ip, buckets in self._hits.items()
                 if all(not b or now - b[-1] > self.window for b in buckets.values())]
        for ip in stale:
            self._hits.pop(ip, None)


def client_ip(handler):
    """Real client address, optionally behind Cloudflare."""
    if (os.environ.get("ANISAMA_TRUST_PROXY") or "0").strip() == "1":
        cf = handler.headers.get("CF-Connecting-IP")
        if cf:
            return cf.strip()
        xff = handler.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return handler.client_address[0]
