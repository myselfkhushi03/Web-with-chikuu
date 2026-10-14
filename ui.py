"""
ui.py — Shared aesthetic text blocks, formatters and inline keyboards.

All user-provided content must pass through ``esc()`` before being placed in
an HTML-formatted Telegram message.
"""
from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config

PAGE_SIZE = 6

# Aesthetic fragments ------------------------------------------------------- #
HEADER = "✨ <b>WΞBIFY DΛSΗBΘΛRD</b> ✨"
LINE = "━━━━━━━━━━━━━━━━━━━━"
BADGE_ACTIVE = "[🟢 ΛᄃƬI√Σ]"
BADGE_LOCKED = "[🔒 LΘᄃKΞD]"
BADGE_PROC = "[⚡ PRΘCΞSSIИG]"
BADGE_OK = "[✅ DΘИΞ]"
BADGE_ERR = "[🔴 ΞRRΘR]"
BADGE_VIP = "[👑 VIP]"


def esc(value: object) -> str:
    return html.escape(str(value), quote=False)


def fmt_bytes(n: int | float) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%d %b %Y, %H:%M UTC") if dt else "—"


def progress_bar(pct: float, width: int = 12) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100))
    return "▓" * filled + "░" * (width - filled)


def tier_of(user_doc: Optional[dict], user_id: Optional[int] = None) -> str:
    """Effective tier: admins always enjoy VIP limits."""
    uid = user_id if user_id is not None else (user_doc or {}).get("telegram_id")
    if uid in config.ADMIN_IDS:
        return "VIP"
    return (user_doc or {}).get("tier", "Free") if (user_doc or {}).get("tier") in config.TIERS else "Free"


def tier_badge(tier: str) -> str:
    return BADGE_VIP if tier == "VIP" else "[🆓 FRΞΞ]"


# --------------------------------------------------------------------------- #
# Texts
# --------------------------------------------------------------------------- #
def welcome_text(first_name: str, tier: str) -> str:
    lim = config.TIERS[tier]
    return (
        f"{HEADER}\n{LINE}\n"
        f"Hey <b>{esc(first_name)}</b>! Turn any HTML, ZIP or pasted code into a "
        f"<b>live website</b> in seconds. 🚀\n\n"
        f"👤 Plan: {tier_badge(tier)}\n"
        f"📦 Sites: up to <b>{lim['max_sites']}</b> · Upload: <b>{fmt_bytes(lim['max_upload'])}</b>\n"
        f"{LINE}\n"
        f"Send me an <code>.html</code> / <code>.zip</code> file or tap a button below."
    )


def help_text() -> str:
    allowed = ", ".join(sorted(e.lstrip(".") for e in config.ALLOWED_EXTENSIONS if e not in (".map",)))
    return (
        f"{HEADER}\n{LINE}\n"
        "<b>📖 Hσω ƭσ υѕє</b>\n"
        "1️⃣ Send an <code>.html</code> file, a <code>.zip</code> of your site, or paste code.\n"
        "2️⃣ Get an instant live link at <code>/s/your-name/</code>.\n"
        "3️⃣ Customise the slug, manage files, make a QR code, track views.\n\n"
        "<b>🛡 Security</b>\n"
        "Only static web assets are accepted. Scripts/executables "
        "(<code>.py .exe .sh .php .bat</code> …) are always refused.\n\n"
        f"<b>✅ Allowed types</b>\n<code>{esc(allowed)}</code>\n\n"
        "<b>⌨️ Commands</b>\n"
        "/start · /new · /mysites · /profile · /help · /cancel"
    )


def site_text(site: dict, tier: str = "Free") -> str:
    locked = bool(site.get("is_locked"))
    badge = BADGE_LOCKED if locked else BADGE_ACTIVE
    url = config.site_url(site["slug"])
    lines = [
        f"{HEADER}\n{LINE}",
        f"{badge} <b>{esc(site['site_name'])}</b>",
        f"🔗 <code>{esc(url)}</code>",
    ]
    if site.get("custom_domain"):
        lines.append(f"🌍 <code>https://{esc(site['custom_domain'])}/</code>")
    lines += [
        f"👁 Views: <b>{site.get('views_count', 0)}</b>",
        f"💾 Size: <b>{fmt_bytes(site.get('size_bytes', 0))}</b>",
        f"🕒 Created: {fmt_dt(site.get('created_at'))}",
    ]
    if locked:
        lines.append("\n⚠️ This site was locked by an administrator.")
    return "\n".join(lines)


def deployed_text(site: dict, files: int, size: int, skipped: list[tuple[str, str]],
                  generated_index: bool, headline: str = "DΞPLΘYΞD") -> str:
    url = config.site_url(site["slug"])
    out = [
        f"{HEADER}\n{LINE}",
        f"{BADGE_OK} <b>{headline}</b> — {BADGE_ACTIVE}",
        f"🌐 <b>{esc(site['site_name'])}</b>",
        f"🔗 {esc(url)}",
        f"📁 Files: <b>{files}</b> · 💾 <b>{fmt_bytes(size)}</b>",
    ]
    if generated_index:
        out.append("🪄 No <code>index.html</code> found — a modern default page was generated.")
    if skipped:
        shown = "\n".join(f"  • <code>{esc(n[:60])}</code> — {esc(r)}" for n, r in skipped[:5])
        more = f"\n  …and {len(skipped) - 5} more" if len(skipped) > 5 else ""
        out.append(f"\n🛡 <b>Refused {len(skipped)} file(s):</b>\n{shown}{more}")
    return "\n".join(out)


def profile_text(user_doc: dict, tier: str, sites: int, views: int) -> str:
    lim = config.TIERS[tier]
    uname = f"@{esc(user_doc['username'])}" if user_doc.get("username") else "—"
    return (
        f"{HEADER}\n{LINE}\n"
        f"👤 <b>Prσϝιƚє</b>\n"
        f"🆔 ID: <code>{user_doc['telegram_id']}</code>\n"
        f"🔖 Username: {uname}\n"
        f"💎 Plan: {tier_badge(tier)}\n"
        f"📅 Joined: {fmt_dt(user_doc.get('joined_at'))}\n"
        f"{LINE}\n"
        f"🌐 Sites: <b>{sites}/{lim['max_sites']}</b>\n"
        f"👁 Total views: <b>{views}</b>\n"
        f"📦 Per-site storage: <b>{fmt_bytes(lim['max_site_size'])}</b>"
    )


# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #
def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚀 New Website", callback_data="new")
    b.button(text="🌐 My Sites", callback_data="ms:0")
    b.button(text="👤 Profile", callback_data="profile")
    b.button(text="📖 Help", callback_data="help")
    if is_admin:
        b.button(text="🛠 Admin Panel", callback_data="adm")
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_kb(target: str = "menu", label: str = "⬅️ Back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=label, callback_data=target)
    return b.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    return back_kb("cancel", "✖️ Cancel")


def new_site_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📄 Upload HTML / ZIP", callback_data="new:upload")
    b.button(text="⌨️ Paste Code", callback_data="new:paste")
    b.button(text="⬅️ Back", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def site_list_kb(sites: list[dict], page: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in sites:
        icon = "🔒" if s.get("is_locked") else "🟢"
        b.button(text=f"{icon} {s['site_name'][:28]}", callback_data=f"site:{s['site_id']}")
    b.adjust(1)
    nav = InlineKeyboardBuilder()
    nav_count = 0
    if page > 0:
        nav.button(text="◀️ Prev", callback_data=f"ms:{page - 1}")
        nav_count += 1
    if (page + 1) * PAGE_SIZE < total:
        nav.button(text="Next ▶️", callback_data=f"ms:{page + 1}")
        nav_count += 1
    if nav_count:
        b.attach(nav)
    foot = InlineKeyboardBuilder()
    foot.button(text="🚀 New", callback_data="new")
    foot.button(text="🏠 Menu", callback_data="menu")
    foot.adjust(2)
    b.attach(foot)
    return b.as_markup()


def site_kb(site: dict, tier: str) -> InlineKeyboardMarkup:
    sid = site["site_id"]
    b = InlineKeyboardBuilder()
    if not site.get("is_locked"):
        b.button(text="🔗 Open Site", url=config.site_url(site["slug"]))
    b.button(text="📂 File Manager", callback_data=f"files:{sid}:0")
    b.button(text="✏️ Custom Slug", callback_data=f"slug:{sid}")
    b.button(text="🏷 Rename", callback_data=f"name:{sid}")
    b.button(text="📱 QR Customizer", callback_data=f"qr:{sid}")
    b.button(text="📊 Analytics", callback_data=f"stat:{sid}")
    b.button(text="🔄 Replace Content", callback_data=f"frep:{sid}")
    domain_label = "🌍 Custom Domain" if config.TIERS[tier]["custom_domain"] else "🌍 Custom Domain 👑"
    b.button(text=domain_label, callback_data=f"dom:{sid}")
    b.button(text="🗑 Delete", callback_data=f"del:{sid}")
    b.button(text="⬅️ My Sites", callback_data="ms:0")
    b.adjust(1, 2, 2, 2, 2, 1)
    return b.as_markup()


def files_kb(site_id: str, rows: list[tuple[str, int]], page: int) -> InlineKeyboardMarkup:
    per_page = 8
    start = page * per_page
    chunk = rows[start:start + per_page]
    b = InlineKeyboardBuilder()
    for i, (name, size) in enumerate(chunk):
        idx = start + i
        b.button(text=f"🗑 {name[-34:]} · {fmt_bytes(size)}", callback_data=f"fdel:{site_id}:{idx}")
    b.adjust(1)
    nav = InlineKeyboardBuilder()
    nav_count = 0
    if page > 0:
        nav.button(text="◀️", callback_data=f"files:{site_id}:{page - 1}")
        nav_count += 1
    if start + per_page < len(rows):
        nav.button(text="▶️", callback_data=f"files:{site_id}:{page + 1}")
        nav_count += 1
    if nav_count:
        b.attach(nav)
    foot = InlineKeyboardBuilder()
    foot.button(text="➕ Add File / ZIP", callback_data=f"fadd:{site_id}")
    foot.button(text="⬅️ Back", callback_data=f"site:{site_id}")
    foot.adjust(1, 1)
    b.attach(foot)
    return b.as_markup()


def confirm_kb(yes_cb: str, no_cb: str, yes_label: str = "✅ Yes, delete") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=yes_label, callback_data=yes_cb)
    b.button(text="✖️ No", callback_data=no_cb)
    b.adjust(2)
    return b.as_markup()


def qr_kb(site_id: str, has_logo: bool) -> InlineKeyboardMarkup:
    from services.qr_generator import STYLES  # local import keeps ui import-light

    b = InlineKeyboardBuilder()
    icons = {"neon": "🌌", "gradient": "🎨", "classic": "⬛"}
    for key, label in STYLES.items():
        b.button(text=f"{icons[key]} {label}", callback_data=f"qrs:{site_id}:{key}")
    b.button(text="🖼 Set Logo", callback_data=f"qrlogo:{site_id}")
    if has_logo:
        b.button(text="❌ Remove Logo", callback_data=f"qrnologo:{site_id}")
    b.button(text="⬅️ Back", callback_data=f"site:{site_id}")
    b.adjust(1)
    return b.as_markup()


# --------------------------------------------------------------------------- #
# Admin keyboards
# --------------------------------------------------------------------------- #
def admin_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Dashboard", callback_data="adm:dash")
    b.button(text="👥 Users", callback_data="adm:users")
    b.button(text="🌐 Sites", callback_data="adm:sites:0")
    b.button(text="📣 Broadcast", callback_data="adm:bc")
    b.button(text="🏠 Main Menu", callback_data="menu")
    b.adjust(2, 2, 1)
    return b.as_markup()


def admin_user_kb(user_doc: dict) -> InlineKeyboardMarkup:
    tid = user_doc["telegram_id"]
    b = InlineKeyboardBuilder()
    if user_doc.get("is_banned"):
        b.button(text="✅ Unban", callback_data=f"adm:unban:{tid}")
    else:
        b.button(text="🚫 Ban", callback_data=f"adm:ban:{tid}")
    if user_doc.get("tier") == "VIP":
        b.button(text="⬇️ Demote to Free", callback_data=f"adm:free:{tid}")
    else:
        b.button(text="👑 Promote to VIP", callback_data=f"adm:vip:{tid}")
    b.button(text="🌐 Their Sites", callback_data=f"adm:usites:{tid}")
    b.button(text="⬅️ Back", callback_data="adm")
    b.adjust(2, 1, 1)
    return b.as_markup()


def admin_site_kb(site: dict) -> InlineKeyboardMarkup:
    sid = site["site_id"]
    b = InlineKeyboardBuilder()
    if site.get("is_locked"):
        b.button(text="🔓 Unlock", callback_data=f"adm:sunlock:{sid}")
    else:
        b.button(text="🔒 Lock", callback_data=f"adm:slock:{sid}")
    b.button(text="🗑 Delete", callback_data=f"adm:sdel:{sid}")
    b.button(text="👤 Owner", callback_data=f"adm:u:{site['owner_id']}")
    b.button(text="⬅️ Sites", callback_data="adm:sites:0")
    b.adjust(2, 2)
    return b.as_markup()


def admin_sites_kb(sites: list[dict], page: int, total: int, per_page: int = 8) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in sites:
        icon = "🔒" if s.get("is_locked") else "🟢"
        b.button(text=f"{icon} {s['slug'][:20]} · 👁{s.get('views_count', 0)}",
                 callback_data=f"adm:s:{s['site_id']}")
    b.adjust(1)
    nav = InlineKeyboardBuilder()
    nav_count = 0
    if page > 0:
        nav.button(text="◀️", callback_data=f"adm:sites:{page - 1}")
        nav_count += 1
    if (page + 1) * per_page < total:
        nav.button(text="▶️", callback_data=f"adm:sites:{page + 1}")
        nav_count += 1
    if nav_count:
        b.attach(nav)
    foot = InlineKeyboardBuilder()
    foot.button(text="🔎 Search Site", callback_data="adm:ssearch")
    foot.button(text="⬅️ Back", callback_data="adm")
    foot.adjust(2)
    b.attach(foot)
    return b.as_markup()