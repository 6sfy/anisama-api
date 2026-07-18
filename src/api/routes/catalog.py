from src.api.utils.http import send_json, get_param
from src.core import cache as cache_mod


def handle(handler, params):
    source_filter = get_param(params, "source", "all").lower()
    page = int(get_param(params, "page", "1") or "1")
    limit = int(get_param(params, "limit", "50") or "50")
    sort = get_param(params, "sort", "title").lower()
    q = get_param(params, "q", "").lower()

    if page < 1:
        page = 1
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    cat = cache_mod.load_catalog()
    filtered = []

    for entry in cat:
        raw_source = entry.get("source", "catalog")
        if raw_source == "catalog":
            entry_source = "anime-sama"
        else:
            entry_source = raw_source

        if source_filter != "all" and source_filter != entry_source:
            continue

        if q:
            title = entry.get("title", "").lower()
            slug = entry.get("slug", "").lower()
            alts = [a.lower() for a in entry.get("alt_titles", [])]
            if q not in title and q not in slug and not any(q in a for a in alts):
                continue

        slug = entry.get("slug", "") or entry.get("link", "").rstrip("/").split("/")[-1]
        filtered.append({
            "title": entry.get("title", ""),
            "slug": slug,
            "link": entry.get("link", ""),
            "source": entry_source,
            "alt_source": entry.get("alt_source", []),
            "genres": entry.get("genres", []),
            "year": entry.get("year", ""),
        })

    if sort == "title":
        filtered.sort(key=lambda x: x["title"].lower())
    elif sort == "source":
        filtered.sort(key=lambda x: (x["source"].lower(), x["title"].lower()))
    else:
        filtered.sort(key=lambda x: x["title"].lower())

    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    page_items = filtered[start:end]

    send_json(handler, {
        "source_filter": source_filter,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
        "count": len(page_items),
        "results": page_items,
    })
