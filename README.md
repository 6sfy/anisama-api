> [!IMPORTANT]
> ## anisama API — Centralized anime streaming backend
>
> **Scrapes 6 sources, returns clean JSON. Powers the anisama CLI.**

## About

REST API server that scrapes Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, and AnimoFlix. Returns search results, episode lists, and resolved video URLs as JSON. Used by the [anisama CLI](https://github.com/6sfy/anisama).

## Quick Start

```sh-session
git clone https://github.com/6sfy/anisama-api.git
cd anisama-api
pip install -r requirements.txt
python run.py
```

Server starts on `http://0.0.0.0:20100`. Set `PORT` and `HOST` env vars to customize.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/search?q=QUERY` | Fuzzy search across all sources |
| GET | `/api/v2/catalog` | Full catalog with filters, pagination |
| GET | `/api/v2/episodes?source=SOURCE&slug=SLUG` | Episode list for an anime |
| GET | `/api/v2/resolve?url=URL&source=SOURCE` | Resolve a single video URL |
| GET | `/api/v2/resolve-episode?source=SOURCE&slug=SLUG&num=NUM` | Resolve one episode |
| GET | `/api/v2/sources` | Available sources with counts |
| GET | `/api/v2/stats` | Catalog statistics |
| GET | `/api/v2/info?title=TITLE` | AniList metadata |
| GET | `/player?url=URL&title=TITLE` | Video player page |

## Sources

| Source | Method |
|--------|--------|
| Anime-Sama | HTML |
| Voiranime | HTML |
| MyFluneo | Playwright |
| AnimesUltra | Sitemap + HTML |
| French-Anime | HTML |
| AnimoFlix | HTML + Playwright |

## Deployment

### Pterodactyl / Docker

Set `PY_FILE=run.py` and `REQUIREMENTS_FILE=requirements.txt`. The server needs Playwright + Chromium for MyFluneo resolution.

### Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `PORT` | `20100` | Server port |
| `HOST` | `0.0.0.0` | Bind address |

## Structure

```
api/
├── run.py                  # Entry point
├── requirements.txt
└── src/
    ├── config.py
    ├── core/
    │   ├── cache.py        # Catalog merge, settings
    │   ├── scraper.py      # All 6 source scrapers
    │   └── resolver.py     # Video URL extraction
    └── api/
        ├── server.py       # HTTP server
        ├── routes/         # API route handlers
        ├── db/             # SQLite storage + background indexer
        └── utils/          # HTTP/text helpers
```
