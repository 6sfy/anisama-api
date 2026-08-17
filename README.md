> [!IMPORTANT]
> ## anisama API — Centralized anime streaming backend
>
> **Scrapes 6 sources, returns clean JSON. Powers the anisama CLI.**

## About

REST API server that scrapes Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, and AnimoFlix. Returns search results, episode lists, and resolved video URLs as JSON. Used by the [anisama CLI](https://github.com/6sfy/anisama).

Built on the [anisama](https://github.com/6sfy/anisama) core library (v2.0.0+) for all scraping, search, and resolution logic.

## Quick Start

```sh-session
git clone https://github.com/6sfy/anisama-api.git
cd anisama-api
pip install .
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

The server needs Playwright + Chromium for MyFluneo resolution. Install with:
```
pip install anisama-api[playwright]
playwright install chromium
```

### Environment Variables

Copy `.env.example` to `.env` (loaded automatically via python-dotenv) or set the variables directly in your environment:

| Var | Default | Description |
|-----|---------|-------------|
| `PORT` | `20100` | Server port |
| `HOST` | `0.0.0.0` | Bind address |
| `ANISAMA_DATA_DIR` | (auto) | Data directory for catalog/cache |
| `ANISAMA_PLAYWRIGHT_EXECUTABLE_PATH` | (auto) | Path to Playwright Chromium executable |

## Structure

```
anisama-api/
├── pyproject.toml              # Package config (anisama>=2.0.0 dependency)
├── run.py                      # Entry point
└── src/
    ├── __init__.py
    ├── server.py               # HTTP server
    ├── helpers.py              # API-specific HTTP/text helpers
    ├── routes/                 # API route handlers
    │   ├── search.py
    │   ├── episodes.py
    │   ├── resolve.py
    │   ├── sources.py
    │   ├── catalog.py
    │   ├── stats.py
    │   ├── info.py
    │   ├── player.py
    │   └── legacy.py
    ├── db/                     # SQLite storage + background indexer
    │   ├── connection.py
    │   ├── models.py
    │   └── indexer.py
    └── web/                    # Static web UI
        ├── index.html
        ├── script.js
        └── styles.css
```
