"""
handlers/admin.py — Admin panel: dashboard, user/site moderation, broadcast engine.

Only users listed in ADMIN_IDS can reach these handlers. Non-admins who somehow
trigger an ``adm*`` callback receive a polite refusal from ``guard_router``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import psutil
from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import ui
from database import db
from services import deployment as dep

log = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

guard_router = Router(name="admin_guard")

SITES_PER_PAGE = 8
_BOOT_TIME = time.time()
_background: set[asyncio.Task] = set()   # strong refs so tasks aren't garbage collected


class AdminStates(StatesGroup):
    user_search = State()
    site_search = State()
    broadcast = State()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _edit(cb: CallbackQuery, text: str, kb=None) -> None:
    try:
        if isinstance(cb.message, Message):
            await cb.message.edit_text(text, reply_markup=kb)
            return
    except TelegramBadRequest as exc:
        if "not modified" in str(exc).lower():
            return
    await cb.bot.send_message(cb.from_user.id, text, reply_markup=kb)  # type: ignore[union-attr]


def _admin_home_text() -> str:
    return f"{ui.HEADER}\n{ui.LINE}\n🛠 <b>ΛDMIN PΛNΞL</b>\nChoose a section:"


def _system_snapshot() -> dict:
    proc = psutil.Process()
    vm = psutil.virtual_memory()
    try:
        disk = psutil.disk_usage(str(config.DATA_DIR))
        disk_pct, disk_used, disk_total = disk.percent, disk.used, disk.total
    except Exception:
        disk_pct = disk_used = disk_total = 0
    return {
        "cpu": psutil.cpu_percent(interval=0.4),
        "ram_pct": vm.percent,
        "ram_used": vm.used,
        "ram_total": vm.total,
        "proc_rss": proc.memory_info().rss,
        "disk_pct": disk_pct,
        "disk_used": disk_used,
        "disk_total": disk_total,
        "storage": dep.dir_size(config.HOSTED_DIR),
        "uptime": time.time() - _BOOT_TIME,
    }


def _fmt_uptime(seconds: float) -> str:
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    return f"{d}d {h}h {m}m" if d else f"{h}h {m}m"


async def _dashboard_text() -> str:
    snap = await asyncio.to_thread(_system_snapshot)
    users = await db.count_users()
    vips = await db.count_users({"tier": "VIP"})
    banned = await db.count_users({"is_banned": True})
    sites = await db.count_sites()
    locked = await db.count_sites({"is_locked": True})
    views = await db.total_views()
    qrs = await db.count_qr()
    return (
        f"✨ <b>WΞBIFY DΛSΗBΘΛRD</b> ✨\n{ui.LINE}\n"
        f"🖥 <b>CPU</b>  {ui.progress_bar(snap['cpu'])} {snap['cpu']:.0f}%\n"
        f"🧠 <b>RAM</b>  {ui.progress_bar(snap['ram_pct'])} {snap['ram_pct']:.0f}% "
        f"({ui.fmt_bytes(snap['ram_used'])}/{ui.fmt_bytes(snap['ram_total'])})\n"
        f"💽 <b>Disk</b> {ui.progress_bar(snap['disk_pct'])} {snap['disk_pct']:.0f}%\n"
        f"⚙️ Bot process: <b>{ui.fmt_bytes(snap['proc_rss'])}</b> · ⏱ {_fmt_uptime(snap['uptime'])}\n"
        f"{ui.LINE}\n"
        f"👥 Users: <b>{users}</b> (👑 {vips} VIP · 🚫 {banned} banned)\n"
        f"🌐 Sites: <b>{sites}</b> {ui.BADGE_ACTIVE} · 🔒 {locked} locked\n"
        f"👁 Total views: <b>{views}</b> · 📱 QR codes: <b>{qrs}</b>\n"
        f"📦 Storage footprint: <b>{ui.fmt_bytes(snap['storage'])}</b>"
    )


async def _user_card(user_doc: dict) -> str:
    uid = user_doc["telegram_id"]
    sites = await db.count_sites_by_owner(uid)
    views = await db.total_views(uid)
    uname = f"@{ui.esc(user_doc['username'])}" if user_doc.get("username") else "—"
    status = "🚫 BANNED" if user_doc.get("is_banned") else "🟢 Active"
    return (
        f"{ui.HEADER}\n{ui.LINE}\n👤 <b>User</b> <code>{uid}</code>\n"
        f"Username: {uname}\n"
        f"Plan: {ui.tier_badge(user_doc.get('tier', 'Free'))}\n"
        f"Status: {status}\n"
        f"Joined: {ui.fmt_dt(user_doc.get('joined_at'))}\n"
        f"Sites: <b>{sites}</b> · Views: <b>{views}</b>"
    )


async def _site_card(site: dict) -> str:
    owner = await db.get_user(site["owner_id"])
    oname = f"@{ui.esc(owner['username'])}" if owner and owner.get("username") else str(site["owner_id"])
    return ui.site_text(site) + f"\n👤 Owner: {oname} (<code>{site['owner_id']}</code>)\n🆔 <code>{site['site_id']}</code>"


async def _notify(bot: Bot, uid: int, text: str) -> None:
    try:
        await bot.send_message(uid, text)
    except Exception:
        log.debug("could not notify %s", uid)


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_admin_home_text(), reply_markup=ui.admin_menu_kb())


@router.callback_query(F.data == "adm")
async def cb_admin_home(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(cb, _admin_home_text(), ui.admin_menu_kb())
    await cb.answer()


@router.callback_query(F.data == "adm:dash")
async def cb_dashboard(cb: CallbackQuery) -> None:
    await cb.answer("⚡ Refreshing…")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Refresh", callback_data="adm:dash")
    kb.button(text="⬅️ Back", callback_data="adm")
    kb.adjust(2)
    await _edit(cb, await _dashboard_text(), kb.as_markup())


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@router.callback_query(F.data == "adm:users")
async def cb_users(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.user_search)
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n👥 <b>User Search</b>\nSend a Telegram <b>ID</b> or <b>@username</b>.",
        ui.back_kb("adm", "✖️ Cancel"),
    )
    await cb.answer()


@router.message(AdminStates.user_search, F.text)
async def on_user_search(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        await state.clear()
        return await cmd_admin(message, state) if message.text.startswith("/admin") else None
    results = await db.search_users(message.text)
    if not results:
        await message.answer(f"{ui.BADGE_ERR} No users found. Try again or /admin.")
        return
    await state.clear()
    if len(results) == 1:
        await message.answer(await _user_card(results[0]), reply_markup=ui.admin_user_kb(results[0]))
        return
    kb = InlineKeyboardBuilder()
    for u in results:
        label = f"@{u['username']}" if u.get("username") else str(u["telegram_id"])
        kb.button(text=f"{'🚫' if u.get('is_banned') else ' 👤'} {label} · {u.get('tier', 'Free')}",
                  callback_data=f"adm:u:{u['telegram_id']}")
    kb.button(text="⬅️ Back", callback_data="adm")
    kb.adjust(1)
    await message.answer(f"Found <b>{len(results)}</b> users:", reply_markup=kb.as_markup())


@router.callback_query(F.data.regexp(r"^adm:u:\d+$"))
async def cb_user_view(cb: CallbackQuery) -> None:
    user_doc = await db.get_user(int(cb.data.split(":")[2]))
    if not user_doc:
        await cb.answer("User not found.", show_alert=True)
        return
    await _edit(cb, await _user_card(user_doc), ui.admin_user_kb(user_doc))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:(ban|unban|vip|free):\d+$"))
async def cb_user_action(cb: CallbackQuery, bot: Bot) -> None:
    _, action, raw = cb.data.split(":")
    tid = int(raw)
    user_doc = await db.get_user(tid)
    if not user_doc:
        await cb.answer("User not found.", show_alert=True)
        return
    if action == "ban":
        if tid in config.ADMIN_IDS:
            await cb.answer("You can't ban an admin.", show_alert=True)
            return
        await db.set_banned(tid, True)
        await _notify(bot, tid, "🚫 <b>Your account has been banned.</b>")
        await cb.answer("🚫 User banned")
    elif action == "unban":
        await db.set_banned(tid, False)
        await _notify(bot, tid, "✅ <b>Your account has been restored.</b> Welcome back!")
        await cb.answer("✅ User unbanned")
    elif action == "vip":
        await db.set_tier(tid, "VIP")
        await _notify(bot, tid, f"👑 <b>You've been upgraded to VIP!</b>\n"
                                f"Enjoy up to {config.TIERS['VIP']['max_sites']} sites and custom domains.")
        await cb.answer("👑 Promoted to VIP")
    else:
        await db.set_tier(tid, "Free")
        await cb.answer("Demoted to Free")
    user_doc = await db.get_user(tid)
    await _edit(cb, await _user_card(user_doc), ui.admin_user_kb(user_doc))


@router.callback_query(F.data.regexp(r"^adm:usites:\d+$"))
async def cb_user_sites(cb: CallbackQuery) -> None:
    tid = int(cb.data.split(":")[2])
    sites = await db.list_sites_by_owner(tid, 0, SITES_PER_PAGE)
    if not sites:
        await cb.answer("This user has no sites.", show_alert=True)
        return
    await _edit(cb, f"{ui.HEADER}\n{ui.LINE}\n🌐 Sites of <code>{tid}</code> (latest {len(sites)}):",
                ui.admin_sites_kb(sites, 0, len(sites), SITES_PER_PAGE))
    await cb.answer()


# --------------------------------------------------------------------------- #
# Sites
# --------------------------------------------------------------------------- #
@router.callback_query(F.data.regexp(r"^adm:sites:\d+$"))
async def cb_sites(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    page = int(cb.data.split(":")[2])
    total = await db.count_sites()
    sites = await db.list_all_sites(skip=page * SITES_PER_PAGE, limit=SITES_PER_PAGE)
    if not sites and page > 0:
        page = 0
        sites = await db.list_all_sites(0, SITES_PER_PAGE)
    text = f"{ui.HEADER}\n{ui.LINE}\n🌐 <b>All Sites</b> — {total} total"
    await _edit(cb, text, ui.admin_sites_kb(sites, page, total, SITES_PER_PAGE))
    await cb.answer()


@router.callback_query(F.data == "adm:ssearch")
async def cb_site_search(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.site_search)
    await _edit(cb, f"{ui.HEADER}\n{ui.LINE}\n🔎 Send a <b>slug</b>, <b>name</b> or <b>site ID</b>.",
                ui.back_kb("adm:sites:0", "✖️ Cancel"))
    await cb.answer()


@router.message(AdminStates.site_search, F.text)
async def on_site_search(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        await state.clear()
        return await cmd_admin(message, state) if message.text.startswith("/admin") else None
    sites = await db.search_sites(message.text.strip().removeprefix("/s/").strip("/"), SITES_PER_PAGE)
    if not sites:
        await message.answer(f"{ui.BADGE_ERR} No matching sites. Try again or /admin.")
        return
    await state.clear()
    await message.answer(f"Found <b>{len(sites)}</b> site(s):",
                         reply_markup=ui.admin_sites_kb(sites, 0, len(sites), SITES_PER_PAGE))


@router.callback_query(F.data.regexp(r"^adm:s:[a-f0-9]{10}$"))
async def cb_site_view(cb: CallbackQuery) -> None:
    site = await db.get_site(cb.data.split(":")[2])
    if not site:
        await cb.answer("Site not found.", show_alert=True)
        return
    await _edit(cb, await _site_card(site), ui.admin_site_kb(site))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:(slock|sunlock):[a-f0-9]{10}$"))
async def cb_site_lock(cb: CallbackQuery, bot: Bot) -> None:
    _, action, sid = cb.data.split(":")
    site = await db.get_site(sid)
    if not site:
        await cb.answer("Site not found.", show_alert=True)
        return
    lock = action == "slock"
    await db.update_site(sid, {"is_locked": lock})
    site["is_locked"] = lock
    await _notify(
        bot, site["owner_id"],
        f"🔒 Your site <b>{ui.esc(site['site_name'])}</b> was locked by an administrator."
        if lock else f"🔓 Your site <b>{ui.esc(site['site_name'])}</b> is live again.",
    )
    await cb.answer("🔒 Site locked" if lock else "🔓 Site unlocked")
    await _edit(cb, await _site_card(site), ui.admin_site_kb(site))


@router.callback_query(F.data.regexp(r"^adm:sdel:[a-f0-9]{10}$"))
async def cb_site_delete(cb: CallbackQuery) -> None:
    sid = cb.data.split(":")[2]
    site = await db.get_site(sid)
    if not site:
        await cb.answer("Site not found.", show_alert=True)
        return
    await _edit(cb, f"⚠️ Permanently delete <b>{ui.esc(site['site_name'])}</b> "
                    f"(<code>/s/{ui.esc(site['slug'])}/</code>)?",
                ui.confirm_kb(f"adm:sdelok:{sid}", f"adm:s:{sid}"))
    await cb.answer()


@router.callback_query(F.data.regexp(r"^adm:sdelok:[a-f0-9]{10}$"))
async def cb_site_delete_ok(cb: CallbackQuery, bot: Bot) -> None:
    sid = cb.data.split(":")[2]
    site = await db.get_site(sid)
    if not site:
        await cb.answer("Already deleted.", show_alert=True)
        return
    await asyncio.to_thread(dep.remove_site_files, sid)
    await db.delete_site(sid)
    await _notify(bot, site["owner_id"],
                  f"🗑 Your site <b>{ui.esc(site['site_name'])}</b> was removed by an administrator.")
    await cb.answer("🗑 Deleted")
    total = await db.count_sites()
    sites = await db.list_all_sites(0, SITES_PER_PAGE)
    await _edit(cb, f"{ui.BADGE_OK} Site deleted.\n\n🌐 <b>All Sites</b> — {total} total",
                ui.admin_sites_kb(sites, 0, total, SITES_PER_PAGE))


# --------------------------------------------------------------------------- #
# Broadcast engine
# --------------------------------------------------------------------------- #
def _broadcast_confirm_kb(is_text: bool, has_caption: bool):
    b = InlineKeyboardBuilder()
    b.button(text="📤 Send as-is", callback_data="adm:bcgo:copy")
    if is_text or has_caption:
        b.button(text="🧩 Send as HTML", callback_data="adm:bcgo:html")
        b.button(text="📝 Send as Markdown", callback_data="adm:bcgo:md")
    b.button(text="✖️ Cancel", callback_data="adm")
    b.adjust(1)
    return b.as_markup()


@router.callback_query(F.data == "adm:bc")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast)
    total = await db.count_users({"is_banned": {"$ne": True}})
    await _edit(
        cb,
        f"{ui.HEADER}\n{ui.LINE}\n📣 <b>Global Broadcast</b> → <b>{total}</b> users\n\n"
        "Send the message to broadcast: text, photo, video, document, GIF…\n"
        "• Telegram formatting is preserved when sent <i>as-is</i>.\n"
        "• Or write raw <code>&lt;b&gt;HTML&lt;/b&gt;</code> / <code>*Markdown*</code> and pick the matching mode.",
        ui.back_kb("adm", "✖️ Cancel"),
    )
    await cb.answer()


@router.message(AdminStates.broadcast)
async def on_broadcast_content(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.startswith("/"):
        await state.clear()
        if message.text.startswith("/admin"):
            await cmd_admin(message, state)
        else:
            await message.answer(f"{ui.BADGE_OK} Broadcast cancelled.")
        return
    is_text = bool(message.text)
    raw = message.text if is_text else (message.caption or "")
    await state.update_data(src_chat=message.chat.id, src_mid=message.message_id,
                            is_text=is_text, raw=raw)
    total = await db.count_users({"is_banned": {"$ne": True}})
    await message.answer("👁 <b>Preview ↓</b>")
    try:
        await bot.copy_message(message.chat.id, message.chat.id, message.message_id)
    except Exception as exc:
        await message.answer(f"{ui.BADGE_ERR} This message type can't be broadcast: {ui.esc(exc)}")
        return
    await message.answer(
        f"{ui.BADGE_PROC} Ready to send to <b>{total}</b> users. Choose a mode:",
        reply_markup=_broadcast_confirm_kb(is_text, bool(raw) and not is_text),
    )


async def _deliver(bot: Bot, uid: int, data: dict, mode: str) -> None:
    """Deliver the stored broadcast message to one user in the chosen mode."""
    src_chat, src_mid = data["src_chat"], data["src_mid"]
    if mode in ("html", "md") and data.get("raw"):
        parse = ParseMode.HTML if mode == "html" else ParseMode.MARKDOWN
        if data["is_text"]:
            await bot.send_message(uid, data["raw"], parse_mode=parse)
        else:
            await bot.copy_message(uid, src_chat, src_mid, caption=data["raw"], parse_mode=parse)
        return
    await bot.copy_message(uid, src_chat, src_mid)


@router.callback_query(F.data.regexp(r"^adm:bcgo:(copy|html|md)$"))
async def cb_broadcast_go(cb: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    mode = cb.data.split(":")[2]
    data = await state.get_data()
    if "src_mid" not in data:
        await cb.answer("Nothing to broadcast. Start again.", show_alert=True)
        return
    await state.clear()

    # Self-test on the admin first: catches HTML/Markdown syntax errors before mass-sending.
    try:
        await _deliver(bot, cb.from_user.id, data, mode)
    except TelegramBadRequest as exc:
        await cb.answer()
        await _edit(cb, f"{ui.BADGE_ERR} Telegram rejected the message in <b>{mode.upper()}</b> mode:\n"
                        f"<code>{ui.esc(exc)}</code>\n\nFix the markup and start again.",
                    ui.back_kb("adm:bc", "🔁 Retry"))
        return

    await cb.answer("🚀 Broadcast started")
    await _edit(cb, f"{ui.BADGE_PROC} Preparing broadcast…")
    status_chat = cb.from_user.id
    status_mid = cb.message.message_id if isinstance(cb.message, Message) else None
    task = asyncio.create_task(_run_broadcast(bot, data, mode, status_chat, status_mid))
    _background.add(task)
    task.add_done_callback(_background.discard)


def _broadcast_text(done: int, total: int, sent: int, blocked: int, failed: int, finished: bool) -> str:
    pct = (done / total * 100) if total else 100.0
    badge = ui.BADGE_OK if finished else ui.BADGE_PROC
    title = "BRΘΛDᄃΛST ᄃΘMPLΞƬΞ" if finished else "BRΘΛDᄃΛSƬING"
    return (
        f"✨ <b>{title}</b> ✨\n{ui.LINE}\n"
        f"{badge} {ui.progress_bar(pct, 14)} <b>{pct:.0f}%</b>\n"
        f"📨 Processed: <b>{done}/{total}</b>\n"
        f"✅ Delivered: <b>{sent}</b>\n"
        f"🚫 Blocked/left: <b>{blocked}</b>\n"
        f"⚠️ Failed: <b>{failed}</b>"
    )


async def _run_broadcast(bot: Bot, data: dict, mode: str, admin_id: int,
                         status_mid: Optional[int]) -> None:
    """Send to every non-banned user, throttled, with a live progress badge."""
    ids = [uid async for uid in db.iter_user_ids()]
    total = len(ids)
    sent = blocked = failed = 0

    async def refresh(done: int, finished: bool = False) -> None:
        text = _broadcast_text(done, total, sent, blocked, failed, finished)
        try:
            if status_mid is not None:
                await bot.edit_message_text(text, chat_id=admin_id, message_id=status_mid)
            else:
                await bot.send_message(admin_id, text)
        except TelegramBadRequest:
            pass   # "message is not modified" etc.
        except Exception:
            log.debug("progress update failed")

    last_edit = 0.0
    await refresh(0)
    for done, uid in enumerate(ids, start=1):
        try:
            await _deliver(bot, uid, data, mode)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            try:
                await _deliver(bot, uid, data, mode)
                sent += 1
            except Exception:
                failed += 1
        except TelegramForbiddenError:
            blocked += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)   # ~20 msg/s, below Telegram's 30 msg/s limit
        now = time.monotonic()
        if now - last_edit >= 2.0 and done < total:
            last_edit = now
            await refresh(done)
    await refresh(total, finished=True)


# --------------------------------------------------------------------------- #
# Guard for non-admins
# --------------------------------------------------------------------------- #
@guard_router.callback_query(F.data.startswith("adm"))
async def deny_non_admin(cb: CallbackQuery) -> None:
    await cb.answer("⛔ Admins only.", show_alert=True)