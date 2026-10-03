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
    if not ctx.args
