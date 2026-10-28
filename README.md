> [!IMPORTANT]
> ## anisama API — Centralized anime streaming backend
>
> **Scrapes 7 sources, returns clean JSON. Powers the anisama CLI.**
> **Fast engine included: Anime-Sama + FRAnime served via direct API extraction (10-50x faster).**

## About

REST API server that scrapes Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix, and Franime. Returns search results, episode lists, and resolved video URLs as JSON. Used by the [anisama CLI](https://github.com/6sfy/anisama).

Built on the [anisama](https://github.com/6sfy/anisama) core library (v2.0.0+) for all scraping, search, and resolution logic.

### Fast engine (`anime_engine`)

The `src/anime_engine/` package is a standalone, dependency-light engine (requests only) that extracts the **real APIs** of Anime-Sama and FRAnime:

| Source | Extraction | Result |
|--------|-----------|--------|
| Anime-Sama | `POST /template-php/defaut/fetch.php` + `episodes.js` parsing | **direct embed URLs** (vidmoly, embed4me, sibnet, sendvid, uqload…), no resolver pass |
| FRAnime | `api.franime.fr` JSON with **0-based indexes** | fixes the 404 « Aucun lecteur disponible » caused by 1-based numbers |

The routes `/api/v2/search`, `/api/v2/episodes` and `/api/v2/resolve-episode` use the fast engine for `anime-sama` and `franime` sources first, and automatically fall back to the historical pipeline if it fails. New engine-native endpoints are also exposed (see table below).

- In-memory TTL caches: search 5 min, episodes 30 min, resolve 10 min, seasons/hosts 1 h.
- Thread-safe: engine network calls are serialized, cached responses are lock-free.
- `ANISAMA_FAST_ENGINE=0` disables the fast path entirely (historical pipeline only).
- `ENGINE_PROXY=http://…` routes engine traffic through a proxy — useful if your server IP is blocked by Cloudflare (Anime-Sama).

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
| GET | `/api/v2/search?q=QUERY` | Fuzzy search across all sources (fast engine for anime-sama + franime) |
| GET | `/api/v2/catalog` | Full catalog with filters, pagination |
| GET | `/api/v2/episodes?source=SOURCE&slug=SLUG` | Episode list for an anime (`&season=N` for franime) |
| GET | `/api/v2/resolve?url=URL&source=SOURCE` | Resolve a single video URL |
| GET | `/api/v2/resolve-episode?source=SOURCE&slug=SLUG&num=NUM` | Resolve one episode (`&season=N&lang=vo|vf` for franime) |
| GET | `/api/v2/seasons?source=SOURCE&slug=SLUG` | **New** — season list via fast engine |
| GET | `/api/v2/hosts?slug=SLUG&season_url=URL` | **New** — distinct video hosts of an anime-sama season |
| GET | `/api/v2/engine` | **New** — fast engine status (enabled, cache, proxy) |
| GET | `/health` | Liveness probe (no cache, no network) |
| GET | `/api/v2/sources` | Available sources with counts |
| GET | `/api/v2/stats` | Catalog statistics |
| GET | `/api/v2/info?title=TITLE` | AniList metadata |
| GET | `/player?url=URL&title=TITLE` | Video player page |

Responses from the fast path carry an extra `"engine": true` flag. Response shapes for existing endpoints are unchanged — the CLI needs no update.

## Sources

| Source | Method |
|--------|--------|
| Anime-Sama | HTML |
| Voiranime | HTML |
| MyFluneo | Playwright |
| AnimesUltra | Sitemap + HTML |
| French-Anime | HTML |
| AnimoFlix | HTML + Playwright |
| Franime | API |

## Deployment

### Pterodactyl / Docker

The fast engine (Anime-Sama + FRAnime) only needs `requests`. Playwright is
**optional** and only used by the historical MyFluneo / AnimoFlix fallback —
its wheel plus Chromium need roughly 500 MB, which fills small containers.
Keep it disabled unless your host has the disk space:

```
pip install anisama-api[playwright]
playwright install chromium
```

The server binds to `SERVER_PORT` automatically (the allocation port injected
by the panel), and that value wins over `PORT`. Point your Cloudflare Origin
Rule / reverse proxy / tunnel at that same port. A Cloudflare **502** means the
origin is unreachable on the expected port, not a frontend error — check the
allocation and the proxy target first.

On constrained hosts, install without cache to avoid a full disk:

```
python -m pip install --no-cache-dir -r requirements.txt
```

If a previous install filled the disk (e.g. Playwright was pulled in), reclaim
space before restarting the server:

```
pip cache purge
rm -rf .local/lib/python*/site-packages/playwright*
```

### Environment Variables

Copy `.env.example` to `.env` (loaded automatically via python-dotenv) or set the variables directly in your environment:

| Var | Default | Description |
|-----|---------|-------------|
| `SERVER_PORT` | (panel) | Pterodactyl allocation port — wins over `PORT` when set |
| `PORT` | `20100` | Server port (fallback when `SERVER_PORT` is unset) |
| `HOST` | `0.0.0.0` | Bind address — keep `0.0.0.0` in Docker (the public IP is not local) |
| `ANISAMA_DATA_DIR` | (auto) | Data directory for catalog/cache |
| `ANISAMA_PLAYWRIGHT_EXECUTABLE_PATH` | (auto) | Path to Playwright Chromium executable |
| `ANISAMA_FAST_ENGINE` | `1` | `0` disables the fast engine (historical pipeline only) |
| `ENGINE_PROXY` | (empty) | Outbound proxy for the fast engine (Cloudflare bypass) |
| `ENGINE_TIMEOUT` | `25` | Fast engine network timeout (seconds) |
| `ANISAMA_RATE_LIMIT_GLOBAL` | `60` | Light requests per IP per window (`0` disables) |
| `ANISAMA_RATE_LIMIT_HEAVY` | `20` | Search/resolve/episodes requests per IP per window |
| `ANISAMA_RATE_LIMIT_RESOLVE` | `5` | `resolve-episode` requests per IP per window |
| `ANISAMA_RATE_LIMIT_WINDOW` | `60` | Rate-limit window in seconds |
| `ANISAMA_API_TOKEN` | (empty) | When set, expensive endpoints require `Authorization: Bearer <token>` |
| `ANISAMA_TRUST_PROXY` | `0` | `1` behind Cloudflare: rate-limit on `CF-Connecting-IP` (not the CF edge IP) |
| `ANISAMA_CORS_ORIGINS` | prod + localhost | Comma-separated allowed browser origins, or `*` |
| `ANISAMA_ENABLE_VOIRANIME` | `1` | `0` hides the Voiranime source from `/api/v2/sources` |

### Security

- Per-IP rate limiting with independent light/heavy/resolve budgets, `429` + `Retry-After`/`RateLimit-*` headers.
- SSRF guard on every client-supplied URL; static file serving is confined to `src/web`.
- Opaque `500` responses (`{"error": "internal_error", "request_id": "..."}`); exception details stay in server logs.
- `Strict-Transport-Security`, CSP on HTML pages, `nosniff`, `X-Frame-Options`, `Referrer-Policy`.
- CORS restricted to an origin whitelist; `Authorization`/`X-API-Key` allowed for authenticated deployments.
- Sources that cannot serve requests (Playwright missing for MyFluneo/AnimoFlix) are not advertised by `/api/v2/sources`.

## Structure

```
anisama-api/
├── pyproject.toml              # Package config (anisama>=2.0.0 dependency)
├── run.py                      # Entry point
└── src/
    ├── __init__.py
    ├── server.py               # HTTP server
    ├── helpers.py              # API-specific HTTP/text helpers
    ├── fast_engine.py          # Fast engine adapter (TTL caches, thread-safe, format conversion)
    ├── anime_engine/           # Standalone extraction engine (requests only)
    │   ├── net.py              #   session + retries + optional proxy
    │   ├── anime_sama.py       #   anime-sama.to scraper (direct embed links)
    │   ├── franime.py          #   api.franime.fr client (0-based indexes)
    │   ├── engine.py           #   unified facade
    │   └── README.md           #   engine internals & pitfalls
    ├── routes/                 # API route handlers
    │   ├── search.py
    │   ├── episodes.py
    │   ├── resolve.py
    │   ├── sources.py
    │   ├── catalog.py
    │   ├── stats.py
    │   ├── info.py
    │   ├── player.py
    │   ├── engine.py           # /api/v2/seasons, /api/v2/hosts, /api/v2/engine
    │   └── legacy.py
    ├── db/                     # SQLite storage + background indexer
    │   ├── connection.py
    │   ├── models.py
    │   └── indexer.py
    └── web/                    # Static web UI
        ├── index.html
        ├── script.js
        ├── a11y.js             # A11y + navigation layer (loaded after script.js)
        └── styles.css
```
