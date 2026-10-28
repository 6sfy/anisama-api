"""Import Anime-Sama catalogue entries from its public sitemap."""

import logging
import re

import requests

from anisama import cache as cache_mod

logger = logging.getLogger("anisama-api")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
_LOC_RE = re.compile(
    r"<loc>\s*https://[^/]+/catalogue/([^/<?#\s]+)/?\s*</loc>",
    re.IGNORECASE,
)
_SKIP_SLUG_TOKENS = (
    "scan",
    "manhwa",
    "manhua",
    "webtoon",
    "manga",
    "novel",
)


def _title_from_slug(slug):
    return re.sub(r"[-_]+", " ", slug).strip().title()


def _is_catalogue_slug(slug):
    slug = slug.strip().strip("/")
    if not slug or "?" in slug or "#" in slug:
        return False
    low = slug.lower()
    return not any(token in low for token in _SKIP_SLUG_TOKENS)


def fetch_anime_sama_entries(domain=None, timeout=30):
    base = "https://{0}".format(domain) if domain else "https://anime-sama.to"
    try:
        response = requests.get(
            base + "/sitemap.xml",
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
    except requests.RequestException as exc:
        logger.warning("Anime-Sama sitemap unavailable: %s", exc)
        return []
    if response.status_code != 200:
        logger.warning("Anime-Sama sitemap returned HTTP %s", response.status_code)
        return []

    slugs = sorted({
        match.group(1).strip("/")
        for match in _LOC_RE.finditer(response.text)
        if _is_catalogue_slug(match.group(1))
    })
    return [
        {
            "title": _title_from_slug(slug),
            "link": "{0}/catalogue/{1}/".format(base, slug),
            "slug": slug,
            "source": "anime-sama",
        }
        for slug in slugs
    ]


def sync_anime_sama_catalog(domain=None):
    entries = fetch_anime_sama_entries(domain)
    if not entries:
        return 0

    catalog = cache_mod.load_catalog()
    known_links = {
        (entry.get("link") or "").rstrip("/").lower()
        for entry in catalog
    }
    new_entries = [
        entry for entry in entries
        if entry["link"].rstrip("/").lower() not in known_links
    ]
    if not new_entries:
        return 0

    cache_mod.save_catalog(catalog + new_entries)
    logger.info("Anime-Sama sitemap: %d new catalogue entries", len(new_entries))
    return len(new_entries)
