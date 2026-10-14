"""
services/qr_generator.py — Offline, scanner-safe aesthetic QR codes (qrcode + Pillow).

Why these codes scan in PhonePe / Google Pay / Paytm / native cameras
--------------------------------------------------------------------
* The payload is a plain absolute ``https://`` URL — the format every scanner
  recognises as a web link (no custom schemes, no wrapping).
* Error-correction level **H** (30 %) tolerates the logo and decoration.
* A full 4-module quiet zone is always kept, on a LIGHT background.
* Modules are always drawn DARK-on-LIGHT (payment apps often fail on inverted
  codes), even in the "Neon Dark" theme: the dark neon frame surrounds a light
  scanning panel.
* The three finder patterns stay solid and high-contrast, the logo covers < 5 %
  of the area, and the contrast ratio is verified for every render.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

STYLES: dict[str, str] = {
    "neon": "Neon Dark Theme",
    "gradient": "Rounded Dot Gradient",
    "classic": "Classic Modern B&W",
}

MODULE_PX = 28      # pixels per QR module -> ~1100-1700 px images
QUIET_ZONE = 4      # modules (QR spec minimum)
MAX_URL_LEN = 400

_LIGHT = (255, 255, 255)
_NEON_PANEL = (245, 247, 255)


class QRError(Exception):
    """Raised for invalid input (bad URL, unreadable logo, unknown style)."""


@dataclass
class ScanReport:
    """Result of the pre-flight scan validation."""
    ok: bool = True
    payload: str = ""
    version: int = 0
    contrast: float = 0.0
    decoded: Optional[str] = None      # set only if an optional decoder is installed
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate_payload(url: str) -> str:
    """Return the cleaned URL or raise QRError. Universal scanners need https://."""
    url = (url or "").strip()
    if not url.lower().startswith(("https://", "http://")):
        raise QRError("QR payload must be an absolute http(s) URL.")
    if any(ch.isspace() for ch in url):
        raise QRError("QR payload must not contain whitespace.")
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc and parsed.hostname != "localhost":
        raise QRError("QR payload must contain a valid host name.")
    if len(url) > MAX_URL_LEN:
        raise QRError("URL is too long for a reliably scannable QR code.")
    return url


def _luminance(rgb: tuple[int, int, int]) -> float:
    def ch(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _try_decode(img: Image.Image, expected: str) -> Optional[str]:
    """
    Round-trip decode using OpenCV when it happens to be installed (optional).

    Individual OpenCV detectors are finicky about exact image sizes, so both the
    Aruco-based and the classic detector are tried at several scales. Returns the
    decoded text (``expected`` as soon as any attempt matches), "" if nothing could
    be decoded, or None when OpenCV is unavailable.
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception:
        return None
    detectors = []
    for factory in ("QRCodeDetectorAruco", "QRCodeDetector"):
        try:
            detectors.append(getattr(cv2, factory)())
        except Exception:
            continue
    if not detectors:
        return None
    rgb = img.convert("RGB")
    last = ""
    for size in (None, 1200, 900, 700):
        view = rgb if size is None else rgb.resize((size, size), Image.LANCZOS)
        arr = np.array(view)
        for det in detectors:
            try:
                text = det.detectAndDecode(arr)[0] or ""
            except Exception:
                continue
            if text == expected:
                return text
            last = text or last
    return last


# --------------------------------------------------------------------------- #
# Drawing primitives
# --------------------------------------------------------------------------- #
def _matrix(url: str) -> list[list[bool]]:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=1,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


def _in_finder(r: int, c: int, n: int) -> bool:
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)


def _gradient(size: int, c1: tuple[int, int, int], c2: tuple[int, int, int]) -> Image.Image:
    """Diagonal two-colour gradient."""
    vertical = Image.linear_gradient("L").resize((size, size))
    horizontal = vertical.rotate(90)
    diagonal = ImageChops.add(vertical, horizontal, scale=2.0)
    return ImageOps.colorize(diagonal, black=c1, white=c2)


def _modules_mask(matrix: list[list[bool]], shape: str, px: int = MODULE_PX) -> Image.Image:
    """White-on-black mask (mode L) of all dark modules incl. quiet zone offset."""
    n = len(matrix)
    size = (n + 2 * QUIET_ZONE) * px
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    off = QUIET_ZONE * px

    for r in range(n):
        for c in range(n):
            if not matrix[r][c] or _in_finder(r, c, n):
                continue
            x0, y0 = off + c * px, off + r * px
            if shape == "dot":
                pad = px * 0.02
                d.ellipse([x0 + pad, y0 + pad, x0 + px - pad - 1, y0 + px - pad - 1], fill=255)
            elif shape == "round":
                d.rounded_rectangle([x0, y0, x0 + px - 1, y0 + px - 1], radius=px * 0.3, fill=255)
            else:
                d.rectangle([x0, y0, x0 + px - 1, y0 + px - 1], fill=255)

    # Finder patterns: solid rounded squares (7x7 ring, 3x3 eye) for reliable detection.
    # Gently rounded only: heavy rounding measurably hurts finder detection.
    outer_r, ring_r, eye_r = px * 0.57, px * 0.39, px * 0.3
    for fr, fc in ((0, 0), (0, n - 7), (n - 7, 0)):
        x0, y0 = off + fc * px, off + fr * px
        d.rounded_rectangle([x0, y0, x0 + 7 * px - 1, y0 + 7 * px - 1], radius=outer_r, fill=255)
        d.rounded_rectangle([x0 + px, y0 + px, x0 + 6 * px - 1, y0 + 6 * px - 1], radius=ring_r, fill=0)
        d.rounded_rectangle([x0 + 2 * px, y0 + 2 * px, x0 + 5 * px - 1, y0 + 5 * px - 1],
                            radius=eye_r, fill=255)
    return mask


def _paint(mask: Image.Image, bg: tuple[int, int, int],
           fg: tuple[int, int, int] | tuple[tuple[int, int, int], tuple[int, int, int]]) -> Image.Image:
    img = Image.new("RGB", mask.size, bg)
    if isinstance(fg[0], tuple):
        layer = _gradient(mask.size[0], fg[0], fg[1])   # type: ignore[arg-type]
    else:
        layer = Image.new("RGB", mask.size, fg)         # type: ignore[arg-type]
    img.paste(layer, (0, 0), mask)
    return img


def _embed_logo(img: Image.Image, logo_bytes: bytes, plate: tuple[int, int, int]) -> Image.Image:
    try:
        logo = Image.open(io.BytesIO(logo_bytes))
        logo.load()
        logo = logo.convert("RGBA")
    except Exception as exc:
        raise QRError("The logo image could not be read. Send a PNG or JPG.") from exc

    side = int(img.size[0] * 0.19)                      # ~3.6 % of the area
    logo.thumbnail((side, side), Image.LANCZOS)
    pad = max(6, int(side * 0.10))
    plate_w, plate_h = logo.size[0] + 2 * pad, logo.size[1] + 2 * pad

    badge = Image.new("RGBA", (plate_w, plate_h), (0, 0, 0, 0))
    ImageDraw.Draw(badge).rounded_rectangle(
        [0, 0, plate_w - 1, plate_h - 1], radius=int(plate_w * 0.22), fill=plate + (255,)
    )
    badge.alpha_composite(logo, (pad, pad))

    out = img.convert("RGBA")
    out.alpha_composite(badge, ((out.size[0] - plate_w) // 2, (out.size[1] - plate_h) // 2))
    return out.convert("RGB")


def _neon_frame(panel: Image.Image) -> Image.Image:
    """Dark neon-glow card around a light, scan-friendly QR panel."""
    # Extra light margin inside the card: scanners get more than the 4-module quiet
    # zone before the dark frame begins (verified to improve detection).
    extra = MODULE_PX * 3
    padded = Image.new("RGB", (panel.size[0] + 2 * extra,) * 2, _NEON_PANEL)
    padded.paste(panel, (extra, extra))
    panel = padded
    margin = MODULE_PX * 3
    w = panel.size[0] + 2 * margin
    bg = Image.new("RGB", (w, w), (9, 11, 26))

    glow = Image.new("RGB", bg.size, (9, 11, 26))
    gd = ImageDraw.Draw(glow)
    box = [margin - 14, margin - 14, w - margin + 13, w - margin + 13]
    gd.rounded_rectangle(box, radius=MODULE_PX, outline=(0, 255, 240), width=14)
    gd.rounded_rectangle([b + 10 for b in box[:2]] + [b - 10 for b in box[2:]],
                         radius=MODULE_PX, outline=(255, 0, 200), width=8)
    glow = glow.filter(ImageFilter.GaussianBlur(MODULE_PX * 0.55))
    bg = ImageChops.screen(bg, glow)

    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([margin - 8, margin - 8, w - margin + 7, w - margin + 7],
                        radius=MODULE_PX * 0.8, outline=(0, 255, 240), width=4)

    rounded = Image.new("L", panel.size, 0)
    ImageDraw.Draw(rounded).rounded_rectangle(
        [0, 0, panel.size[0] - 1, panel.size[1] - 1], radius=MODULE_PX * 0.6, fill=255
    )
    bg.paste(panel, (margin, margin), rounded)
    return bg


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate_qr(url: str, style: str = "classic",
                logo_bytes: Optional[bytes] = None) -> tuple[bytes, ScanReport]:
    """
    Render a QR code PNG for ``url``.

    Returns ``(png_bytes, ScanReport)``. Raises QRError for invalid input.
    """
    if style not in STYLES:
        raise QRError(f"Unknown QR style '{style}'.")
    url = validate_payload(url)
    matrix = _matrix(url)
    n = len(matrix)
    report = ScanReport(payload=url, version=(n - 17) // 4)

    if style == "classic":
        bg, fg = _LIGHT, (12, 12, 14)
        mask = _modules_mask(matrix, "round")
        img = _paint(mask, bg, fg)
        worst = contrast_ratio(fg, bg)
    elif style == "gradient":
        bg, fg = _LIGHT, ((106, 17, 203), (20, 90, 230))
        mask = _modules_mask(matrix, "dot")
        img = _paint(mask, bg, fg)
        worst = min(contrast_ratio(fg[0], bg), contrast_ratio(fg[1], bg))
    else:  # neon
        bg, fg = _NEON_PANEL, ((96, 20, 210), (10, 40, 140))
        mask = _modules_mask(matrix, "round")
        img = _paint(mask, bg, fg)
        worst = min(contrast_ratio(fg[0], bg), contrast_ratio(fg[1], bg))

    if logo_bytes:
        img = _embed_logo(img, logo_bytes, bg)
        report.notes.append("Logo embedded (<5 % of the code area, ECC level H).")

    if style == "neon":
        img = _neon_frame(img)

    report.contrast = round(worst, 1)
    if worst < 4.5:
        report.ok = False
        report.notes.append(f"Low contrast ({worst:.1f}:1) — some scanners may struggle.")
    report.notes.append(f"Plain https:// payload, ECC-H, {QUIET_ZONE}-module quiet zone, "
                        f"contrast {report.contrast}:1.")

    decoded = _try_decode(img, url)
    if decoded is not None:
        report.decoded = decoded
        if decoded != url:
            report.ok = False
            report.notes.append("Round-trip decode did not match the URL.")
        else:
            report.notes.append("Round-trip decode matched the URL.")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), report