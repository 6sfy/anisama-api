from src.routes import search, episodes, resolve, sources, info, player, legacy, catalog, stats, engine

ROUTES = {
    "/api/v2/search": search.handle,
    "/api/v2/episodes": episodes.handle,
    "/api/v2/resolve": resolve.handle_resolve,
    "/api/v2/resolve-episode": resolve.handle_resolve_episode,
    "/api/v2/sources": sources.handle,
    "/api/v2/catalog": catalog.handle,
    "/api/v2/stats": stats.handle,
    "/api/v2/info": info.handle,
    "/api/v2/seasons": engine.handle_seasons,
    "/api/v2/hosts": engine.handle_hosts,
    "/api/v2/engine": engine.handle_status,
    "/health": engine.handle_health,
    "/api/v2/health": engine.handle_health,
    "/player": player.handle,
}

POST_ROUTES = {
    "/api/v2/resolve-episode": resolve.handle_resolve_episode_submit,
}

LEGACY_PREFIXES = ("/api/search", "/api/episodes", "/api/resolve", "/api/sources")
