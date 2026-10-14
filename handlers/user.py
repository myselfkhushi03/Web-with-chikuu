"""
handlers/user.py — Commands, callbacks and FSM flows for regular users.

Covers: onboarding, deploying (HTML / ZIP / pasted code), My Sites, File Manager,
custom slugs / names / domains, QR customizer, analytics, profile and help.
"""
from __future__ import annotations

import asyncio
import io
import logging
import re
import uuid
from pathlib import Path
from typing import Awaitable, Callable, Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from PIL import Image
from pymongo.errors import DuplicateKeyError

import config
import ui
from database import db
from services import deployment as dep
from services.deployment import DeploymentError
from services.qr_generator import STYLES, QRError, generate_qr

log = logging.getLogger(__name__)
router = Router(name="user")


# --------------------------------------------------------------------------- #
# FSM states
# --------------------------------------------------------------------------- #
class DeployStates(StatesGroup):
    paste = State()      # waiting for pasted HTML code
    add_file = State()   # adding files to an existing site
    replace = State()    # replacing a site's whole content


class EditStates(StatesGroup):
    slug = State()
    name = State()
    domain = State()
    logo = State()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _is_admin(uid: int) -> bool:
    return uid in config.ADMIN_IDS


async def _edit(cb: CallbackQuery, text: str, kb=None) -> None:
    """Edit the callback's message; fall back to a fresh message if impossible."""
    msg = cb.message
    try:
        if isinstance(msg, Message):
            await msg.edit_text(text, reply_markup=kb)
            return
    except TelegramBadRequest as exc:
        if "not modified" in str(exc).lower():
            return
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=kb)  # type: ignore[union-attr]


async def _owned_site(cb: CallbackQuery, site_id: str, *, need_unlocked: bool = False) -> Optional[dict]:
    site = await db.get_site(site_id)
    if not site or site["owner_id"] != cb.from_user.id:
        await cb.answer("❌ Site not found.", show_alert=True)
        return None
    if need_unlocked and site.get("is_locked"):
        await cb.answer("🔒 This site is locked by an administrator.", show_alert=True)
        return None
    return site


def _limits(db_user: dict, uid: int) -> tuple[str, dict]:
    tier = ui.tier_of(db_user, uid)
    return tier, config.TIERS[tier]


def _public_base(site: dict) -> str:
    if site.get("custom_domain"):
        return f"https://{site['custom_domain']}/"
    return config.site_url(site["slug"])


def _logo_path(uid: int) -> Path:
    return config.LOGO_DIR / f"{uid}.png"


async def _show_site(cb: CallbackQuery, site: dict, db_user: dict) -> None:
    tier = ui.tier_of(db_user, cb.from_user.id)
    await _edit(cb, ui.site_text(site, tier), ui.site_kb(site, tier))


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    tier = ui.tier_of(db_user, message.from_user.id)
    await message.answer(
        ui.welcome_text(message.from_user.first_name or "there", tier),
        reply_markup=ui.main_menu_kb(_is_admin(message.from_user.id)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(ui.help_text(), reply_markup=ui.back_kb())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(f"{ui.BADGE_OK} Cancelled.", reply_markup=ui.main_menu_kb(_is_admin(message.from_user.id)))


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_new_text(), reply_markup=ui.new_site_kb())


@router.message(Command("mysites"))
async def cmd_mysites(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, kb = await _my_sites_view(message.from_user.id, 0)
    await message.answer(text, reply_markup=kb)


@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    await message.answer(await _profile_view(db_user, message.from_user.id), reply_markup=ui.back_kb())


def _new_text() -> str:
    return (
        f"{ui.HEADER}\n{ui.LINE}\n"
        "🚀 <b>Create a new website</b>\n\n"
        "• Send an <code>.html</code> file\n"
        "• Send a <code>.zip</code> with your whole site\n"
        "• Or paste your HTML code as a message\n\n"
        "<i>No index.html in your ZIP? I'll generate a clean default page.</i>"
    )


async def _my_sites_view(uid: int, page: int):
    total = await db.count_sites_by_owner(uid)
    sites = await db.list_sites_by_owner(uid, skip=page * ui.PAGE_SIZE, limit=ui.PAGE_SIZE)
    if not total:
        return (
            f"{ui.HEADER}\n{ui.LINE}\n📭 You have no websites yet.\nTap <b>New</b> to publish your first one!",
            ui.new_site_kb(),
        )
    text = f"{ui.HEADER}\n{ui.LINE}\n🌐 <b>Mყ Sɪƫҽs</b> — {total} total\nSelect a site to manage it:"
    return text, ui.site_list_kb(sites, page, total)


async def _profile_view(db_user: dict, uid: int) -> str:
    tier = ui.tier_of(db_user, uid)
    sites = await db.count_sites_by_owner(uid)
    views = await db.total_views(uid)
    return ui.profile_text(db_user, tier, sites, views)


# --------------------------------------------------------------------------- #
# Main navigation callbacks
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    tier = ui.tier_of(db_user, cb.from_user.id)
    await _edit(cb, ui.welcome_text(cb.from_user.first_name or "there", tier),
                ui.main_menu_kb(_is_admin(cb.from_user.id)))
    await cb.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    tier = ui.tier_of(db_user, cb.from_user.id)
    await _edit(cb, ui.welcome_text(cb.from_user.first_name or "there", tier),
                ui.main_menu_kb(_is_admin(cb.from_user.id)))
    await cb.answer("Cancelled")


@router.callback_query(F.data == "help")
async def cb_help(cb: CallbackQuery) -> None:
    await _edit(cb, ui.help_text(), ui.back_kb())
    await cb.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery, db_user: dict) -> None:
    await _edit(cb, await _profile_view(db_user, cb.from_user.id), ui.back_kb())
    await cb.answer()


@router.callback_query(F.data == "new")
async def cb_new(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(cb, _new_text(), ui.new_site_kb())
    await cb.answer()


@router.callback_query(F.data == "new:upload")
async def cb_new_upload(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n📄 <b>Send your file now</b>\n"
        "Accepted: <code>.html</code> · <code>.htm</code> · <code>.zip</code>",
        ui.cancel_kb(),
    )
    await cb.answer()


@router.callback_query(F.data == "new:paste")
async def cb_new_paste(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DeployStates.paste)
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n⌨️ <b>Paste your HTML code</b> in the next message.\n"
        "A bare snippet gets wrapped into a full responsive page automatically.",
        ui.cancel_kb(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ms:"))
async def cb_my_sites(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        page = max(0, int(cb.data.split(":")[1]))
    except (IndexError, ValueError):
        page = 0
    text, kb = await _my_sites_view(cb.from_user.id, page)
    await _edit(cb, text, kb)
    await cb.answer()


@router.callback_query(F.data.startswith("site:"))
async def cb_site(cb: CallbackQuery, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    await _show_site(cb, site, db_user)
    await cb.answer()


# --------------------------------------------------------------------------- #
# Deployment core
# --------------------------------------------------------------------------- #
Runner = Callable[[str, dict], Awaitable[dep.DeployResult]]


async def _create_site(message: Message, db_user: dict, name: str, runner: Runner,
                       status: Optional[Message] = None) -> None:
    """Shared "new site" pipeline for pasted code, HTML files and ZIPs."""
    uid = message.from_user.id
    tier, limits = _limits(db_user, uid)
    if await db.count_sites_by_owner(uid) >= limits["max_sites"]:
        text = (f"{ui.BADGE_ERR} Site limit reached (<b>{limits['max_sites']}</b> on the "
                f"{tier} plan). Delete a site first.")
        if status:
            await status.edit_text(text, reply_markup=ui.back_kb("ms:0", "🌐 My Sites"))
        else:
            await message.answer(text, reply_markup=ui.back_kb("ms:0", "🌐 My Sites"))
        return

    status = status or await message.answer(f"{ui.BADGE_PROC} Deploying your website…")
    site_id = dep.new_site_id()
    try:
        result = await runner(site_id, limits)
    except DeploymentError as exc:
        dep.remove_site_files(site_id)
        await status.edit_text(f"{ui.BADGE_ERR} {ui.esc(exc)}", reply_markup=ui.back_kb("new", "🔁 Try again"))
        return
    except Exception:
        log.exception("deployment failed")
        dep.remove_site_files(site_id)
        await status.edit_text(f"{ui.BADGE_ERR} Unexpected error while deploying. Please try again.",
                               reply_markup=ui.back_kb("new", "🔁 Try again"))
        return

    site_name = (name or "My Website")[:40]
    slug = await dep.unique_slug(site_name)
    site = None
    for attempt in range(3):
        try:
            site = await db.create_site(
                site_id=site_id, owner_id=uid, slug=slug, site_name=site_name,
                file_path=str(dep.site_dir(site_id)), size_bytes=result.total_size,
            )
            break
        except DuplicateKeyError:
            slug = f"site-{uuid.uuid4().hex[:8]}"
    if site is None:
        dep.remove_site_files(site_id)
        await status.edit_text(f"{ui.BADGE_ERR} Could not reserve a link. Please try again.")
        return

    await status.edit_text(
        ui.deployed_text(site, result.files, result.total_size, result.skipped, result.generated_index),
        reply_markup=ui.site_kb(site, tier),
    )


async def _download(bot: Bot, message: Message, file_name: str) -> Path:
    config.TMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.TMP_DIR / f"{uuid.uuid4().hex}_{file_name}"
    await bot.download(message.document, destination=dest)
    return dest


# --------------------------------------------------------------------------- #
# Pasted code
# --------------------------------------------------------------------------- #
async def _deploy_pasted(message: Message, state: FSMContext, db_user: dict) -> None:
    await state.clear()
    code = message.text or ""

    async def runner(site_id: str, limits: dict) -> dep.DeployResult:
        return await dep.deploy_text(site_id, code, limits=limits, title="My Website")

    title_match = re.search(r"<title>(.*?)</title>", code, re.IGNORECASE | re.DOTALL)
    name = (title_match.group(1).strip() if title_match else "") or "My Website"
    await _create_site(message, db_user, name, runner)


@router.message(DeployStates.paste, F.text, ~F.text.startswith("/"))
async def on_paste(message: Message, state: FSMContext, db_user: dict) -> None:
    await _deploy_pasted(message, state, db_user)


# --------------------------------------------------------------------------- #
# Edit flows (slug / name / domain / logo)
# --------------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("slug:"))
async def cb_slug(cb: CallbackQuery, state: FSMContext) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1], need_unlocked=True)
    if not site:
        return
    await state.set_state(EditStates.slug)
    await state.update_data(site_id=site["site_id"])
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n✏️ <b>Custom Slug</b>\n"
        f"Current: <code>/s/{ui.esc(site['slug'])}/</code>\n\n"
        "Send the new name (3–32 chars: <code>a-z 0-9 -</code>).\nExample: <code>my-portfolio</code>",
        ui.back_kb(f"site:{site['site_id']}", "✖️ Cancel"),
    )
    await cb.answer()


@router.message(EditStates.slug, F.text, ~F.text.startswith("/"))
async def on_slug(message: Message, state: FSMContext, db_user: dict) -> None:
    data = await state.get_data()
    site = await db.get_site(data.get("site_id", ""))
    if not site or site["owner_id"] != message.from_user.id or site.get("is_locked"):
        await state.clear()
        await message.answer(f"{ui.BADGE_ERR} Site unavailable.")
        return
    slug = dep.slugify(message.text.strip().removeprefix("/s/"))
    error = dep.validate_slug(slug)
    if error:
        await message.answer(f"{ui.BADGE_ERR} {ui.esc(error)}\nTry another one or /cancel.")
        return
    if not await db.slug_available(slug, exclude_site_id=site["site_id"]):
        await message.answer(f"{ui.BADGE_ERR} <code>{ui.esc(slug)}</code> is already taken. Try another.")
        return
    try:
        await db.update_site(site["site_id"], {"slug": slug})
    except DuplicateKeyError:
        await message.answer(f"{ui.BADGE_ERR} <code>{ui.esc(slug)}</code> was just taken. Try another.")
        return
    await state.clear()
    site["slug"] = slug
    tier = ui.tier_of(db_user, message.from_user.id)
    await message.answer(f"{ui.BADGE_OK} <b>Slug updated!</b>\n\n" + ui.site_text(site, tier),
                         reply_markup=ui.site_kb(site, tier))


@router.callback_query(F.data.startswith("name:"))
async def cb_name(cb: CallbackQuery, state: FSMContext) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    await state.set_state(EditStates.name)
    await state.update_data(site_id=site["site_id"])
    await _edit(cb, f"{ui.HEADER}\n{ui.LINE}\n🏷 Send a new <b>display name</b> (max 40 characters).",
                ui.back_kb(f"site:{site['site_id']}", "✖️ Cancel"))
    await cb.answer()


@router.message(EditStates.name, F.text, ~F.text.startswith("/"))
async def on_name(message: Message, state: FSMContext, db_user: dict) -> None:
    data = await state.get_data()
    site = await db.get_site(data.get("site_id", ""))
    name = message.text.strip()[:40]
    if not site or site["owner_id"] != message.from_user.id or not name:
        await state.clear()
        await message.answer(f"{ui.BADGE_ERR} Could not rename.")
        return
    await db.update_site(site["site_id"], {"site_name": name})
    await state.clear()
    site["site_name"] = name
    tier = ui.tier_of(db_user, message.from_user.id)
    await message.answer(f"{ui.BADGE_OK} Renamed.\n\n" + ui.site_text(site, tier),
                         reply_markup=ui.site_kb(site, tier))


@router.callback_query(F.data.startswith("dom:"))
async def cb_domain(cb: CallbackQuery, state: FSMContext, db_user: dict) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1], need_unlocked=True)
    if not site:
        return
    tier, limits = _limits(db_user, cb.from_user.id)
    if not limits["custom_domain"]:
        await cb.answer("👑 Custom domains are a VIP feature.", show_alert=True)
        return
    await state.set_state(EditStates.domain)
    await state.update_data(site_id=site["site_id"])
    extra = (f"• Or just a prefix (e.g. <code>shop</code>) → <code>shop.{ui.esc(config.WILDCARD_DOMAIN)}</code>\n"
             if config.WILDCARD_DOMAIN else "")
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n🌍 <b>Custom Domain</b>\n"
        f"Current: <code>{ui.esc(site.get('custom_domain') or 'none')}</code>\n\n"
        f"• Send your domain (e.g. <code>www.example.com</code>) and point its CNAME to "
        f"<code>{ui.esc(config.MAIN_HOST)}</code>. The domain must also be added in your hosting "
        f"provider's custom-domain settings.\n{extra}"
        "• Send <code>-</code> to remove the domain.",
        ui.back_kb(f"site:{site['site_id']}", "✖️ Cancel"),
    )
    await cb.answer()


@router.message(EditStates.domain, F.text, ~F.text.startswith("/"))
async def on_domain(message: Message, state: FSMContext, db_user: dict) -> None:
    data = await state.get_data()
    site = await db.get_site(data.get("site_id", ""))
    uid = message.from_user.id
    tier, limits = _limits(db_user, uid)
    if not site or site["owner_id"] != uid or site.get("is_locked") or not limits["custom_domain"]:
        await state.clear()
        await message.answer(f"{ui.BADGE_ERR} Custom domain is unavailable.")
        return

    raw = message.text.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    if raw == "-":
        domain = ""
    elif "." not in raw and config.WILDCARD_DOMAIN:
        prefix = dep.slugify(raw)
        if dep.validate_slug(prefix):
            await message.answer(f"{ui.BADGE_ERR} Invalid prefix. Use letters, numbers and hyphens (3+).")
            return
        domain = f"{prefix}.{config.WILDCARD_DOMAIN}"
        await db.set_domain_prefix(uid, prefix)
    else:
        error = dep.validate_domain(raw)
        if error:
            await message.answer(f"{ui.BADGE_ERR} {ui.esc(error)}")
            return
        domain = raw

    if domain and not await db.domain_available(domain, exclude_site_id=site["site_id"]):
        await message.answer(f"{ui.BADGE_ERR} That domain is already used by another site.")
        return
    try:
        await db.update_site(site["site_id"], {"custom_domain": domain})
    except DuplicateKeyError:
        await message.answer(f"{ui.BADGE_ERR} That domain is already used by another site.")
        return
    await state.clear()
    site["custom_domain"] = domain
    await message.answer(f"{ui.BADGE_OK} Domain {'saved' if domain else 'removed'}.\n\n"
                         + ui.site_text(site, tier), reply_markup=ui.site_kb(site, tier))


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("stat:"))
async def cb_stats(cb: CallbackQuery) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    files = await asyncio.to_thread(dep.count_files, dep.site_dir(site["site_id"]))
    size = await asyncio.to_thread(dep.dir_size, dep.site_dir(site["site_id"]))
    qrs = await db.count_qr(site["site_id"])
    status = ui.BADGE_LOCKED if site.get("is_locked") else ui.BADGE_ACTIVE
    text = (
        f"{ui.HEADER}\n{ui.LINE}\n📊 <b>Anαℓყƫιcѕ</b> — {ui.esc(site['site_name'])}\n"
        f"Status: {status}\n"
        f"👁 Page views: <b>{site.get('views_count', 0)}</b>\n"
        f"📁 Files: <b>{files}</b>\n"
        f"💾 Storage: <b>{ui.fmt_bytes(size)}</b>\n"
        f"📱 QR codes made: <b>{qrs}</b>\n"
        f"🕒 Created: {ui.fmt_dt(site.get('created_at'))}\n"
        f"🔄 Updated: {ui.fmt_dt(site.get('updated_at'))}"
    )
    await _edit(cb, text, ui.back_kb(f"site:{site['site_id']}"))
    await cb.answer()


# --------------------------------------------------------------------------- #
# File manager
# --------------------------------------------------------------------------- #
async def _render_files(cb: CallbackQuery, site: dict, page: int) -> None:
    rows = await asyncio.to_thread(dep.list_site_files, site["site_id"])
    page = max(0, min(page, max(0, (len(rows) - 1) // 8)))
    total = sum(s for _, s in rows)
    text = (
        f"{ui.HEADER}\n{ui.LINE}\n📂 <b>Fιʅҽ Mαɳαɠҽɾ</b> — {ui.esc(site['site_name'])}\n"
        f"{len(rows)} file(s) · {ui.fmt_bytes(total)}\n"
        "Tap a file to <b>delete</b> it."
    )
    await _edit(cb, text, ui.files_kb(site["site_id"], rows, page))


@router.callback_query(F.data.startswith("files:"))
async def cb_files(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    parts = cb.data.split(":")
    site = await _owned_site(cb, parts[1])
    if not site:
        return
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _render_files(cb, site, page)
    await cb.answer()


@router.callback_query(F.data.startswith("fdel:"))
async def cb_file_delete(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    site = await _owned_site(cb, parts[1], need_unlocked=True)
    if not site or len(parts) < 3 or not parts[2].isdigit():
        return
    idx = int(parts[2])
    rows = await asyncio.to_thread(dep.list_site_files, site["site_id"])
    if idx >= len(rows):
        await cb.answer("File no longer exists.", show_alert=True)
        await _render_files(cb, site, 0)
        return
    name = rows[idx][0]
    ok = await asyncio.to_thread(dep.delete_site_file, site["site_id"], name)
    size = await asyncio.to_thread(dep.dir_size, dep.site_dir(site["site_id"]))
    await db.update_site(site["site_id"], {"size_bytes": size})
    await cb.answer(f"🗑 Deleted {name[-40:]}" if ok else "Could not delete.", show_alert=not ok)
    await _render_files(cb, site, idx // 8)


@router.callback_query(F.data.startswith("fadd:"))
async def cb_file_add(cb: CallbackQuery, state: FSMContext) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1], need_unlocked=True)
    if not site:
        return
    await state.set_state(DeployStates.add_file)
    await state.update_data(site_id=site["site_id"])
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n➕ <b>Add files</b> to <b>{ui.esc(site['site_name'])}</b>\n"
        "Send any allowed static file (css, js, images, fonts, html…) or a <code>.zip</code> to merge.\n"
        "Send as <b>File/Document</b> so the name is kept. Tap Done when finished.",
        ui.back_kb(f"site:{site['site_id']}", "✅ Done"),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("frep:"))
async def cb_file_replace(cb: CallbackQuery, state: FSMContext) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1], need_unlocked=True)
    if not site:
        return
    await state.set_state(DeployStates.replace)
    await state.update_data(site_id=site["site_id"])
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n🔄 <b>Replace content</b> of <b>{ui.esc(site['site_name'])}</b>\n"
        "Send an <code>.html</code> or <code>.zip</code>. ⚠️ All current files will be replaced; "
        "the link stays the same.",
        ui.back_kb(f"site:{site['site_id']}", "✖️ Cancel"),
    )
    await cb.answer()


# --------------------------------------------------------------------------- #
# Delete site
# --------------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("del:"))
async def cb_delete(cb: CallbackQuery) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n⚠️ Delete <b>{ui.esc(site['site_name'])}</b> permanently?\n"
        "All files and QR records will be removed.",
        ui.confirm_kb(f"delok:{site['site_id']}", f"site:{site['site_id']}"),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("delok:"))
async def cb_delete_ok(cb: CallbackQuery) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    await asyncio.to_thread(dep.remove_site_files, site["site_id"])
    await db.delete_site(site["site_id"])
    await cb.answer("🗑 Site deleted")
    text, kb = await _my_sites_view(cb.from_user.id, 0)
    await _edit(cb, text, kb)


# --------------------------------------------------------------------------- #
# QR customizer
# --------------------------------------------------------------------------- #
@router.callback_query(F.data.startswith("qr:"))
async def cb_qr(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    has_logo = _logo_path(cb.from_user.id).exists()
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n📱 <b>QR Cυʂƚσɱιʐҽɾ</b>\n"
        f"🔗 <code>{ui.esc(_public_base(site))}</code>\n\n"
        "Pick a style. Codes are generated offline, use a plain <code>https://</code> link and "
        "scan in PhonePe, Google Pay, Paytm and any phone camera.\n"
        f"🖼 Logo: <b>{'set' if has_logo else 'none'}</b>",
        ui.qr_kb(site["site_id"], has_logo),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("qrs:"))
async def cb_qr_style(cb: CallbackQuery, bot: Bot) -> None:
    parts = cb.data.split(":")
    if len(parts) != 3 or parts[2] not in STYLES:
        await cb.answer("Unknown style.", show_alert=True)
        return
    site = await _owned_site(cb, parts[1])
    if not site:
        return
    if site.get("is_locked"):
        await cb.answer("🔒 This site is locked.", show_alert=True)
        return
    style = parts[2]
    await cb.answer("⚡ Generating…")
    uid = cb.from_user.id
    logo = None
    lp = _logo_path(uid)
    if lp.exists():
        logo = await asyncio.to_thread(lp.read_bytes)
    url = _public_base(site)
    try:
        png, report = await asyncio.to_thread(generate_qr, url, style, logo)
    except QRError as exc:
        await bot.send_message(uid, f"{ui.BADGE_ERR} {ui.esc(exc)}")
        return
    except Exception:
        log.exception("QR generation failed")
        await bot.send_message(uid, f"{ui.BADGE_ERR} Could not generate the QR code.")
        return

    await db.create_qr(uuid.uuid4().hex[:12], site["site_id"], style)
    verdict = "✅ Scan check passed" if report.ok else "⚠️ Scan check warning"
    caption = (
        f"{ui.BADGE_OK} <b>{ui.esc(STYLES[style])}</b>\n"
        f"🔗 {ui.esc(url)}\n"
        f"{verdict} · contrast {report.contrast}:1 · QR v{report.version}\n"
        "📲 Works with PhonePe · GPay · Paytm · camera"
    )
    await bot.send_document(
        uid,
        BufferedInputFile(png, filename=f"webify_{site['slug']}_{style}.png"),
        caption=caption,
        reply_markup=ui.back_kb(f"qr:{site['site_id']}", "🎨 Another style"),
    )


@router.callback_query(F.data.startswith("qrlogo:"))
async def cb_qr_logo(cb: CallbackQuery, state: FSMContext) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    await state.set_state(EditStates.logo)
    await state.update_data(site_id=site["site_id"])
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n🖼 Send your <b>logo</b> as a photo or PNG/JPG file "
        "(square works best, max 5 MB). It will be placed at the center of your QR codes.",
        ui.back_kb(f"qr:{site['site_id']}", "✖️ Cancel"),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("qrnologo:"))
async def cb_qr_nologo(cb: CallbackQuery) -> None:
    site = await _owned_site(cb, cb.data.split(":")[1])
    if not site:
        return
    _logo_path(cb.from_user.id).unlink(missing_ok=True)
    await cb.answer("Logo removed")
    await _edit(cb, f"{ui.HEADER}\n{ui.LINE}\n📱 <b>QR Cυʂƚσɱιʐҽɾ</b>\n🖼 Logo: <b>none</b>",
                ui.qr_kb(site["site_id"], False))


@router.message(EditStates.logo, F.photo | F.document)
async def on_logo(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    site_id = data.get("site_id", "")
    if message.photo:
        file_obj, size = message.photo[-1], message.photo[-1].file_size or 0
    else:
        file_obj, size = message.document, message.document.file_size or 0
        if not (message.document.mime_type or "").startswith("image/"):
            await message.answer(f"{ui.BADGE_ERR} Please send an image (PNG/JPG).")
            return
    if size > 5 * config.MB:
        await message.answer(f"{ui.BADGE_ERR} Logo is too large (max 5 MB).")
        return
    buf = io.BytesIO()
    try:
        await bot.download(file_obj, destination=buf)
        buf.seek(0)
        img = Image.open(buf)
        img.load()
        img = img.convert("RGBA")
        img.thumbnail((512, 512), Image.LANCZOS)
        config.LOGO_DIR.mkdir(parents=True, exist_ok=True)
        img.save(_logo_path(message.from_user.id), format="PNG")
    except Exception:
        log.exception("logo save failed")
        await message.answer(f"{ui.BADGE_ERR} I couldn't read that image. Try a PNG or JPG.")
        return
    await state.clear()
    await message.answer(f"{ui.BADGE_OK} Logo saved! Pick a style to generate your QR.",
                         reply_markup=ui.qr_kb(site_id, True) if site_id else ui.back_kb())


# --------------------------------------------------------------------------- #
# Document uploads (new site / add file / replace content)
# --------------------------------------------------------------------------- #
@router.message(F.document)
async def on_document(message: Message, state: FSMContext, bot: Bot, db_user: dict) -> None:
    uid = message.from_user.id
    doc = message.document
    tier, limits = _limits(db_user, uid)

    st = await state.get_state()
    data = await state.get_data()
    mode, site = "new", None
    if st in (DeployStates.add_file.state, DeployStates.replace.state):
        mode = "add" if st == DeployStates.add_file.state else "replace"
        site = await db.get_site(data.get("site_id", ""))
        if not site or site["owner_id"] != uid or site.get("is_locked"):
            await state.clear()
            await message.answer(f"{ui.BADGE_ERR} That site is unavailable.")
            return

    fname = dep.sanitize_filename(doc.file_name or "upload.html")
    ext = Path(fname).suffix.lower()

    if ext in config.BLOCKED_EXTENSIONS:
        await message.answer(
            f"{ui.BADGE_ERR} <b>Blocked file type</b> <code>{ui.esc(ext)}</code>.\n"
            "Scripts and executables are never accepted — only static web assets.")
        return
    if ext != config.ARCHIVE_EXTENSION and ext not in config.ALLOWED_EXTENSIONS:
        await message.answer(
            f"{ui.BADGE_ERR} <code>{ui.esc(ext or 'no extension')}</code> isn't an allowed static asset. "
            "See /help for the supported types.")
        return
    if mode == "new" and ext not in (".html", ".htm", ".zip"):
        await message.answer(
            f"{ui.BADGE_ERR} To start a site, send an <code>.html</code> or <code>.zip</code>.\n"
            "Assets like CSS/images can be added later via <b>My Sites → File Manager</b>.")
        return
    if mode == "replace" and ext not in (".html", ".htm", ".zip"):
        await message.answer(f"{ui.BADGE_ERR} To replace a site, send an <code>.html</code> or <code>.zip</code>.")
        return
    if (doc.file_size or 0) > limits["max_upload"]:
        await message.answer(
            f"{ui.BADGE_ERR} File too large — your <b>{tier}</b> plan allows "
            f"{ui.fmt_bytes(limits['max_upload'])} per upload.")
        return

    status = await message.answer(f"{ui.BADGE_PROC} Downloading &amp; processing <code>{ui.esc(fname)}</code>…")
    tmp: Optional[Path] = None
    try:
        tmp = await _download(bot, message, fname)
    except TelegramBadRequest:
        await status.edit_text(f"{ui.BADGE_ERR} Telegram refused the download (files over 20 MB can't be fetched).")
        return
    except Exception:
        log.exception("download failed")
        await status.edit_text(f"{ui.BADGE_ERR} Download failed. Please try again.")
        return

    try:
        is_zip = ext == ".zip"
        stem = Path(fname).stem

        if mode == "new":
            await state.clear()

            async def runner(site_id: str, lim: dict) -> dep.DeployResult:
                if is_zip:
                    return await dep.deploy_archive(tmp, site_id, replace=True, limits=lim, title=stem)
                return await dep.deploy_file(tmp, site_id, fname, as_index=True, replace=True,
                                             limits=lim, title=stem)

            await _create_site(message, db_user, stem, runner, status=status)
            return

        assert site is not None
        replace = mode == "replace"
        try:
            if is_zip:
                result = await dep.deploy_archive(tmp, site["site_id"], replace=replace,
                                                  limits=limits, title=site["site_name"])
            else:
                result = await dep.deploy_file(tmp, site["site_id"], fname, as_index=replace,
                                               replace=replace, limits=limits, title=site["site_name"])
        except DeploymentError as exc:
            await status.edit_text(f"{ui.BADGE_ERR} {ui.esc(exc)}",
                                   reply_markup=ui.back_kb(f"site:{site['site_id']}"))
            return
        await db.update_site(site["site_id"], {"size_bytes": result.total_size})
        site["size_bytes"] = result.total_size
        if replace:
            await state.clear()
        tier_now = ui.tier_of(db_user, uid)
        head = "UPDΛTΞD" if replace else "FILΞ ΛDDΞD"
        await status.edit_text(
            ui.deployed_text(site, result.files, result.total_size, result.skipped,
                             result.generated_index, headline=head),
            reply_markup=ui.site_kb(site, tier_now) if replace else ui.back_kb(f"site:{site['site_id']}", "✅ Done"),
        )
    except Exception:
        log.exception("document handling failed")
        await status.edit_text(f"{ui.BADGE_ERR} Unexpected error. Please try again.")
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Fallbacks
# --------------------------------------------------------------------------- #
@router.message(F.text & ~F.text.startswith("/"))
async def on_text_fallback(message: Message, state: FSMContext, db_user: dict) -> None:
    """Plain text outside a flow: auto-deploy if it looks like a full HTML page."""
    low = (message.text or "").lower()
    if len(low) > 40 and ("<html" in low or "<!doctype html" in low):
        await _deploy_pasted(message, state, db_user)
        return
    await message.answer(
        f"{ui.HEADER}\n{ui.LINE}\nSend me an <code>.html</code> / <code>.zip</code> file, "
        "paste a full HTML page, or use the menu.",
        reply_markup=ui.main_menu_kb(_is_admin(message.from_user.id)),
    )


@router.message(F.photo)
async def on_photo_fallback(message: Message) -> None:
    await message.answer("📎 Please send files as <b>File/Document</b> (not as a compressed photo). "
                         "To set a QR logo use <b>My Sites → QR Customizer → Set Logo</b>.")