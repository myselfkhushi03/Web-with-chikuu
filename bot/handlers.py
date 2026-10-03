import io
import zipfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config import ADMIN_ID, DEFAULT_FILES, MAX_PROJECTS_FREE, WEBHOOK_URL
from bot.database import (
    create_user, get_user, create_project, get_project,
    get_user_projects, update_project, delete_project, get_stats
)
from bot.filemanager import (
    add_or_update_file, delete_file as fm_delete_file,
    rename_file as fm_rename_file, find_file
)
from bot.templates import get_template, list_templates
from bot.keyboards import (
    main_menu, project_menu, confirm_delete, file_actions,
    projects_list, files_list, templates_kb
)
from bot.utils import esc, human_size

USER_STATE = {}


# ---------------- START / HELP ----------------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await create_user(u.id, u.username, u.first_name)
    text = (
        f"👋 *Welcome {esc(u.first_name)}*\n\n"
        "🚀 *WebBuilder Bot* — apni website banao, edit karo, deploy karo, sab Telegram se\\!\n\n"
        "*Quick Start:*\n"
        "• /newproject \\<name\\> \\<type\\>\n"
        "• /myprojects\n"
        "• /templates\n"
        "• /help\n\n"
        "Ya niche buttons use karo 👇"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu())


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Commands Guide*\n\n"
        "*Project*\n"
        "`/newproject <name> <type>` \\- naya project\n"
        "`/myprojects` \\- projects list\n"
        "`/openproject <id>` \\- project kholo\n"
        "`/deleteproject <id>` \\- delete\n"
        "`/renameproject <id> <new>` \\- rename\n"
        "`/cloneproject <id>` \\- duplicate\n\n"
        "*Files*\n"
        "`/addfile <id> <file>` \\- file add\n"
        "`/editfile <id> <file>` \\- edit\n"
        "`/deletefile <id> <file>` \\- delete\n"
        "`/listfiles <id>` \\- list\n"
        "`/viewfile <id> <file>` \\- view\n"
        "`/renamefile <id> <old> <new>` \\- rename\n\n"
        "*Preview & Deploy*\n"
        "`/preview <id>` \\- live preview\n"
        "`/deploy <id>` \\- deploy URL\n"
        "`/exportzip <id>` \\- ZIP download\n\n"
        "*Other*\n"
        "`/templates` \\- ready templates\n"
        "`/storage` \\- usage\n"
        "`/status` \\- bot status"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)


# ---------------- PROJECTS ----------------

async def newproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = await get_user(u.id) or await create_user(u.id, u.username, u.first_name)
    if len(user.get("projects", [])) >= MAX_PROJECTS_FREE and not user.get("is_premium"):
        await update.message.reply_text(
            f"⚠️ Free limit: {MAX_PROJECTS_FREE} projects.\nDelete karo ya /premium lo."
        )
        return

    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: `/newproject <name> <type>`\nTypes: portfolio, blog, landing, ecommerce, admin, custom",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    ptype = args[-1].lower()
    name = " ".join(args[:-1])

    tpl = get_template(ptype) if ptype in list_templates() else None
    files = tpl if tpl else DEFAULT_FILES

    proj = await create_project(u.id, name, ptype, files)
    await update.message.reply_text(
        f"✅ Project ban gaya\\!\n\n"
        f"🆔 `{esc(proj['project_id'])}`\n"
        f"📛 {esc(name)}\n"
        f"🎨 {esc(ptype)}\n\n"
        f"Files: {len(files)}",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=project_menu(proj["project_id"])
    )


async def myprojects(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    projects = await get_user_projects(u.id)
    if not projects:
        await update.message.reply_text(
            "📭 Koi project nahi\\.\n`/newproject <name> <type>`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    await update.message.reply_text(
        f"📁 *Your Projects* \\({len(projects)}\\)",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=projects_list(projects)
    )


async def openproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/openproject <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    await update.message.reply_text(
        f"📁 *{esc(p['name'])}*\n🆔 `{esc(pid)}`\n📄 {len(p['files'])} files\n👁 {p.get('views', 0)} views",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=project_menu(pid)
    )


async def deleteproject_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/deleteproject <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    await update.message.reply_text(
        f"⚠️ Delete *{esc(p['name'])}*?",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=confirm_delete(pid)
    )


async def renameproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/renameproject <id> <new name>`",
                                        parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    new_name = " ".join(ctx.args[1:])
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    await update_project(pid, {"name": new_name})
    await update.message.reply_text(f"✅ Renamed to *{esc(new_name)}*", parse_mode=ParseMode.MARKDOWN_V2)


async def cloneproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/cloneproject <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = {f["name"]: f["content"] for f in p["files"]}
    new_p = await create_project(update.effective_user.id, p["name"] + " (copy)", p["type"], files)
    await update.message.reply_text(
        f"✅ Cloned as `{esc(new_p['project_id'])}`",
        parse_mode=ParseMode.MARKDOWN_V2
    )


# ---------------- FILES ----------------

async def listfiles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/listfiles <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    await update.message.reply_text(
        f"📄 *Files in {esc(p['name'])}*",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=files_list(pid, p["files"])
    )


async def addfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/addfile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid, fname = ctx.args[0], ctx.args[1]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    USER_STATE[update.effective_user.id] = {"action": "addfile", "pid": pid, "fname": fname}
    await update.message.reply_text(
        f"✏️ Ab content bhejo `{esc(fname)}` ke liye \\(text ya file\\).",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def editfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/editfile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid, fname = ctx.args[0], ctx.args[1]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    USER_STATE[update.effective_user.id] = {"action": "editfile", "pid": pid, "fname": fname}
    await update.message.reply_text(
        f"✏️ Naya content bhejo `{esc(fname)}` ke liye\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def deletefile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/deletefile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid, fname = ctx.args[0], ctx.args[1]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = fm_delete_file(p, fname)
    await update_project(pid, {"files": files})
    await update.message.reply_text(f"✅ `{esc(fname)}` deleted.", parse_mode=ParseMode.MARKDOWN_V2)


async def renamefile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 3:
        await update.message.reply_text("Usage: `/renamefile <id> <old> <new>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid, old, new = ctx.args[0], ctx.args[1], ctx.args[2]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = fm_rename_file(p, old, new)
    await update_project(pid, {"files": files})
    await update.message.reply_text(
        f"✅ Renamed `{esc(old)}` → `{esc(new)}`",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def viewfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/viewfile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid, fname = ctx.args[0], ctx.args[1]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    f = find_file(p, fname)
    if not f:
        await update.message.reply_text("❌ File not found.")
        return
    content = f["content"]
    if len(content) > 3500:
        buf = io.BytesIO(content.encode())
        buf.name = fname
        await update.message.reply_document(document=buf, filename=fname)
    else:
        await update.message.reply_text(f"```\n{content[:3500]}\n```", parse_mode=ParseMode.MARKDOWN_V2)
        # ---------------- PREVIEW / DEPLOY ----------------

async def preview(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/preview <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p:
        await update.message.reply_text("❌ Not found.")
        return
    url = f"{WEBHOOK_URL}/preview/{pid}"
    await update.message.reply_text(
        f"👁 *Live Preview:*\n{url}",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Open Preview", url=url)
        ]])
    )


async def deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/deploy <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    url = f"{WEBHOOK_URL}/s/{pid}"
    await update_project(pid, {"deploy_url": url, "is_public": True})
    await update.message.reply_text(
        f"🚀 *Deployed\\!*\n\n🌐 {url}",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Visit Site", url=url)
        ]])
    )


async def exportzip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/exportzip <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0]
    p = await get_project(pid)
    if not p or p["owner_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in p["files"]:
            z.writestr(f["name"], f["content"])
    buf.seek(0)
    buf.name = f"{pid}.zip"
    await update.message.reply_document(document=buf, filename=f"{pid}.zip")


# ---------------- MISC ----------------

async def templates_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎨 *Templates* \\- ek choose karo:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=templates_kb()
    )


async def storage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = await get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Pehle /start karo.")
        return
    used = u.get("storage_used", 0)
    mb = used / (1024 * 1024)
    await update.message.reply_text(
        f"💾 *Storage*\n\nUsed: {mb:.2f} MB\nProjects: {len(u.get('projects', []))}",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = await get_stats()
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n👥 Users: {s['users']}\n📁 Projects: {s['projects']}\n✅ Online",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    s = await get_stats()
    await update.message.reply_text(f"🔐 Admin\nUsers: {s['users']}\nProjects: {s['projects']}")


# ---------------- MESSAGE HANDLER ----------------

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    state = USER_STATE.get(u.id)
    if not state:
        return

    action = state.get("action")

    # Rename project
    if action == "renameproject" and update.message.text:
        new_name = update.message.text.strip()
        p = await get_project(state["pid"])
        if p and p["owner_id"] == u.id:
            await update_project(state["pid"], {"name": new_name})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(
            f"✅ Renamed to `{esc(new_name)}`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # Rename file
    if action == "renamefile" and update.message.text:
        new_name = update.message.text.strip()
        p = await get_project(state["pid"])
        if p and p["owner_id"] == u.id:
            files = fm_rename_file(p, state["fname"], new_name)
            await update_project(state["pid"], {"files": files})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(
            f"✅ Renamed to `{esc(new_name)}`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # Ask for filename (add file)
    if action == "askfilename" and update.message.text:
        fname = update.message.text.strip()
        USER_STATE[u.id] = {"action": "addfile", "pid": state["pid"], "fname": fname}
        await update.message.reply_text(
            f"✏️ Ab content bhejo `{esc(fname)}` ke liye:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # Add / Edit file content
    if action in ("addfile", "editfile"):
        pid = state["pid"]
        fname = state["fname"]

        content = None
        if update.message.document:
            file = await update.message.document.get_file()
            data = await file.download_as_bytearray()
            content = data.decode("utf-8", errors="ignore")
        elif update.message.text:
            content = update.message.text

        if not content:
            return

        p = await get_project(pid)
        if not p or p["owner_id"] != u.id:
            await update.message.reply_text("❌ Project not found.")
            USER_STATE.pop(u.id, None)
            return

        files = add_or_update_file(p, fname, content)
        await update_project(pid, {"files": files})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(
            f"✅ `{esc(fname)}` saved\\! \\({len(content)} bytes\\)",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=project_menu(pid)
        )
        return


# ---------------- CALLBACK HANDLER ----------------

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    u = q.from_user

    # --- Static menus ---
    if data == "menu_back":
        await q.edit_message_text("🏠 Main Menu", reply_markup=main_menu())
        return

    if data == "menu_new":
        await q.edit_message_text(
            "🚀 Use: `/newproject <name> <type>`\nTypes: portfolio, blog, landing, ecommerce, admin, custom",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    if data == "menu_list":
        projects = await get_user_projects(u.id)
        if not projects:
            await q.edit_message_text("📭 No projects yet.")
            return
        await q.edit_message_text(
            f"📁 *Your Projects* \\({len(projects)}\\)",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=projects_list(projects)
        )
        return

    if data == "menu_templates":
        await q.edit_message_text("🎨 Templates:", reply_markup=templates_kb())
        return

    if data == "menu_storage":
        user = await get_user(u.id)
        used = user.get("storage_used", 0) / (1024 * 1024)
        await q.edit_message_text(
            f"💾 Used: {used:.2f} MB\n📁 Projects: {len(user.get('projects', []))}"
        )
        return

    if data == "menu_help":
        await q.edit_message_text("📖 Type /help for full command list.")
        return

    # --- Project open ---
    if data.startswith("open_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p or p["owner_id"] != u.id:
            await q.edit_message_text("❌ Not found.")
            return
        await q.edit_message_text(
            f"📁 *{esc(p['name'])}*\n🆔 `{esc(pid)}`\n📄 {len(p['files'])} files",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=project_menu(pid)
        )
        return

    # --- Delete project ---
    if data.startswith("delp_"):
        pid = data.split("_", 1)[1]
        await q.edit_message_text(
            f"⚠️ Confirm delete `{esc(pid)}`?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=confirm_delete(pid)
        )
        return

    if data.startswith("confdel_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if p and p["owner_id"] == u.id:
            await delete_project(pid)
        await q.edit_message_text("🗑 Deleted.")
        return

    # --- Files list ---
    if data.startswith("files_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p:
            return
        await q.edit_message_text(
            f"📄 Files in *{esc(p['name'])}*",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=files_list(pid, p["files"])
        )
        return

    # --- Single file actions ---
    if data.startswith("file_"):
        _, pid, fname = data.split("_", 2)
        await q.edit_message_text(
            f"📄 `{esc(fname)}`\n\nChoose action:",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=file_actions(pid, fname)
        )
        return

    if data.startswith("view_"):
        _, pid, fname = data.split("_", 2)
        p = await get_project(pid)
        f = find_file(p, fname) if p else None
        if not f:
            await q.edit_message_text("❌ Not found.")
            return
        content = f["content"]
        txt = f"```\n{content[:3000]}\n```" if len(content) <= 3000 else "File too big, use /viewfile"
        try:
            await q.edit_message_text(
                txt,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=file_actions(pid, fname)
            )
        except Exception:
            await q.edit_message_text("⚠️ Content contains special chars. Use /viewfile.")
        return

    if data.startswith("dl_"):
        _, pid, fname = data.split("_", 2)
        p = await get_project(pid)
        f = find_file(p, fname) if p else None
        if not f:
            return
        buf = io.BytesIO(f["content"].encode())
        buf.name = fname
        await q.message.reply_document(document=buf, filename=fname)
        return

    if data.startswith("delf_"):
        _, pid, fname = data.split("_", 2)
        p = await get_project(pid)
        if not p or p["owner_id"] != u.id:
            return
        files = fm_delete_file(p, fname)
        await update_project(pid, {"files": files})
        await q.edit_message_text(
            f"🗑 `{esc(fname)}` deleted.",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=files_list(pid, files)
        )
        return

    if data.startswith("ren_"):
        _, pid, fname = data.split("_", 2)
        USER_STATE[u.id] = {"action": "renamefile", "pid": pid, "fname": fname}
        await q.edit_message_text(
            f"📝 Naya naam bhejo `{esc(fname)}` ke liye:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    if data.startswith("edit_"):
        _, pid, fname = data.split("_", 2)
        USER_STATE[u.id] = {"action": "editfile", "pid": pid, "fname": fname}
        await q.edit_message_text(
            f"✏️ Naya content bhejo `{esc(fname)}` ke liye:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    if data.startswith("addf_"):
        pid = data.split("_", 1)[1]
        USER_STATE[u.id] = {"action": "askfilename", "pid": pid}
        await q.edit_message_text(
            "➕ Naya file ka naam bhejo \\(e\\.g\\. about\\.html\\):",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    # --- Preview / Deploy ---
    if data.startswith("prev_"):
        pid = data.split("_", 1)[1]
        url = f"{WEBHOOK_URL}/preview/{pid}"
        await q.edit_message_text(
            f"👁 Preview: {url}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Open", url=url)],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"open_{pid}")]
            ])
        )
        return

    if data.startswith("deploy_"):
        pid = data.split("_", 1)[1]
        url = f"{WEBHOOK_URL}/s/{pid}"
        await update_project(pid, {"deploy_url": url, "is_public": True})
        await q.edit_message_text(
            f"🚀 Deployed\\!\n🌐 {url}",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Visit", url=url)],
                [InlineKeyboardButton("⬅️ Back", callback_data=f"open_{pid}")]
            ])
        )
        return

    # --- ZIP download ---
    if data.startswith("zip_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p or p["owner_id"] != u.id:
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in p["files"]:
                z.writestr(f["name"], f["content"])
        buf.seek(0)
        buf.name = f"{pid}.zip"
        await q.message.reply_document(document=buf, filename=f"{pid}.zip")
        return

    # --- Rename project ---
    if data.startswith("renp_"):
        pid = data.split("_", 1)[1]
        USER_STATE[u.id] = {"action": "renameproject", "pid": pid}
        await q.edit_message_text("✏️ Naya project naam bhejo:", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # --- Template choose ---
    if data.startswith("tpl_"):
        tpl = data.split("_", 1)[1]
        await q.edit_message_text(
            f"🎨 Template *{esc(tpl)}* use karne ke liye:\n"
            f"`/newproject <name> {tpl}`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
