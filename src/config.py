import os
import json
from pathlib import Path

KNOWN_DOMAINS = [
    "anime-sama.to",
    "anime-sama.si",
    "anime-sama.org",
    "anime-sama.tv",
    "anime-sama.eu",
    "anime-sama.pw",
    "anime-sama.fr",
]

PROVIDER_URL = "https://anime-sama.pw/"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

VOIRANIME_DOMAIN = "voiranime.rip"

VOIRANIME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.6",
    "Referer": "https://voiranime.rip/catalogue/",
}

RESOLVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

PACKAGE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CATALOG_FILE = DATA_DIR / "catalog.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
HISTORY_FILE = DATA_DIR / "history.json"
DOMAIN_CACHE_FILE = DATA_DIR / "active_domain.txt"

CACHE_MAX_AGE_HOURS = 24
REQUEST_TIMEOUT = 15
CATALOG_REMOTE_URL = "https://raw.githubusercontent.com/6sfy/anisama/main/data/catalog.json"

PLAYER_PATHS = {
    "Windows": {
        "mpv": [
            "mpv.exe",
            r"C:\Program Files\mpv\mpv.exe",
            r"C:\Program Files (x86)\mpv\mpv.exe",
            r"C:\Program Files\MPV Player\mpv.exe",
            r"C:\Program Files (x86)\MPV Player\mpv.exe",
        ],
        "vlc": [
            "vlc.exe",
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ],
        "iina": [],
        "moonplayer": [
            "moonplayer.exe",
            r"C:\Program Files\MoonPlayer\moonplayer.exe",
        ],
        "implay": [
            "ImPlay.exe",
            r"C:\Program Files\ImPlay\ImPlay.exe",
        ],
    },
    "Linux": {
        "mpv": ["mpv"],
        "vlc": ["vlc"],
        "iina": [],
        "moonplayer": ["moonplayer"],
        "implay": ["ImPlay"],
    },
    "Darwin": {
        "mpv": ["mpv"],
        "vlc": ["vlc"],
        "iina": ["iina"],
        "moonplayer": ["moonplayer"],
        "implay": ["ImPlay"],
    },
}
