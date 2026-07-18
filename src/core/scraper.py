import base64
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import DEFAULT_HEADERS, KNOWN_DOMAINS, PROVIDER_URL, REQUEST_TIMEOUT, VOIRANIME_HEADERS
from src.core.cache import load_domain_cache, save_domain_cache

_client = None
_active_domain = None

def get_client():
    global _client
    if _client is None:
        _client = httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT)
    return _client

def find_active_domain():
    global _active_domain
    if _active_domain is not None:
        return _active_domain

    cached = load_domain_cache()
    if cached:
        try:
            r = get_client().get(f"https://{cached}", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if final:
                    _active_domain = final
                    if final != cached:
                        save_domain_cache(final)
                    return final
        except Exception:
            pass

    try:
        r = get_client().get(PROVIDER_URL, headers=DEFAULT_HEADERS)
        m = re.search(r'href="(.+?)">Acceder a Anime-Sama', r.text, re.IGNORECASE)
        if m:
            r2 = get_client().get(m.group(1), headers=DEFAULT_HEADERS)
            u = str(r2.url)
            dm = re.search(r"https?://([^/]+)", u)
            if dm:
                _active_domain = dm.group(1)
                save_domain_cache(_active_domain)
                return _active_domain
    except Exception:
        pass

    for d in KNOWN_DOMAINS:
        try:
            r = get_client().get(f"https://{d}/", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if not final:
                    final = d
                _active_domain = final
                save_domain_cache(final)
                return final
        except Exception:
            continue

    return None

_SKIP_SEASON_KEYWORDS = {"scan", "manhwa", "webtoon", "manhua", "manga", "novel", "light novel", "ln"}


def _is_anime_season(name):
    lower = name.lower()
    return not any(kw in lower for kw in _SKIP_SEASON_KEYWORDS)


def get_anime_seasons(url):
    client = get_client()
    r = client.get(url, headers=DEFAULT_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seasons = []
    pat = re.compile(r'panneau(?:Anime|Film|Scan|Visual)\s*\(\s*(["\'])(.*?)\1\s*,\s*(["\'])(.*?)\3\s*\)')
    for s in soup.find_all("script"):
        if s.text:
            txt = re.sub(r'/\*.*?\*/', "", s.text, flags=re.DOTALL)
            for _, name, _, path in pat.findall(txt):
                if name.lower() != "nom" and path.lower() != "url":
                    if not _is_anime_season(name):
                        continue
                    full = urljoin(url.rstrip("/") + "/", path).rstrip("/")
                    seasons.append({"name": name, "url": full})
    seen = set()
    uniq = []
    for s in seasons:
        if s["name"] not in seen:
            seen.add(s["name"])
            uniq.append(s)
    return uniq

def get_episodes(url):
    client = get_client()
    if not url.endswith("/"):
        url += "/"
    r = client.get(url, headers=DEFAULT_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", src=lambda s: s and "episodes.js" in s)
    if not script:
        return []
    src = script.get("src", "")
    if src.startswith("/"):
        parsed = urlparse(url)
        js_url = f"{parsed.scheme}://{parsed.netloc}{src}"
    else:
        js_url = urljoin(url, src)
    try:
        js = client.get(js_url, headers=DEFAULT_HEADERS).text
    except Exception:
        return []
    matches = re.findall(r"var\s+(eps\d+)\s*=\s*\[(.*?)\];", js, re.DOTALL)
    if not matches:
        return []
    all_eps = {}
    for name, content in matches:
        urls = re.findall(r"'(https?://[^']+)'", content)
        all_eps[name] = urls
    keys = sorted(all_eps.keys(), key=lambda x: int(x[3:]))
    if not keys:
        return []
    n = len(all_eps[keys[0]])
    eps = []
    for i in range(n):
        mirrors = {}
        for k in keys:
            if i < len(all_eps[k]):
                mirrors[k] = all_eps[k][i]
        eps.append({"number": i + 1, "mirrors": mirrors, "referer": url})
    return eps

def resolve_episode_url(url):
    from src.core.resolver import resolve_url as _resolve
    return _resolve(url)

def search_online(domain, query):
    url = f"https://{domain}/template-php/defaut/fetch.php"
    try:
        r = get_client().post(url, data={"query": query}, headers=DEFAULT_HEADERS)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", class_="asn-search-result"):
        link = a.get("href", "").strip()
        t = a.find("h3", class_="asn-search-result-title")
        title = t.get_text(strip=True) if t else ""
        if not title or not link:
            continue
        results.append({"title": title, "link": link, "score": 100, "source": "online"})
    return results

def voiranime_get_seasons(url):
    r = get_client().get(url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seasons = []
    section = soup.find("section", id="seasons")
    if not section:
        return seasons
    for card in section.find_all("a", class_="season-card"):
        href = card.get("href", "")
        title_el = card.find("h3", class_="season-title")
        meta = card.find("div", class_="season-meta")
        langs = set()
        if meta:
            for badge in meta.find_all("span", class_="lang-badge"):
                langs.add(badge.get_text(strip=True).lower())
        name = title_el.get_text(strip=True) if title_el else ""
        if not name or not href:
            continue
        if not href.startswith("http"):
            href = urljoin(url, href)
        seasons.append({"name": name, "url": href, "langs": langs})
    return seasons

def voiranime_get_episodes(season_url, lang=None):
    r = get_client().get(season_url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    eps = []
    grid = soup.find("div", class_="episodes-grid")
    if not grid:
        return eps
    for card in grid.find_all("a", class_="episode-card"):
        href = card.get("href", "")
        num_el = card.find("div", class_="episode-number")
        num = num_el.get_text(strip=True) if num_el else ""
        m = re.search(r"(\d+)", num)
        ep_num = int(m.group(1)) if m else 0
        langs_raw = card.get("data-langs", "")
        ep_langs = set(langs_raw.split()) if langs_raw else set()

        if lang and lang not in ep_langs:
            continue

        if not href.startswith("http"):
            href = urljoin(season_url, href)

        eps.append({"number": ep_num, "url": href, "langs": ep_langs})
    return eps


# ── MyFluneo (myfluneo.eu) ──
MYFLUNEO_DOMAIN = "myfluneo.eu"
MYFLUNEO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _base_slug(slug):
    s = re.sub(r"-(vf|vostfr|vo)$", "", slug)
    s = re.sub(r"-\d+$", "", s)
    return s


def myfluneo_catalog():
    entries = []
    seen = set()

    for i in range(1, 18):
        url = "https://{d}/sitemap_{i}.xml".format(d=MYFLUNEO_DOMAIN, i=i)
        try:
            r = get_client().get(url, headers=MYFLUNEO_HEADERS)
        except Exception:
            continue
        if r.status_code != 200:
            continue

        for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
            loc = loc.strip()
            if "/anime/" not in loc:
                continue
            slug = loc.rstrip("/").split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)

            base = _base_slug(slug)
            title = base.replace("-", " ").title()
            title = re.sub(r"\s+Saison\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+Movie\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+Film\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = title.strip()

            entries.append({
                "title": title,
                "link": loc,
                "slug": slug,
                "source": "myfluneo",
            })

    return entries


def myfluneo_search(query, entries=None):
    if entries is None:
        entries = myfluneo_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "myfluneo"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def myfluneo_resolve(episode_url):
    try:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=True,
            executable_path="/opt/hermes/.playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell",
        )
        page = browser.new_page()

        video_url = None
        def on_response(response):
            nonlocal video_url
            if "/embed-player?" in response.url:
                try:
                    data = response.json()
                    if data.get("redirectUrl"):
                        video_url = data["redirectUrl"]
                except:
                    pass

        page.on("response", on_response)
        page.goto(episode_url, wait_until="networkidle", timeout=15000)

        if not video_url:
            iframes = page.locator("iframe").all()
            for f in iframes:
                src = f.get_attribute("src")
                if src and "/embed-player" in src:
                    v_match = re.search(r"v=([A-Za-z0-9+/=]+)", src)
                    if v_match:
                        try:
                            decoded = base64.b64decode(v_match.group(1)).decode()
                            video_url = decoded
                        except:
                            pass

        browser.close()
        pw.stop()

        if video_url:
            return {"url": video_url, "type": "mp4", "referer": episode_url}

        return {"url": episode_url, "type": "raw", "referer": episode_url}

    except Exception:
        return {"url": episode_url, "type": "raw", "referer": episode_url}


def myfluneo_episodes(anime_url):
    import hashlib
    from pathlib import Path
    cache_key = hashlib.md5(anime_url.encode()).hexdigest()
    cache_file = Path(__file__).parent.parent / "api_cache" / "mf_eps_{k}.json".format(k=cache_key)
    if cache_file.exists():
        import time
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400:
            import json
            return json.loads(cache_file.read_text())

    try:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=True,
            executable_path="/opt/hermes/.playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell",
        )
        page = browser.new_page()

        episodes = {}
        page.goto(anime_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        links = page.locator('a[href*="/episode-"]').all()
        for link in links:
            href = link.get_attribute("href") or ""
            m = re.search(r"/saison-(\d+)/episode-(\d+)", href)
            if m:
                ep_num = int(m.group(2))
                if ep_num not in episodes:
                    ep_url = href.split("?_rsc=")[0].split("?")[0]
                    if not ep_url.startswith("http"):
                        ep_url = "https://myfluneo.eu" + ep_url
                    episodes[ep_num] = {"url": ep_url, "season": m.group(1)}

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        more = page.locator('a[href*="/episode-"]').all()
        for link in more:
            href = link.get_attribute("href") or ""
            m = re.search(r"/saison-(\d+)/episode-(\d+)", href)
            if m:
                ep_num = int(m.group(2))
                if ep_num not in episodes:
                    ep_url = href.split("?_rsc=")[0].split("?")[0]
                    if not ep_url.startswith("http"):
                        ep_url = "https://myfluneo.eu" + ep_url
                    episodes[ep_num] = {"url": ep_url, "season": m.group(1)}

        browser.close()
        pw.stop()

        eps = [{"number": n, "url": e["url"], "lang": "vostfr", "season": e.get("season", "1")}
               for n, e in sorted(episodes.items())]

        if eps:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            import json
            cache_file.write_text(json.dumps(eps, ensure_ascii=False))

        return eps

    except Exception:
        return []


_ALT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


_AN_DOMAIN = "ww.animesultra.org"


def animesultra_catalog():
    entries = []
    seen = set()
    try:
        r = get_client().get("https://{d}/sitemap.xml".format(d=_AN_DOMAIN), headers=_ALT_HEADERS)
        if r.status_code != 200:
            return entries
    except Exception:
        return entries

    for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
        loc = loc.strip()
        if "/anime-vostfr/" not in loc and "/anime-vf/" not in loc:
            continue
        slug = loc.rstrip("/").split("/")[-1].replace(".html", "")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        title = slug.replace("-", " ").title()
        title = re.sub(r"\s+Au\s*$", "", title, flags=re.IGNORECASE).strip()
        entries.append({"title": title, "link": loc, "slug": slug, "source": "animesultra"})
    return entries


def animesultra_search(query, entries=None):
    if entries is None:
        entries = animesultra_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "animesultra"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def animesultra_episodes(url):
    eps = []
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return eps
    except Exception:
        return eps
    soup = BeautifulSoup(r.text, "lxml")
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        m = re.search(r"episode[-/]?(\d+)", href)
        if m:
            ep_num = int(m.group(1))
            if not href.startswith("http"):
                href = "https://{d}{h}".format(d=_AN_DOMAIN, h=href)
            eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    for ep_div in soup.find_all("div", class_=re.compile(r"epi|episode|eps", re.I)):
        a = ep_div.find("a", href=True)
        if a:
            href = a.get("href", "")
            m = re.search(r"(\d+)", a.get_text(strip=True) or "")
            if m:
                ep_num = int(m.group(1))
                if not href.startswith("http"):
                    href = "https://{d}{h}".format(d=_AN_DOMAIN, h=href)
                if not any(e["number"] == ep_num for e in eps):
                    eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    return sorted(eps, key=lambda x: x["number"])


def animesultra_resolve(url):
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for div in soup.find_all(attrs={"data-embed": True}):
        embed = div.get("data-embed", "")
        if embed:
            if embed.startswith("//"):
                embed = "https:" + embed
            return {"url": embed, "type": "embed", "referer": url}
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            known = ["vidmoly", "sendvid", "sibnet", "streamtape", "vidstream"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}
    return {"url": url, "type": "raw", "referer": url}


_FA_DOMAIN = "french-anime.com"


def frenchanime_catalog():
    entries = []
    seen = set()
    try:
        r = get_client().get("https://{d}/".format(d=_FA_DOMAIN), headers=_ALT_HEADERS)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=re.compile(r"/animes-(?:vostfr|vf)/")):
                href = a.get("href", "")
                title = a.get_text(strip=True) or a.get("title", "")
                if not title or not href:
                    continue
                if not href.startswith("http"):
                    href = "https://{d}{h}".format(d=_FA_DOMAIN, h=href)
                slug = href.rstrip("/").split("/")[-1].replace(".html", "")
                if slug and slug not in seen:
                    seen.add(slug)
                    entries.append({"title": title, "link": href, "slug": slug, "source": "frenchanime"})
    except Exception:
        pass
    return entries


def frenchanime_search(query, entries=None):
    if entries is None:
        entries = frenchanime_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "frenchanime"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def frenchanime_episodes(url):
    eps = []
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return eps
    except Exception:
        return eps
    soup = BeautifulSoup(r.text, "lxml")
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        m = re.search(r"episode[-/]?(\d+)", href)
        if m:
            ep_num = int(m.group(1))
            if not href.startswith("http"):
                href = "https://{d}{h}".format(d=_FA_DOMAIN, h=href)
            eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    return sorted(eps, key=lambda x: x["number"])


def frenchanime_resolve(url):
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            known = ["luluvdo", "vidmoly", "vidara", "sendvid", "sibnet"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}
    return {"url": url, "type": "raw", "referer": url}


_AF_DOMAIN = "animoflix.to"


def animoflix_catalog():
    entries = []
    seen = set()
    try:
        r = get_client().get("https://{d}/catalogue/".format(d=_AF_DOMAIN), headers=_ALT_HEADERS)
        if r.status_code != 200:
            return entries
    except Exception:
        return entries
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.find_all("a", href=re.compile(r"/anime/")):
        href = a.get("href", "")
        title = a.get_text(strip=True) or a.get("title", "")
        if not title or not href:
            continue
        if not href.startswith("http"):
            href = "https://{d}{h}".format(d=_AF_DOMAIN, h=href)
        slug = href.rstrip("/").split("/")[-2] if href.endswith("/") else href.rstrip("/").split("/")[-1]
        if slug and slug not in seen:
            seen.add(slug)
            entries.append({"title": title, "link": href, "slug": slug, "source": "animoflix"})
    return entries


def animoflix_search(query, entries=None):
    if entries is None:
        entries = animoflix_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "animoflix"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def animoflix_episodes(url):
    eps = []
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                m = re.search(r"episode[-/]?(\d+)", href)
                if m:
                    ep_num = int(m.group(1))
                    if not href.startswith("http"):
                        href = "https://{d}{h}".format(d=_AF_DOMAIN, h=href)
                    if not any(e["number"] == ep_num for e in eps):
                        eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    except Exception:
        pass

    if eps:
        return sorted(eps, key=lambda x: x["number"])

    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        for link in page.locator('a[href*="episode-"]').all():
            href = link.get_attribute("href") or ""
            m = re.search(r"episode[-/]?(\d+)", href)
            if m:
                ep_num = int(m.group(1))
                if not href.startswith("http"):
                    href = "https://{d}{h}".format(d=_AF_DOMAIN, h=href)
                if not any(e["number"] == ep_num for e in eps):
                    eps.append({"number": ep_num, "url": href, "lang": "vostfr"})

        browser.close()
        pw.stop()
    except Exception:
        pass

    return sorted(eps, key=lambda x: x["number"])


def animoflix_resolve(url):
    try:
        r = get_client().get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            known = ["sendvid", "sibnet", "vidmoly"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}

    try:
        from playwright.sync_api import sync_playwright
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        for btn in page.locator("[data-server], .server-item, .btn-server").all():
            try:
                btn.click()
                page.wait_for_timeout(1500)
            except Exception:
                continue
            for iframe in page.locator("iframe").all():
                src = iframe.get_attribute("src") or ""
                if src and "javascript" not in src:
                    if src.startswith("//"):
                        src = "https:" + src
                    browser.close()
                    pw.stop()
                    return {"url": src, "type": "embed", "referer": url}

        browser.close()
        pw.stop()
    except Exception:
        pass

    return {"url": url, "type": "raw", "referer": url}
