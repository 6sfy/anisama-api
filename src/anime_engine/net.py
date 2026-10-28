"""HTTP commun — session requests avec retries, backoff et proxy optionnel."""
import os, time, random
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

TIMEOUT = int(os.environ.get("ENGINE_TIMEOUT", "25"))
PROXY = os.environ.get("ENGINE_PROXY", "").strip()   # ex: http://host:port
RETRIES = int(os.environ.get("ENGINE_RETRIES", "3"))


def session(headers=None, use_proxy=None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    if headers:
        s.headers.update(headers)
    px = PROXY if use_proxy is None else use_proxy
    if px:
        s.proxies.update({"http": px, "https": px})
    return s


def request(sess, method, url, **kw):
    """Requête avec retry sur 429/5xx et erreurs réseau."""
    kw.setdefault("timeout", TIMEOUT)
    last = None
    for attempt in range(RETRIES):
        try:
            r = sess.request(method, url, **kw)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 2)) + random.random())
                continue
            if r.status_code >= 500:
                time.sleep(1.5 * (attempt + 1))
                last = r
                continue
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.2 * (attempt + 1))
    if isinstance(last, requests.Response):
        return last
    if last:
        raise last
    raise RuntimeError("request failed without response")
