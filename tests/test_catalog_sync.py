"""Tests for the Anime-Sama sitemap catalogue sync and genre stats."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import catalog_sync
from src.routes.stats import _entry_genres

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://anime-sama.to/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/naruto/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/naruto/saison1/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/one-piece/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/foo-scan/</loc></url>
  <url><loc>https://anime-sama.to/catalogue/bar/?page=2</loc></url>
</urlset>
"""


class _Response:
    status_code = 200
    text = SITEMAP


def test_sitemap_entries_only_include_catalogue_root_pages(monkeypatch):
    monkeypatch.setattr(
        catalog_sync.requests,
        "get",
        lambda *args, **kwargs: _Response(),
    )

    entries = catalog_sync.fetch_anime_sama_entries("anime-sama.to")

    assert [entry["slug"] for entry in entries] == ["naruto", "one-piece"]
    assert entries[0] == {
        "title": "Naruto",
        "link": "https://anime-sama.to/catalogue/naruto/",
        "slug": "naruto",
        "source": "anime-sama",
    }


def test_sync_appends_only_unknown_links(monkeypatch):
    existing = [{
        "title": "Naruto",
        "link": "https://anime-sama.to/catalogue/naruto/",
        "source": "anime-sama",
    }]
    saved = []
    monkeypatch.setattr(catalog_sync, "fetch_anime_sama_entries", lambda domain: [
        {
            "title": "Naruto",
            "link": "https://anime-sama.to/catalogue/naruto/",
            "slug": "naruto",
            "source": "anime-sama",
        },
        {
            "title": "One Piece",
            "link": "https://anime-sama.to/catalogue/one-piece/",
            "slug": "one-piece",
            "source": "anime-sama",
        },
    ])
    monkeypatch.setattr(catalog_sync.cache_mod, "load_catalog", lambda: existing)
    monkeypatch.setattr(catalog_sync.cache_mod, "save_catalog", lambda catalog: saved.append(catalog))

    added = catalog_sync.sync_anime_sama_catalog("anime-sama.to")

    assert added == 1
    assert saved[0][-1]["slug"] == "one-piece"
    assert len(saved[0]) == 2


def test_stats_accepts_singular_genre_and_ignores_format_buckets():
    assert _entry_genres({"genre": "Animes"}) == []
    assert _entry_genres({"genre": "Action"}) == ["Action"]
    assert _entry_genres({"genre": "Action, Comédie"}) == ["Action", "Comédie"]
    assert _entry_genres({"genres": ["Fantastique"]}) == ["Fantastique"]
    assert _entry_genres({"genre": "Top Animes", "genres": None}) == []
