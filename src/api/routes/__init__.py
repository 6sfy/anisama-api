from src.api.routes import search, episodes, resolve, sources, info, player, legacy, catalog, stats

ROUTES = {
    "/api/v2/search": search.handle,
    "/api/v2/episodes": episodes.handle,
    "/api/v2/resolve": resolve.handle_resolve,
    "/api/v2/resolve-episode": resolve.handle_resolve_episode,
    "/api/v2/sources": sources.handle,
    "/api/v2/catalog": catalog.handle,
    "/api/v2/stats": stats.handle,
    "/api/v2/info": info.handle,
    "/player": player.handle,
}

LEGACY_PREFIXES = ("/api/search", "/api/episodes", "/api/resolve", "/api/sources")
