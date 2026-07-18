import json
import re
import shutil
import subprocess
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import REQUEST_TIMEOUT, RESOLVER_HEADERS

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT)
    return _client


def _extract_video_url(text, base_url=""):
    patterns = [
        # JS/JSON common patterns
        (r'(?:var|let|const)\s+(?:video[_-]?url|source[_-]?url|file|src|url|video)\s*=\s*["\']([^"\']+)["\']', None),
        (r'(?:video[_-]?url|file|src|url)\s*:\s*["\'](https?://[^"\']+)["\']', None),
        (r'"(?:file|src|url|video|source)"\s*:\s*"([^"]+)"', None),
        (r"'(?:file|src|url|video|source)'\s*:\s*'([^']+)'", None),
        (r'sources\s*:\s*\[\s*\{[^}]*(?:file|src)\s*:\s*["\']([^"\']+)["\']', None),
        # HTML5 video/source tags
        (r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', None),
        # Direct file URLs
        (r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', "m3u8"),
        (r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', "mp4"),
        (r'["\'](https?://[^"\']+\.webm[^"\']*)["\']', "webm"),
        (r'["\'](https?://[^"\']+/hls/[^"\']*)["\']', "m3u8"),
        (r'["\'](https?://[^"\']+/playlist[^"\']*)["\']', "m3u8"),
        # Generic fallback for any http(s) URL that looks like video
        (r'["\'](https?://[^"\']+\.(?:m3u8|mp4|webm|mkv|mov)[^"\']*)["\']', None),
    ]

    found = []
    for pat, forced_type in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            u = m.group(1)
            if not u or u in found:
                continue
            found.append(u)
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/") and base_url:
                u = urljoin(base_url, u)
            elif not u.startswith("http"):
                continue

            path = urlparse(u).path.split("?")[0].lower()
            ext = path.split(".")[-1] if "." in path else ""

            if forced_type:
                return {"url": u, "type": forced_type}
            if ext in ("m3u8",):
                return {"url": u, "type": "m3u8"}
            if ext in ("mp4", "webm", "mkv", "mov"):
                return {"url": u, "type": ext if ext != "mov" else "mp4"}
            if "/hls" in u.lower() or "/playlist" in u.lower() or ".m3u8" in u.lower():
                return {"url": u, "type": "m3u8"}
            if any(x in u.lower() for x in ["/video/", "/videos/", "cdn", "stream", "media"]):
                return {"url": u, "type": "mp4"}
    return None


def _resolve_embed_page(url, depth=0):
    if depth > 2:
        return None
    c = _get_client()
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": base + "/"}, follow_redirects=True)
        if r.status_code != 200:
            return None

        direct = _extract_video_url(r.text, base)
        if direct:
            return direct

        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        for src in iframes:
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(base, src)
            elif not src.startswith("http"):
                continue
            resolved = _resolve_embed_page(src, depth + 1)
            if resolved:
                return resolved
    except Exception:
        pass
    return None

def _to_base_n(num, base):
    if num == 0:
        return '0'
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    res = ""
    while num > 0:
        res = chars[num % base] + res
        num //= base
    return res

def _decode_pack(p, a, c, k_str):
    k_list = k_str.split("|")
    for i in range(c - 1, -1, -1):
        if i < len(k_list) and k_list[i]:
            alias = _to_base_n(i, a)
            p = re.sub(r"\b" + re.escape(alias) + r"\b", k_list[i], p)
    return p

def resolve_vidmoly(url):
    url_net = url.replace("vidmoly.to", "vidmoly.net")
    c = _get_client()
    try:
        r = c.get(
            url_net,
            headers={**RESOLVER_HEADERS, "Referer": url_net},
        )
        redirect = re.search(r"window\.location\.replace\('([^']+)'\)", r.text)
        if redirect:
            r = c.get(
                redirect.group(1),
                headers={**RESOLVER_HEADERS, "Referer": url_net},
            )
        match = re.search(
            r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text
        )
        if match:
            return {"url": match.group(1), "type": "m3u8"}
    except Exception:
        pass
    return None

def resolve_smoothpre(url):
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    c = _get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": f"{base_url}/"})
        eval_match = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)\)\)",
            r.text,
            re.DOTALL,
        )
        if eval_match:
            decoded = _decode_pack(
                eval_match.group(1),
                int(eval_match.group(2)),
                int(eval_match.group(3)),
                eval_match.group(4),
            )
            for key in ["hls4", "hls3", "hls2", "hls"]:
                m = re.search(rf'"{key}"\s*:\s*"(.*?)"', decoded)
                if m:
                    target_url = m.group(1).replace("\\", "")
                    if target_url.startswith("/"):
                        target_url = base_url + target_url
                    return {"url": target_url, "type": "m3u8"}
    except Exception:
        pass
    return None

def resolve_sendvid(url):
    c = _get_client()
    try:
        r = c.get(
            url,
            headers={**RESOLVER_HEADERS, "Referer": "https://sendvid.com/"},
        )
        match = re.search(r'<source\s+src="([^"]+\.mp4[^"]*)"', r.text)
        if not match:
            match = re.search(r'property="og:video"\s+content="([^"]+)"', r.text)
        if not match:
            match = re.search(
                r'property="og:video:url"\s+content="([^"]+)"', r.text
            )
        if match:
            video_url = match.group(1)
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            return {"url": video_url, "type": "mp4"}
    except Exception:
        pass
    return None

def resolve_oneupload(url):
    c = _get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": url})
        match = re.search(
            r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text
        )
        if match:
            return {"url": match.group(1), "type": "m3u8"}
        match = re.search(r'<source\s+src="([^"]+)"', r.text)
        if match:
            return {"url": match.group(1), "type": "mp4"}
    except Exception:
        pass
    return None

def resolve_sibnet(url):
    c = _get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": url})
        direct = _extract_video_url(r.text, url)
        if direct and direct.get("type") != "raw":
            return direct

        iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        if iframe:
            iframe_url = iframe.group(1)
            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            elif iframe_url.startswith("/"):
                iframe_url = urljoin(url, iframe_url)
            inner = c.get(
                iframe_url,
                headers={**RESOLVER_HEADERS, "Referer": url},
            )
            direct = _extract_video_url(inner.text, iframe_url)
            if direct and direct.get("type") != "raw":
                return direct
    except Exception:
        pass
    return None


def resolve_minochinos(url):
    return _resolve_embed_page(url)


def resolve_embed4me(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    c = _get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": base + "/"}, follow_redirects=True)
        if r.status_code == 200:
            frag = parsed.fragment
            if frag and (frag.startswith("http") or "://" in frag):
                decoded = frag
                if decoded.startswith("//"):
                    decoded = "https:" + decoded
                ext = urlparse(decoded).path.split("?")[0].split(".")[-1].lower()
                t = "m3u8" if ext == "m3u8" else "mp4"
                return {"url": decoded, "type": t}
            direct = _extract_video_url(r.text, base)
            if direct:
                return direct
    except Exception:
        pass
    return _resolve_embed_page(url)


def resolve_with_ytdlp(url):
    yt = shutil.which("yt-dlp")
    if not yt:
        return None
    try:
        result = subprocess.run(
            [yt, "--no-playlist", "--get-url", "--format", "best", url],
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            video_url = result.stdout.strip().splitlines()[0]
            ext = urlparse(video_url).path.split("?")[0].split(".")[-1].lower()
            t = "m3u8" if ext == "m3u8" else "mp4"
            return {"url": video_url, "type": t}
    except Exception:
        pass

    try:
        result = subprocess.run(
            [yt, "--no-playlist", "--dump-json", "--format", "best", url],
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().splitlines()[0])
            video_url = data.get("url") or data.get("manifest_url")
            if not video_url and data.get("formats"):
                video_url = data["formats"][-1].get("url")
            if video_url:
                ext = urlparse(video_url).path.split("?")[0].split(".")[-1].lower()
                t = "m3u8" if ext == "m3u8" else "mp4"
                return {"url": video_url, "type": t}
    except Exception:
        pass
    return None


def resolve_generic(url):
    ytdlp_result = resolve_with_ytdlp(url)
    if ytdlp_result:
        return ytdlp_result
    return _resolve_embed_page(url)


def resolve_voiranime_episode(episode_url, lang):
    c = _get_client()
    try:
        r = c.get(episode_url, headers={**VOIRANIME_HEADERS, "Referer": episode_url})
        if r.status_code != 200:
            return None
        m = re.search(r"const\s+videoUrls\s*=\s*({.*?});", r.text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get(lang)
                if url:
                    return {"url": url, "type": "mp4"}
            except Exception:
                pass
        soup = BeautifulSoup(r.text, "html.parser")
        iframe = soup.find("iframe", id="videoPlayer")
        if iframe:
            src = iframe.get("src")
            if src:
                return {"url": src, "type": "raw"}
    except Exception:
        pass
    return None


RESOLVER_MAP: dict[str, callable] = {
    "vidmoly.to": resolve_vidmoly,
    "vidmoly.net": resolve_vidmoly,
    "smoothpre.com": resolve_smoothpre,
    "vidhide.com": resolve_smoothpre,
    "streamwish.com": resolve_smoothpre,
    "sendvid.com": resolve_sendvid,
    "oneupload.to": resolve_oneupload,
    "video.sibnet.ru": resolve_sibnet,
    "minochinos.com": resolve_minochinos,
    "embed4me.com": resolve_embed4me,
    "lpayer.embed4me.com": resolve_embed4me,
}

def resolve_url(url):
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    resolver = RESOLVER_MAP.get(domain)
    if resolver:
        result = resolver(url)
        if result:
            return result
    generic = resolve_generic(url)
    if generic:
        return generic
    return {"url": url, "type": "raw"}
