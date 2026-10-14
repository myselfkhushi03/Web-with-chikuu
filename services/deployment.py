"""
services/deployment.py — Upload sanitising, ZIP/HTML deployment and static hosting.

Security model
--------------
* Only extensions in ``config.ALLOWED_EXTENSIONS`` are ever written to disk.
* Dangerous types (.py .exe .sh .php .bat ...) are refused/stripped.
* ZIP extraction is streamed with byte/file limits (zip-bomb safe), rejects
  absolute paths, ``..`` traversal and drive letters, and never creates symlinks.
* Everything is staged in a temp directory first, then committed to
  ``HOSTED_DIR/<site_id>`` so a bad upload can never half-destroy a live site.
* The HTTP router re-checks every resolved path stays inside the site folder
  and re-checks the extension (defence in depth).
"""
from __future__ import annotations

import asyncio
import html
import logging
import re
import secrets
import shutil
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

import config
from database import db

log = logging.getLogger(__name__)

SITE_ID_RE = re.compile(r"^[a-f0-9]{10}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")
DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"
)


class DeploymentError(Exception):
    """Raised with a user-presentable message when a deployment is refused."""


@dataclass
class DeployResult:
    files: int = 0
    bytes: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    generated_index: bool = False
    total_size: int = 0   # size of the whole site after the deployment


# --------------------------------------------------------------------------- #
# Naming helpers
# --------------------------------------------------------------------------- #
def new_site_id() -> str:
    return secrets.token_hex(5)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)[:32].strip("-")
    return slug


def validate_slug(slug: str) -> Optional[str]:
    """Return an error message, or None when the slug is acceptable."""
    if not (3 <= len(slug) <= 32):
        return "Slug must be 3–32 characters long."
    if not SLUG_RE.match(slug):
        return "Use only lowercase letters, numbers and hyphens (no hyphen at the ends)."
    if "--" in slug:
        return "Avoid double hyphens."
    if slug in config.RESERVED_SLUGS:
        return "That slug is reserved. Please choose another."
    return None


async def unique_slug(base: str) -> str:
    """Create a free slug derived from ``base`` (falls back to a random one)."""
    base = slugify(base)
    candidates = []
    if base and validate_slug(base) is None:
        candidates.append(base)
        candidates.extend(f"{base[:26]}-{secrets.token_hex(2)}" for _ in range(3))
    candidates.extend(f"site-{secrets.token_hex(3)}" for _ in range(5))
    for cand in candidates:
        if validate_slug(cand) is None and await db.slug_available(cand):
            return cand
    return f"site-{secrets.token_hex(6)}"


def validate_domain(domain: str) -> Optional[str]:
    domain = domain.lower().strip()
    if not DOMAIN_RE.match(domain):
        return "That doesn't look like a valid domain name."
    if domain == config.MAIN_HOST:
        return "You can't use the bot's own domain."
    return None


def sanitize_filename(name: str) -> str:
    """Reduce an arbitrary string to a safe single path component."""
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._\-]+", "_", name).lstrip(".")
    name = name.strip("_") or "file"
    return name[:120]


def check_extension(filename: str) -> Optional[str]:
    """Return None if the file may be hosted, else the reason it is refused."""
    ext = Path(filename).suffix.lower()
    if ext in config.BLOCKED_EXTENSIONS:
        return f"'{ext}' files are blocked for security reasons"
    if ext not in config.ALLOWED_EXTENSIONS:
        return f"'{ext or 'no extension'}' is not an allowed static web asset"
    return None


def site_dir(site_id: str) -> Path:
    if not SITE_ID_RE.match(site_id):
        raise DeploymentError("Invalid site id.")
    return config.HOSTED_DIR / site_id


def dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def count_files(path: Path) -> int:
    return sum(1 for p in path.rglob("*") if p.is_file()) if path.exists() else 0


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #
_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9]*\s*\n(.*?)\n?```\s*$", re.DOTALL)


def normalize_html(code: str) -> str:
    """Strip markdown fences and wrap bare fragments into a full document."""
    code = code.strip()
    m = _FENCE_RE.match(code)
    if m:
        code = m.group(1).strip()
    low = code.lower()
    if "<html" in low or "<!doctype" in low:
        return code
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>My Website</title>\n</head>\n<body>\n" + code + "\n</body>\n</html>\n"
    )


def build_fallback_html(title: str, pages: list[str]) -> str:
    """Modern default index.html used when a ZIP has no index.html."""
    items = "".join(
        f'<a class="card" href="{html.escape(p, quote=True)}">{html.escape(p)}</a>' for p in pages
    ) or '<p class="muted">This site is ready. Upload your pages to get started.</p>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#e9ecff;
background:radial-gradient(1200px 600px at 10% 0%,#3a2a8a 0%,transparent 60%),
radial-gradient(900px 500px at 100% 100%,#0b6b8a 0%,transparent 55%),#0b0f1f}}
main{{width:100%;max-width:560px;padding:40px 32px;border-radius:24px;
background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
backdrop-filter:blur(14px);box-shadow:0 20px 60px rgba(0,0,0,.45)}}
h1{{font-size:1.9rem;margin-bottom:6px}}
.muted{{color:#aab1d6;margin-bottom:22px}}
.grid{{display:grid;gap:10px}}
.card{{display:block;padding:12px 16px;border-radius:12px;text-decoration:none;color:#fff;
background:linear-gradient(90deg,#6a11cb,#2575fc);word-break:break-all;font-size:.95rem}}
.card:hover{{filter:brightness(1.12)}}
footer{{margin-top:26px;font-size:.78rem;color:#7f88b8;text-align:center}}
</style></head><body><main>
<h1>✨ {html.escape(title)}</h1>
<p class="muted">Your site is live. Pages available:</p>
<div class="grid">{items}</div>
<footer>Hosted with Webify Bot</footer>
</main></body></html>
"""


def message_page(title: str, text: str, status: int = 200) -> HTMLResponse:
    body = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#0b0f1f;color:#e9ecff;text-align:center;padding:24px}}
.b{{max-width:480px}}h1{{font-size:3rem;margin-bottom:8px}}p{{color:#aab1d6;line-height:1.5}}</style></head>
<body><div class="b"><h1>{html.escape(title)}</h1><p>{html.escape(text)}</p></div></body></html>"""
    return HTMLResponse(body, status_code=status)


# --------------------------------------------------------------------------- #
# Deployment (blocking functions run in worker threads)
# --------------------------------------------------------------------------- #
def _stage_dir() -> Path:
    stage = config.TMP_DIR / f"stage_{uuid.uuid4().hex}"
    stage.mkdir(parents=True, exist_ok=True)
    return stage


def _extract_zip(zip_path: Path, stage: Path, max_total: int, max_files: int) -> DeployResult:
    result = DeployResult()
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise DeploymentError("That ZIP archive is corrupted or not a valid ZIP.") from exc

    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > max_files * 3:
            raise DeploymentError("The archive contains too many entries.")
        stage_root = stage.resolve()
        for info in infos:
            raw = info.filename.replace("\\", "/")
            parts = [p for p in PurePosixPath(raw).parts if p not in ("", ".")]
            if not parts:
                continue
            if raw.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", parts[0]):
                result.skipped.append((raw, "unsafe path"))
                continue
            if any(p.startswith("__MACOSX") or p.startswith(".") for p in parts):
                result.skipped.append((raw, "hidden/system file"))
                continue
            if info.flag_bits & 0x1:
                raise DeploymentError("Password-protected ZIP files are not supported.")
            # Symlinks are stored with a unix mode in the high bits of external_attr.
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                result.skipped.append((raw, "symlink"))
                continue
            reason = check_extension(parts[-1])
            if reason:
                result.skipped.append((raw, reason))
                continue
            if result.files >= max_files:
                raise DeploymentError(f"Too many files (limit {max_files}).")

            cleaned = [sanitize_filename(p) for p in parts]
            target = stage.joinpath(*cleaned)
            resolved = target.resolve()
            if stage_root not in resolved.parents:
                result.skipped.append((raw, "unsafe path"))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(64 * 1024)
                    if not chunk:
                        break
                    result.bytes += len(chunk)
                    if result.bytes > max_total:
                        raise DeploymentError(
                            f"Extracted content exceeds the {max_total // config.MB} MB site limit."
                        )
                    out.write(chunk)
            result.files += 1
    return result


def _flatten_single_root(stage: Path) -> None:
    """If everything sits in one top-level folder, move it up one level."""
    entries = list(stage.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        tmp = stage / f"__flat_{uuid.uuid4().hex}"
        inner.rename(tmp)
        for item in list(tmp.iterdir()):
            item.rename(stage / item.name)
        tmp.rmdir()


def _commit(stage: Path, target: Path, replace: bool) -> None:
    """Move staged content into the live site folder."""
    if replace and target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    for item in stage.iterdir():
        dest = target / item.name
        if item.is_dir():
            if dest.exists() and not dest.is_dir():
                dest.unlink()
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            if dest.exists() and dest.is_dir():
                shutil.rmtree(dest)
            shutil.copy2(item, dest)


def ensure_index(path: Path, title: str = "My Website") -> bool:
    """Create a default index.html when missing. Returns True if generated."""
    index = path / "index.html"
    if index.exists():
        return False
    pages = sorted(
        str(p.relative_to(path).as_posix())
        for p in path.rglob("*")
        if p.is_file() and p.suffix.lower() in (".html", ".htm")
    )[:50]
    index.write_text(build_fallback_html(title, pages), encoding="utf-8")
    return True


def _finish(stage: Path, target: Path, replace: bool, result: DeployResult,
            max_site_size: int, title: str) -> DeployResult:
    existing = 0 if replace else dir_size(target)
    staged = dir_size(stage)
    if existing + staged > max_site_size:
        raise DeploymentError(
            f"Site would exceed the {max_site_size // config.MB} MB storage limit."
        )
    if not any(stage.rglob("*")) and (replace or not target.exists()):
        raise DeploymentError("No hostable files were found in the upload.")
    _commit(stage, target, replace)
    result.generated_index = ensure_index(target, title)
    result.total_size = dir_size(target)
    return result


def _deploy_archive_sync(zip_path: Path, site_id: str, replace: bool, limits: dict,
                         title: str) -> DeployResult:
    target = site_dir(site_id)
    stage = _stage_dir()
    try:
        result = _extract_zip(zip_path, stage, limits["max_site_size"], limits["max_files"])
        if result.files == 0:
            reasons = ", ".join(sorted({r for _, r in result.skipped})[:3])
            raise DeploymentError(
                "No hostable files were found in the ZIP."
                + (f" Skipped: {reasons}." if reasons else "")
            )
        _flatten_single_root(stage)
        return _finish(stage, target, replace, result, limits["max_site_size"], title)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _deploy_text_sync(site_id: str, code: str, limits: dict, title: str) -> DeployResult:
    data = normalize_html(code).encode("utf-8")
    if len(data) > limits["max_upload"]:
        raise DeploymentError("That code is larger than your plan's upload limit.")
    stage = _stage_dir()
    try:
        (stage / "index.html").write_bytes(data)
        result = DeployResult(files=1, bytes=len(data))
        return _finish(stage, site_dir(site_id), True, result, limits["max_site_size"], title)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _deploy_file_sync(src: Path, site_id: str, filename: str, as_index: bool, replace: bool,
                      limits: dict, title: str) -> DeployResult:
    filename = sanitize_filename(filename)
    reason = check_extension(filename)
    if reason:
        raise DeploymentError(reason.capitalize() + ".")
    size = src.stat().st_size
    if size > limits["max_upload"]:
        raise DeploymentError("File is larger than your plan's upload limit.")
    stage = _stage_dir()
    try:
        if as_index:
            data = normalize_html(src.read_text(encoding="utf-8", errors="replace"))
            (stage / "index.html").write_text(data, encoding="utf-8")
        else:
            shutil.copy2(src, stage / filename)
        result = DeployResult(files=1, bytes=size)
        return _finish(stage, site_dir(site_id), replace, result, limits["max_site_size"], title)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


async def deploy_archive(zip_path: Path, site_id: str, *, replace: bool, limits: dict,
                         title: str = "My Website") -> DeployResult:
    return await asyncio.to_thread(_deploy_archive_sync, zip_path, site_id, replace, limits, title)


async def deploy_text(site_id: str, code: str, *, limits: dict, title: str = "My Website") -> DeployResult:
    return await asyncio.to_thread(_deploy_text_sync, site_id, code, limits, title)


async def deploy_file(src: Path, site_id: str, filename: str, *, as_index: bool, replace: bool,
                      limits: dict, title: str = "My Website") -> DeployResult:
    return await asyncio.to_thread(_deploy_file_sync, src, site_id, filename, as_index, replace,
                                   limits, title)


# --------------------------------------------------------------------------- #
# File manager helpers
# --------------------------------------------------------------------------- #
def list_site_files(site_id: str, limit: int = 500) -> list[tuple[str, int]]:
    root = site_dir(site_id)
    if not root.exists():
        return []
    rows = [
        (p.relative_to(root).as_posix(), p.stat().st_size)
        for p in root.rglob("*") if p.is_file() and not p.is_symlink()
    ]
    rows.sort(key=lambda r: r[0].lower())
    return rows[:limit]


def delete_site_file(site_id: str, rel_path: str) -> bool:
    root = site_dir(site_id).resolve()
    target = (root / rel_path).resolve()
    if root not in target.parents or not target.is_file():
        return False
    target.unlink()
    # Remove now-empty parent folders (never the root itself).
    parent = target.parent
    while parent != root and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    ensure_index(root)
    return True


def remove_site_files(site_id: str) -> None:
    try:
        shutil.rmtree(site_dir(site_id), ignore_errors=True)
    except DeploymentError:
        pass


# --------------------------------------------------------------------------- #
# Static hosting router
# --------------------------------------------------------------------------- #
router = APIRouter()

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "public, max-age=120",
}


async def serve_site_path(request: Request, site: dict, rel_path: str) -> Response:
    """Serve ``rel_path`` of a site (shared by /s/<slug>/ and custom domains)."""
    if site.get("is_locked"):
        return message_page("🔒 Locked", "This site has been locked by an administrator.", 403)

    try:
        root = site_dir(site["site_id"]).resolve()
    except DeploymentError:
        return message_page("404", "Site not found.", 404)
    if not root.is_dir():
        return message_page("404", "This site has no content yet.", 404)

    rel_path = rel_path.lstrip("/")
    candidate = (root / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        return message_page("404", "Page not found.", 404)

    if candidate.is_dir():
        if rel_path and not request.url.path.endswith("/"):
            return RedirectResponse(request.url.path + "/", status_code=308)
        candidate = candidate / "index.html"
    elif not candidate.is_file() and candidate.suffix == "":
        # Friendly URLs: /about -> about.html
        alt = candidate.with_name(candidate.name + ".html")
        if alt.is_file():
            candidate = alt

    if not candidate.is_file() or check_extension(candidate.name) is not None:
        return message_page("404", "Page not found.", 404)

    headers = dict(_SECURITY_HEADERS)
    suffix = candidate.suffix.lower()
    if suffix == ".svg":
        # SVG can embed scripts; serve it as an inert image.
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    if suffix in (".html", ".htm") and request.method == "GET":
        try:
            await db.inc_views(site["site_id"])
        except Exception:  # never fail a page view because analytics failed
            log.exception("view counter failed")
    return FileResponse(candidate, headers=headers)


@router.api_route("/s/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def site_redirect(slug: str) -> RedirectResponse:
    return RedirectResponse(f"/s/{slug}/", status_code=308)


@router.api_route("/s/{slug}/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def site_files(request: Request, slug: str, path: str = "") -> Response:
    site = await db.get_site_by_slug(slug)
    if not site:
        return message_page("404", "No site exists at this address.", 404)
    return await serve_site_path(request, site, path)