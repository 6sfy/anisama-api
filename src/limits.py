"""Shared per-IP rate limiting and proxy-aware client address."""

import ipaddress
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

_CLOUDFLARE_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22",
    "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18",
    "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22",
    "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13",
    "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
    "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
    "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
    "2c0f:f248::/32",
))


def _parse_networks(raw):
    networks = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            continue
    return tuple(networks)


_CUSTOM_PROXIES = _parse_networks(os.environ.get("ANISAMA_TRUSTED_PROXIES", ""))


def _valid_ip(value):
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


def _is_trusted_proxy(peer):
    try:
        addr = ipaddress.ip_address(peer)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback:
        return True
    return any(addr in net for net in _CLOUDFLARE_NETWORKS + _CUSTOM_PROXIES)


def trust_proxy_mode():
    return (os.environ.get("ANISAMA_TRUST_PROXY") or "auto").strip().lower()


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

    def peek(self, ip, tier="light"):
        """Current budget without consuming a request (cache-hit responses)."""
        now = time.time()
        limit = self.limits.get(tier, self.limits.get("light", 0))
        if limit <= 0:
            return 0, 0, 0
        with self._lock:
            buckets = self._hits.get(ip) or {}
            bucket = buckets.get(tier) or deque()
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            remaining = max(0, limit - len(bucket))
            reset = int(self.window - (now - bucket[0])) + 1 if bucket else self.window
            return limit, remaining, max(1, reset)

    def _maybe_prune(self, now):
        if len(self._hits) < 4096:
            return
        stale = [ip for ip, buckets in self._hits.items()
                 if all(not b or now - b[-1] > self.window for b in buckets.values())]
        for ip in stale:
            self._hits.pop(ip, None)


def client_ip(handler):
    """Real client address.

    `auto` (default) trusts CF-Connecting-IP / X-Forwarded-For only when the
    direct peer is loopback, private, Cloudflare, or listed in
    ANISAMA_TRUSTED_PROXIES. `1` always trusts the headers; `0` never does.
    """
    peer = handler.client_address[0]
    mode = trust_proxy_mode()
    if mode not in ("1", "true", "yes", "auto"):
        return peer
    if mode == "auto" and not _is_trusted_proxy(peer):
        return peer

    headers = getattr(handler, "headers", None)
    if not headers:
        return peer

    cf = (headers.get("CF-Connecting-IP") or "").split(",")[0].strip()
    if _valid_ip(cf):
        return cf
    xff = (headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if _valid_ip(xff):
        return xff
    return peer
