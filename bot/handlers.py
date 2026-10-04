import io
import zipfile
import mimetypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.config import ADMIN_ID, DEFAULT_FILES, MAX_PROJECTS_FREE, WEBHOOK_URL, MAX_FILE_SIZE
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

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        await create_user(u.id, u.username, u.first_name)
    except Exception as e:
        print(f"DB error in start: {e}")
    welcome_text = (
        f"👋 *Welcome {esc(u.first_name)} to WebBuilder Bot*\\!\n\n"
        "🚀 Build, edit, deploy websites directly from Telegram\\.\n\n"
        "🔥 *Features:*\n"
        "• Create unlimited websites \\(free: 5\\)\n"
        "• Edit HTML, CSS, JS files\n"
        "• Live preview & deploy\n"
        "• Export as ZIP\n"
        "• Custom templates\n\n"
        "*Quick Start:*\n"
        "• /newproject \\<name\\> \\<type\\> — create new\n"
        "• /myprojects — your projects\n"
        "• /templates — ready designs\n"
        "• /help — all commands\n\n"
        "Select from menu below 👇"
    )
    try:
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu())
    except Exception as e:
        print(f"Markdown fail start: {e}")
        await update.message.reply_text(f"Welcome {u.first_name}! WebBuilder Bot is online.\nUse /help for commands.", reply_markup=main_menu())

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *WebBuilder Bot — Full Commands Guide*\n\n"
        "*🏗️ Project Management*\n"
        "`/newproject <name> <type>` — create new project\n"
        " Types: portfolio, blog, landing, ecommerce, admin, custom\n"
        "`/myprojects` — list all your projects\n"
        "`/openproject <id>` — open project details\n"
        "`/deleteproject <id>` — delete project\n"
        "`/renameproject <id> <new name>` — rename\n"
        "`/cloneproject <id>` — duplicate project\n\n"
        "*📄 File Management*\n"
        "`/addfile <id> <filename>` — add new file\n"
        "`/editfile <id> <filename>` — edit file content\n"
        "`/deletefile <id> <filename>` — delete file\n"
        "`/listfiles <id>` — list all files\n"
        "`/viewfile <id> <filename>` — view content\n"
        "`/renamefile <id> <old> <new>` — rename file\n\n"
        "*🌐 Preview & Deploy*\n"
        "`/preview <id>` — live preview link\n"
        "`/deploy <id>` — get deployable link\n"
        "`/exportzip <id>` — download as ZIP\n\n"
        "*🎨 Templates & Utils*\n"
        "`/templates` — browse templates\n"
        "`/storage` — check storage usage\n"
        "`/status` — bot status\n"
        "`/help` — this message\n\n"
        "💡 *Tip:* You can also use buttons — much easier\\!"
    )
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        await update.message.reply_text(help_text.replace("\\", ""))

async def newproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        user = await get_user(u.id)
        if not user:
            user = await create_user(u.id, u.username, u.first_name)
    except Exception:
        user = {"projects": [], "is_premium": False}
    projects_count = len(user.get("projects", []))
    if projects_count >= MAX_PROJECTS_FREE and not user.get("is_premium", False):
        await update.message.reply_text(
            f"⚠️ *Free limit reached:* {MAX_PROJECTS_FREE} projects\\.\n"
            f"You have {projects_count} projects\\.\n"
            f"Delete one or upgrade to premium\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    args = ctx.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ *Usage:* `/newproject <name> <type>`\n\n"
            "*Examples:*\n"
            "`/newproject MyPortfolio portfolio`\n"
            "`/newproject MyBlog blog`\n"
            "`/newproject LandingPage landing`\n\n"
            "*Available types:*\n"
            f"{', '.join(list_templates())}, custom",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    ptype = args[-1].lower()
    name = " ".join(args[:-1])
    if len(name) < 2:
        await update.message.reply_text("❌ Name too short. Min 2 chars.")
        return
    if len(name) > 50:
        await update.message.reply_text("❌ Name too long. Max 50 chars.")
        return
    if ptype in list_templates():
        tpl_files = get_template(ptype)
        files_dict = tpl_files
    else:
        files_dict = DEFAULT_FILES
    try:
        proj = await create_project(u.id, name, ptype, files_dict)
    except Exception as e:
        print(f"create_project error: {e}")
        await update.message.reply_text("❌ DB error. Try again.")
        return
    success_text = (
        f"✅ *Project Created Successfully\\!*\n\n"
        f"📛 *Name:* {esc(name)}\n"
        f"🆔 *ID:* `{esc(proj['project_id'])}`\n"
        f"🎨 *Type:* {esc(ptype)}\n"
        f"📄 *Files:* {len(files_dict)}\n\n"
        f"Use buttons below to manage 👇"
    )
    await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(proj["project_id"]))

async def myprojects(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    try:
        projects = await get_user_projects(u.id)
    except Exception as e:
        print(f"myprojects error: {e}")
        await update.message.reply_text("❌ DB error. Try /start again.")
        return
    if not projects:
        await update.message.reply_text(
            "📭 *No projects yet\\.*\n\n"
            "Create one with:\n"
            "`/newproject <name> <type>`\n\n"
            "Example: `/newproject MySite portfolio`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    await update.message.reply_text(
        f"📁 *Your Projects* \\({len(projects)}\\)\n\nSelect to open:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=projects_list(projects)
    )

async def openproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/openproject <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p:
        await update.message.reply_text("❌ Project not found. Check ID with /myprojects")
        return
    if p["owner_id"]!= update.effective_user.id and update.effective_user.id!= ADMIN_ID:
        await update.message.reply_text("❌ Not your project.")
        return
    info = (
        f"📁 *{esc(p['name'])}*\n\n"
        f"🆔 `{esc(p['project_id'])}`\n"
        f"🎨 Type: {esc(p['type'])}\n"
        f"📄 Files: {len(p['files'])}\n"
        f"👁 Views: {p.get('views', 0)}\n"
        f"📅 Created: {p.get('created_at', '')}\n"
        f"🌐 Public: {'Yes' if p.get('is_public') else 'No'}\n"
    )
    await update.message.reply_text(info, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(pid))

async def deleteproject_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/deleteproject <project_id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found or not yours.")
        return
    await update.message.reply_text(
        f"⚠️ *Are you sure to delete?*\n\n"
        f"📁 *{esc(p['name'])}*\n"
        f"🆔 `{esc(pid)}`\n\n"
        f"This cannot be undone\\!",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=confirm_delete(pid)
    )

async def renameproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/renameproject <id> <new name>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    new_name = " ".join(ctx.args[1:])
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    await update_project(pid, {"name": new_name})
    await update.message.reply_text(f"✅ Renamed to *{esc(new_name)}*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(pid))

async def cloneproject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/cloneproject <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = {f["name"]: f["content"] for f in p["files"]}
    new_p = await create_project(update.effective_user.id, p["name"] + " (copy)", p["type"], files)
    await update.message.reply_text(
        f"✅ *Cloned\\!*\nNew ID: `{esc(new_p['project_id'])}`",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=project_menu(new_p["project_id"])
    )

async def listfiles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/listfiles <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    file_list_text = f"📄 *Files in {esc(p['name'])} \\({len(p['files'])}\\)*\n\n"
    for f in p["files"]:
        file_list_text += f"• {esc(f['name'])} — {human_size(f['size'])}\n"
    await update.message.reply_text(file_list_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=files_list(pid, p["files"]))

async def addfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/addfile <id> <filename>`\nExample: `/addfile WEB-ABC123 about.html`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    fname = ctx.args[1].strip()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    USER_STATE[update.effective_user.id] = {"action": "addfile", "pid": pid, "fname": fname}
    await update.message.reply_text(
        f"✏️ *Send content for:* `{esc(fname)}`\n\n"
        f"You can send text or upload a file\\.\n"
        f"Project: {esc(p['name'])}",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def editfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/editfile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    fname = ctx.args[1].strip()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    f = find_file(p, fname)
    if not f:
    f = find_file(p, fname)
    if not f:
        await update.message.reply_text("❌ File not found in project.")
        return
    USER_STATE[update.effective_user.id] = {"action": "editfile", "pid": pid, "fname": fname}
    await update.message.reply_text(
        f"✏️ *Editing:* `{esc(fname)}`\n"
        f"Current size: {human_size(f['size'])}\n\n"
        f"Send new content now:",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def deletefile_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Usage: `/deletefile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    fname = ctx.args[1].strip()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = fm_delete_file(p, fname)
    await update_project(pid, {"files": files})
    await update.message.reply_text(f"🗑 ✅ `{esc(fname)}` deleted from {esc(p['name'])}", parse_mode=ParseMode.MARKDOWN_V2)

async def renamefile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 3:
        await update.message.reply_text("Usage: `/renamefile <id> <old> <new>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    old = ctx.args[1].strip()
    new = ctx.args[2].strip()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    files = fm_rename_file(p, old, new)
    await update_project(pid, {"files": files})
    await update.message.reply_text(f"✅ Renamed `{esc(old)}` → `{esc(new)}`", parse_mode=ParseMode.MARKDOWN_V2)

async def viewfile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/viewfile <id> <filename>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    fname = ctx.args[1].strip()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    f = find_file(p, fname)
    if not f:
        await update.message.reply_text("❌ File not found.")
        return
    content = f["content"]
    size = f["size"]
    if len(content) > 3500:
        buf = io.BytesIO(content.encode())
        buf.name = fname
        await update.message.reply_document(
            document=buf,
            filename=fname,
            caption=f"📄 {fname} ({human_size(size)}) — too long, sent as file"
        )
    else:
        # FIXED: No MarkdownV2 with code blocks — Telegram was crashing here
        try:
            await update.message.reply_text(content[:4000])
        except Exception:
            buf = io.BytesIO(content.encode())
            buf.name = fname
            await update.message.reply_document(document=buf, filename=fname)

async def preview(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/preview <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p:
        await update.message.reply_text("❌ Project not found.")
        return
    url = f"{WEBHOOK_URL}/preview/{pid}"
    text = (
        f"👁 *Live Preview Ready\\!*\n\n"
        f"📁 {esc(p['name'])}\n"
        f"🆔 `{esc(pid)}`\n\n"
        f"🔗 *Preview URL:*\n{esc(url)}\n\n"
        f"Anyone with link can view\\."
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Open Preview", url=url)]])
    )

async def deploy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/deploy <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    url = f"{WEBHOOK_URL}/s/{pid}"
    await update_project(pid, {"deploy_url": url, "is_public": True})
    text = (
        f"🚀 *Deployed Successfully\\!*\n\n"
        f"📁 {esc(p['name'])}\n"
        f"🌐 *Live URL:*\n{esc(url)}\n\n"
        f"Share this link — permanent\\!"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Visit Site", url=url)]])
    )

async def exportzip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/exportzip <id>`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    pid = ctx.args[0].strip().upper()
    p = await get_project(pid)
    if not p or p["owner_id"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not found.")
        return
    buf = io.BytesIO()
    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in p["files"]:
                z.writestr(f["name"], f["content"])
        buf.seek(0)
        buf.name = f"{p['name']}_{pid}.zip"
        await update.message.reply_document(
            document=buf,
            filename=f"{p['name']}_{pid}.zip",
            caption=f"📦 ZIP for {p['name']} ({len(p['files'])} files)"
        )
    except Exception as e:
        print(f"zip error: {e}")
        await update.message.reply_text("❌ ZIP export failed.")

async def templates_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tpl_list = list_templates()
    text = f"🎨 *Available Templates* \\({len(tpl_list)}\\)\n\n" + "\n".join([f"• {esc(t)}" for t in tpl_list])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=templates_kb())

async def storage(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = await get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Please /start first.")
        return
    used = u.get("storage_used", 0)
    used_mb = used / (1024 * 1024)
    limit_mb = 50.0 if not u.get("is_premium") else 500.0
    percent = (used_mb / limit_mb * 100) if limit_mb > 0 else 0
    text = (
        f"💾 *Storage Usage*\n\n"
        f"Used: {used_mb:.2f} MB / {limit_mb:.0f} MB\n"
        f"Progress: {percent:.1f}%\n"
        f"Projects: {len(u.get('projects', []))} / {MAX_PROJECTS_FREE}\n"
        f"Premium: {'Yes ✅' if u.get('is_premium') else 'No'}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        s = await get_stats()
    except Exception:
        s = {"users": 0, "projects": 0}
    text = (
        f"📊 *Bot Status*\n\n"
        f"👥 Total Users: {s['users']}\n"
        f"📁 Total Projects: {s['projects']}\n"
        f"✅ Status: Online\n"
        f"🌐 URL: {WEBHOOK_URL}\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!= ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    s = await get_stats()
    await update.message.reply_text(f"🔐 *Admin Panel*\n\nUsers: {s['users']}\nProjects: {s['projects']}", parse_mode=ParseMode.MARKDOWN_V2)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    state = USER_STATE.get(u.id)
    if not state:
        return
    action = state.get("action")
    if action == "renameproject" and update.message.text:
        new_name = update.message.text.strip()
        if len(new_name) < 2:
            await update.message.reply_text("❌ Name too short.")
            return
        p = await get_project(state["pid"])
        if p and p["owner_id"] == u.id:
            await update_project(state["pid"], {"name": new_name})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(f"✅ Project renamed to `{esc(new_name)}`", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(state["pid"]))
        return
    if action == "renamefile" and update.message.text:
        new_name = update.message.text.strip()
        p = await get_project(state["pid"])
        if p and p["owner_id"] == u.id:
            files = fm_rename_file(p, state["fname"], new_name)
            await update_project(state["pid"], {"files": files})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(f"✅ File renamed to `{esc(new_name)}`", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(state["pid"]))
        return
    if action == "askfilename" and update.message.text:
        fname = update.message.text.strip()
        if "." not in fname:
            await update.message.reply_text("❌ Add extension e.g. about.html")
            return
        USER_STATE[u.id] = {"action": "addfile", "pid": state["pid"], "fname": fname}
        await update.message.reply_text(f"✏️ Now send content for `{esc(fname)}`:", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if action in ("addfile", "editfile"):
        pid = state["pid"]
        fname = state["fname"]
        content = None
        if update.message.document:
            if update.message.document.file_size > MAX_FILE_SIZE:
                await update.message.reply_text(f"❌ File too big. Max {human_size(MAX_FILE_SIZE)}")
                return
            file = await update.message.document.get_file()
            data = await file.download_as_bytearray()
            try:
                content = data.decode("utf-8", errors="ignore")
            except Exception:
                await update.message.reply_text("❌ Binary files not supported. Send text.")
                return
        elif update.message.text:
            content = update.message.text
        if not content:
            return
        p = await get_project(pid)
        if not p or p["owner_id"]!= u.id:
            await update.message.reply_text("❌ Project not found.")
            USER_STATE.pop(u.id, None)
            return
        files = add_or_update_file(p, fname, content)
        await update_project(pid, {"files": files})
        USER_STATE.pop(u.id, None)
        await update.message.reply_text(f"✅ `{esc(fname)}` saved\\! \\({len(content)} bytes\\)", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(pid))
        return

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass
    data = q.data
    u = q.from_user
    if data == "menu_back":
        await q.edit_message_text("🏠 *Main Menu*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu())
        return
    if data == "menu_new":
        await q.edit_message_text("🚀 *Create New Project*\n\nUse:\n`/newproject <name> <type>`\n\nTypes: portfolio, blog, landing, ecommerce, admin, custom", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data == "menu_list":
        projects = await get_user_projects(u.id)
        if not projects:
            await q.edit_message_text("📭 No projects yet.\nUse /newproject")
            return
        await q.edit_message_text(f"📁 *Your Projects* \\({len(projects)}\\)", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=projects_list(projects))
        return
    if data == "menu_templates":
        await q.edit_message_text("🎨 *Choose Template*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=templates_kb())
        return
    if data == "menu_storage":
        user = await get_user(u.id)
        if not user:
            await q.edit_message_text("Please /start first.")
            return
        used = user.get("storage_used", 0) / (1024 * 1024)
        await q.edit_message_text(f"💾 *Storage*\n\nUsed: {used:.2f} MB\nProjects: {len(user.get('projects', []))}", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data == "menu_help":
        await q.edit_message_text("📖 Use /help for full command list.")
        return
    if data.startswith("open_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p or p["owner_id"]!= u.id:
            await q.edit_message_text("❌ Not found or not yours.")
            return
        info = f"📁 *{esc(p['name'])}*\n🆔 `{esc(pid)}`\n📄 Files: {len(p['files'])}\n👁 Views: {p.get('views',0)}"
        await q.edit_message_text(info, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=project_menu(pid))
        return
    if data.startswith("delp_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p:
            await q.edit_message_text("❌ Not found.")
            return
        await q.edit_message_text(f"⚠️ *Confirm Delete?*\n\n{esc(p['name'])} \\(`{esc(pid)}`\\)\n\nThis cannot be undone\\!", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=confirm_delete(pid))
        return
    if data.startswith("confdel_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if p and p["owner_id"] == u.id:
            await delete_project(pid)
        await q.edit_message_text("🗑 *Project Deleted*", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=main_menu())
        return
    if data.startswith("file_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        await q.edit_message_text(f"📄 *File:* `{esc(fname)}`\n🆔 `{esc(pid)}`\n\nChoose action:", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=file_actions(pid, fname))
        return
    if data.startswith("view_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        p = await get_project(pid)
        f = find_file(p, fname) if p else None
        if not f:
            await q.edit_message_text("❌ File not found.")
            return
        content = f["content"]
        if len(content) > 3000:
            await q.edit_message_text(f"📄 `{esc(fname)}` too big ({human_size(f['size'])}). Use /viewfile command.", parse_mode=ParseMode.MARKDOWN_V2)
            return
        try:
            await q.message.reply_text(content[:3000])
        except Exception:
            await q.edit_message_text("⚠️ Cannot display. Use /viewfile to download.")
        return
    if data.startswith("dl_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        p = await get_project(pid)
        f = find_file(p, fname) if p else None
        if not f:
            return
        buf = io.BytesIO(f["content"].encode())
        buf.name = fname
        await q.message.reply_document(document=buf, filename=fname, caption=f"📄 {fname}")
        return
    if data.startswith("delf_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        p = await get_project(pid)
        if not p or p["owner_id"]!= u.id:
            return
        files = fm_delete_file(p, fname)
        await update_project(pid, {"files": files})
        await q.edit_message_text(f"🗑 `{esc(fname)}` deleted.", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=files_list(pid, files))
        return
    if data.startswith("ren_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        USER_STATE[u.id] = {"action": "renamefile", "pid": pid, "fname": fname}
        await q.edit_message_text(f"📝 *Rename File*\n\nCurrent: `{esc(fname)}`\nSend new name:", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data.startswith("edit_"):
        try:
            _, pid, fname = data.split("_", 2)
        except ValueError:
            return
        USER_STATE[u.id] = {"action": "editfile", "pid": pid, "fname": fname}
        await q.edit_message_text(f"✏️ *Edit File*\n\n`{esc(fname)}`\nSend new content:", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data.startswith("addf_"):
        pid = data.split("_", 1)[1]
        USER_STATE[u.id] = {"action": "askfilename", "pid": pid}
        await q.edit_message_text("➕ *Add New File*\n\nSend file name with extension:\nExample: `about.html`, `style.css`", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data.startswith("prev_"):
        pid = data.split("_", 1)[1]
        url = f"{WEBHOOK_URL}/preview/{pid}"
        await q.edit_message_text(f"👁 *Preview*\n{url}", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Open Preview", url=url)], [InlineKeyboardButton("⬅️ Back", callback_data=f"open_{pid}")]]))
        return
    if data.startswith("deploy_"):
        pid = data.split("_", 1)[1]
        url = f"{WEBHOOK_URL}/s/{pid}"
        await update_project(pid, {"deploy_url": url, "is_public": True})
        await q.edit_message_text(f"🚀 *Deployed\\!*\n\n🌐 {esc(url)}", parse_mode=ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌐 Visit Site", url=url)], [InlineKeyboardButton("⬅️ Back", callback_data=f"open_{pid}")]]))
        return
    if data.startswith("zip_"):
        pid = data.split("_", 1)[1]
        p = await get_project(pid)
        if not p or p["owner_id"]!= u.id:
            await q.edit_message_text("❌ Not found.")
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in p["files"]:
                z.writestr(f["name"], f["content"])
        buf.seek(0)
        buf.name = f"{pid}.zip"
        await q.message.reply_document(document=buf, filename=f"{pid}.zip", caption=f"📦 {p['name']}")
        return
    if data.startswith("renp_"):
        pid = data.split("_", 1)[1]
        USER_STATE[u.id] = {"action": "renameproject", "pid": pid}
        await q.edit_message_text("✏️ *Rename Project*\n\nSend new name:", parse_mode=ParseMode.MARKDOWN_V2)
        return
    if data.startswith("tpl_"):
        tpl = data.split("_", 1)[1]
        await q.edit_message_text(f"🎨 *Template: {esc(tpl)}*\n\nUse:\n`/newproject MySite {tpl}`", parse_mode=ParseMode.MARKDOWN_V2)
        return
