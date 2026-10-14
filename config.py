"""
config.py — Central configuration for Webify Bot.

Every value is read from environment variables so the same code runs locally
and on Render without edits.

Required:
    BOT_TOKEN   Telegram bot token from @BotFather
    MONGO_URI   MongoDB connection string (e.g. MongoDB Atlas)

Optional:
    RENDER_EXTERNAL_URL  Public base URL (Render sets this automatically)
    PORT                 HTTP port (Render sets this automatically, default 8080)
    ADMIN_IDS            Comma separated Telegram user IDs allowed to use /admin
    DB_NAME              MongoDB database name (default: webify_bot)
    DATA_DIR             Where sites/logos are stored (default: ./data)
                         On Render, point this at a persistent disk mount.
    USE_WEBHOOK          "true"/"false". Default: webhook when RENDER_EXTERNAL_URL
                         is https, otherwise long polling.
    WEBHOOK_SECRET       Secret used in the webhook path/header (derived from the
                         bot token when not given).
    WILDCARD_DOMAIN      Optional base domain for VIP subdomains, e.g. "sites.example.com"
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


# --------------------------------------------------------------------------- #
# Core credentials
# --------------------------------------------------------------------------- #
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI: str = os.getenv("MONGO_URI", "").strip()
DB_NAME: str = os.getenv("DB_NAME", "webify_bot").strip() or "webify_bot"

# --------------------------------------------------------------------------- #
# Networking
# --------------------------------------------------------------------------- #
RENDER_EXTERNAL_URL: str = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
PORT: int = _env_int("PORT", 8080)
HOST: str = "0.0.0.0"

BASE_URL: str = RENDER_EXTERNAL_URL or f"http://localhost:{PORT}"
MAIN_HOST: str = (urlparse(BASE_URL).hostname or "localhost").lower()

USE_WEBHOOK: bool = BASE_URL.startswith("https://") and _env_bool("USE_WEBHOOK", True)
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "").strip() or hashlib.sha256(
    ("webify:" + BOT_TOKEN).encode()
).hexdigest()[:40]
WEBHOOK_PATH: str = f"/webhook/{WEBHOOK_SECRET}"
WEBHOOK_URL: str = f"{BASE_URL}{WEBHOOK_PATH}"

WILDCARD_DOMAIN: str = os.getenv("WILDCARD_DOMAIN", "").strip().lower().lstrip(".")

# Render's free tier sleeps after ~15 min without inbound traffic. When enabled the
# app pings its own public /health URL periodically so it stays awake 24/7.
KEEP_ALIVE: bool = _env_bool("KEEP_ALIVE", BASE_URL.startswith("https://"))
KEEP_ALIVE_INTERVAL: int = max(60, _env_int("KEEP_ALIVE_INTERVAL", 600))

# --------------------------------------------------------------------------- #
# Admins
# --------------------------------------------------------------------------- #
ADMIN_IDS: set[int] = {
    int(x) for x in re.split(r"[,\s]+", os.getenv("ADMIN_IDS", "")) if x.strip().isdigit()
}

# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
HOSTED_DIR: Path = DATA_DIR / "hosted_sites"   # /hosted_sites/{site_id}/...
LOGO_DIR: Path = DATA_DIR / "logos"            # per-user QR logos
TMP_DIR: Path = DATA_DIR / "tmp"               # staging area for uploads

# --------------------------------------------------------------------------- #
# Tier limits
# --------------------------------------------------------------------------- #
MB = 1024 * 1024
TIERS: dict[str, dict] = {
    "Free": {
        "max_sites": 3,
        "max_upload": 10 * MB,      # per uploaded file (Telegram bots can fetch <= 20 MB)
        "max_site_size": 25 * MB,   # total size of one site on disk
        "max_files": 300,
        "custom_domain": False,
    },
    "VIP": {
        "max_sites": 25,
        "max_upload": 20 * MB,
        "max_site_size": 100 * MB,
        "max_files": 2000,
        "custom_domain": True,
    },
}

# --------------------------------------------------------------------------- #
# File security
# --------------------------------------------------------------------------- #
# Only these (static) extensions may be stored/served.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".html", ".htm", ".css", ".js", ".mjs", ".json", ".txt", ".md", ".xml", ".csv",
    ".webmanifest", ".map", ".ico",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".mp4", ".webm", ".ogg", ".wav", ".pdf",
})

# Explicitly dangerous extensions: refused with a specific message.
BLOCKED_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".pyc", ".pyw", ".exe", ".sh", ".bash", ".zsh", ".php", ".phtml", ".php3",
    ".php4", ".php5", ".bat", ".cmd", ".com", ".msi", ".dll", ".so", ".jar", ".war",
    ".pl", ".rb", ".cgi", ".asp", ".aspx", ".jsp", ".ps1", ".vbs", ".vbe", ".scr",
    ".bin", ".apk", ".app", ".dmg", ".htaccess", ".lnk", ".reg", ".wasm",
})

ARCHIVE_EXTENSION = ".zip"

# Reserved slugs that would clash with server routes.
RESERVED_SLUGS: frozenset[str] = frozenset({
    "admin", "api", "health", "webhook", "static", "s", "root", "www", "bot",
    "webify", "login", "dashboard", "assets", "favicon", "robots",
})


def validate() -> None:
    """Fail fast with a clear message when mandatory settings are missing."""
    missing = [n for n, v in (("BOT_TOKEN", BOT_TOKEN), ("MONGO_URI", MONGO_URI)) if not v]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )


def ensure_dirs() -> None:
    for d in (DATA_DIR, HOSTED_DIR, LOGO_DIR, TMP_DIR):
        d.mkdir(parents=True, exist_ok=True)


def site_url(slug: str) -> str:
    """Public URL of a site by slug."""
    return f"{BASE_URL}/s/{slug}/"