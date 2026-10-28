# Changelog

All notable changes to `anisama-api` are documented in this file.

## [2.0.1] - 2026-10-28

### Added

- Voiranime source fixed and enabled by default: new `/<slug>/` URLs, saga pages, VF/VOSTFR and direct HLS resolution.
- Anime-Sama episode resolution selects the best resolvable mirror (`ansembed`, `embed4me`, ...) and returns a direct `m3u8` stream.
- Custom HTML 404 page for mistyped URLs; API routes still return JSON errors.
- Security hardening: per-tier per-IP rate limiting, opaque errors with `request_id`, HSTS/CSP, CORS whitelist, optional Bearer token, `robots.txt`, static asset caching.
- `/api/v2/seasons` supports Voiranime; `/api/v2/sources` only advertises sources that can serve requests.

### Fixed

- Scan and one-shot seasons no longer pollute Anime-Sama episode numbering.
- Resolving one episode now caches the full episode list without erasing previously resolved URLs.
- FRAnime is now listed in `/api/v2/sources` and documented on the sources page (7 sources total).
- Light mode is now warm cream with readable code blocks, table headers, inline code and terminal.
- Code block text no longer disappears in light mode.
- HLS playback: IP/ASN-bound server tokens fall back to the ansembed iframe; the resolver extracts media from embed pages and ignores stale non-media cache entries.

### Changed

- Voiranime is advertised by default (`ANISAMA_ENABLE_VOIRANIME=1`, set `0` to hide it).
- Web assets are served without comments.

## [2.0.0] - 2026-10-23

- Fast engine for Anime-Sama and FRAnime (direct API extraction, no BeautifulSoup/Playwright).
- New `/api/v2/seasons`, `/api/v2/hosts`, `/api/v2/engine` and `/health` endpoints.
- Parallel API/local resolution with cache write-back and `fresh=1` re-resolution.
- Search scores clamped to 0-100.
- Pterodactyl `SERVER_PORT` handling and bind fallback.
- Optional Playwright; lighter installs on small containers.
- Web documentation navigation and accessibility layer fixes.

## [1.1.0] - 2026-07-18

- MyFluneo, AnimesUltra, French-Anime and AnimoFlix sources.
- Central API v2 with server-side scraping.
- `/api/v2/catalog`, `/api/v2/stats` and `/api/v2/resolve-episode`.
- Realistic search scores (rapidfuzz).
- Absolute episode numbering across seasons.

## [1.0.3]

- Original release with Anime-Sama and Voiranime, local catalog, client-side scraping and basic search.
