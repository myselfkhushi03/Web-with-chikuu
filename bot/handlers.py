import secrets
import html
import io
from telegram import Update, BotCommand
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from bot.config import WEBHOOK_URL, DEV_USERNAME, ADMIN_ID, MAX_FILE_SIZE, MAX_TOTAL_STORAGE, GITHUB_ISSUES
from bot.database import (
    create_project, get_project, get_user_projects, update_project_file,
    delete_project_file, rename_project_file, delete_project_db, rename_project_db,
    get_user_storage_size, get_stats
)
from bot.utils import esc, human_size
from bot.templates import get_template_files
from bot.filemanager import create_project_zip
from bot.keyboards import (
    main_menu_kb, projects_list_kb, project_menu_kb, confirm_delete_kb,
    files_list_kb, file_actions_kb, templates_kb
)

# Conversation states store
USER_STATE = {}

async def set_bot_commands(app):
    """Set side menu slash commands in Telegram Chat"""
    commands = [
        BotCommand("start", "Start bot & main menu"),
        BotCommand("help", "Full command guide"),
        BotCommand("newproject", "<name> <type> - Create site"),
        BotCommand("myprojects", "List all your websites"),
        BotCommand("openproject", "<id> - Open project details"),
        BotCommand("deleteproject", "<id> - Delete project"),
        BotCommand("renameproject", "<id> <new> - Rename project"),
        BotCommand("cloneproject", "<id> - Duplicate project"),
        BotCommand("listfiles", "<id> - List project files"),
        BotCommand("addfile", "<id> <file> - Add custom code/file"),
        BotCommand("editfile", "<id> <file> - Edit file code"),
        BotCommand("deletefile", "<id> <file> - Delete file"),
        BotCommand("viewfile", "<id> <file> - Read file code"),
        BotCommand("renamefile", "<id> <old> <new> - Rename file"),
        BotCommand("preview", "<id> - Get live preview link"),
        BotCommand("deploy", "<id> - Publish live website"),
        BotCommand("exportzip", "<id> - Download project ZIP"),
        BotCommand("templates", "Browse ready website templates"),
        BotCommand("storage", "Check storage consumption"),
        BotCommand("status", "System & stats status"),
        BotCommand("admin", "Admin dashboard stats")
    ]
    await app.bot.set_my_commands(commands)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✨ *Welcome to Web\\-with\\-chikuu Builder Bot\\!* ✨\n\n"
        "Build, manage, edit, and publish aesthetic web applications directly from Telegram\\.\n\n"
        "🚀 *Features:* Unlimited files, Custom uploads, Live preview, Instant deployment, ZIP export\\.\n\n"
        f"👤 *Developer:* [{esc(DEV_USERNAME)}](https://instagram.com/myselfkhushi03)"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=main_menu_kb())

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *Web\\-with\\-chikuu Command Guide*\n\n"
        "📂 *Projects:*\n"
        "• `/newproject <name> <type>` \\- Create site\n"
        "• `/myprojects` \\- List your projects\n"
        "• `/openproject <id>` \\- Open project details\n"
        "• `/renameproject <id> <new>` \\- Rename site\n"
        "• `/cloneproject <id>` \\- Duplicate project\n"
        "• `/deleteproject <id>` \\- Delete site\n\n"
        "📄 *File Management:*\n"
        "• `/addfile <id> <filename>` \\- Add via message/upload\n"
        "• `/editfile <id> <filename>` \\- Edit code\n"
        "• `/viewfile <id> <filename>` \\- View code\n"
        "• `/deletefile <id> <filename>` \\- Remove file\n"
        "• `/renamefile <id> <old> <new>` \\- Rename file\n\n"
        "🌐 *Deployment & Export:*\n"
        "• `/preview <id>` \\- Generate preview link\n"
        "• `/deploy <id>` \\- Deploy public URL\n"
        "• `/exportzip <id>` \\- Download ZIP archive"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def newproject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ *Usage:* `/newproject <name> <type>`\n_Types:_ `portfolio`, `blog`, `landing`, `ecommerce`, `admin`, `custom`", parse_mode="MarkdownV2")
        return

    p_name = context.args[0]
    p_type = context.args[1].lower()
    p_id = f"WEB\\-{secrets.token_hex(3).upper()}"
    p_id_raw = p_id.replace('\\', '')

    initial_files = get_template_files(p_type, p_name)
    success = await create_project(update.effective_user.id, p_id_raw, p_name, p_type, initial_files)

    if not success:
        await update.message.reply_text("❌ *Limit Reached:* Free tier permits max 5 projects\\. Delete an existing site first\\.", parse_mode="MarkdownV2")
        return

    reply = f"✅ *Project Created\\!*\n\n🆔 *ID:* `{p_id}`\n📁 *Name:* {esc(p_name)}\n🎨 *Type:* {esc(p_type)}"
    await update.message.reply_text(reply, parse_mode="MarkdownV2", reply_markup=project_menu_kb(p_id_raw))

async def myprojects_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    projects = await get_user_projects(update.effective_user.id)
    if not projects:
        await update.message.reply_text("📂 You have no active projects\\. Use `/newproject` to create one\\.", parse_mode="MarkdownV2")
        return
    await update.message.reply_text("📁 *Your Web Projects:*", parse_mode="MarkdownV2", reply_markup=projects_list_kb(projects))

async def openproject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ *Usage:* `/openproject <id>`", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    project = await get_project(p_id)
    if not project or project["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Project not found or access denied\\.", parse_mode="MarkdownV2")
        return
    
    msg = f"🌐 *Project:* {esc(project['name'])}\n🆔 *ID:* `{esc(p_id)}`\n🎨 *Type:* {esc(project['type'])}"
    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=project_menu_kb(p_id))

async def addfile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ *Usage:* `/addfile <project_id> <filename>`\n_Next, send code or document file in chat\\._", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    filename = context.args[1]

    project = await get_project(p_id)
    if not project or project["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Project not found or access denied\\.", parse_mode="MarkdownV2")
        return

    USER_STATE[update.effective_user.id] = {
        "action": "addfile",
        "project_id": p_id,
        "filename": filename
    }
    await update.message.reply_text(f"📥 Send code text or attach a file document for `{esc(filename)}`:", parse_mode="MarkdownV2")

async def editfile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ *Usage:* `/editfile <project_id> <filename>`", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    filename = context.args[1]

    project = await get_project(p_id)
    if not project or project["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Project not found or access denied\\.", parse_mode="MarkdownV2")
        return

    USER_STATE[update.effective_user.id] = {
        "action": "addfile",
        "project_id": p_id,
        "filename": filename
    }
    await update.message.reply_text(f"✏️ Send new content/document for `{esc(filename)}`:", parse_mode="MarkdownV2")

async def deletefile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ *Usage:* `/deletefile <project_id> <filename>`", parse_mode="MarkdownV2")
        return
    p_id, filename = context.args[0], context.args[1]
    project = await get_project(p_id)
    if not project or project["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Project not found or access denied\\.", parse_mode="MarkdownV2")
        return

    await delete_project_file(p_id, filename)
    await update.message.reply_text(f"🗑️ File `{esc(filename)}` deleted\\.", parse_mode="MarkdownV2")

async def viewfile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ *Usage:* `/viewfile <project_id> <filename>`", parse_mode="MarkdownV2")
        return
    p_id, filename = context.args[0], context.args[1]
    project = await get_project(p_id)
    if not project or project["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Project not found or access denied\\.", parse_mode="MarkdownV2")
        return

    content = project.get("files", {}).get(filename, "")
    if len(content) > 3500:
        file_bytes = io.BytesIO(content.encode("utf-8"))
        await update.message.reply_document(document=file_bytes, filename=filename, caption=f"📄 `{esc(filename)}` \\(Large file attachment\\)", parse_mode="MarkdownV2")
    else:
        await update.message.reply_text(f"📄 *File:* `{esc(filename)}`\n```html\n{content}\n```", parse_mode="MarkdownV2")

async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ *Usage:* `/preview <id>`", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    await update.message.reply_text(f"🔗 *Preview Link:* {WEBHOOK_URL}/preview/{p_id}", parse_mode="MarkdownV2")

async def deploy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ *Usage:* `/deploy <id>`", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    await update.message.reply_text(f"🚀 *Live Deployed URL:* {WEBHOOK_URL}/s/{p_id}", parse_mode="MarkdownV2")

async def exportzip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ *Usage:* `/exportzip <id>`", parse_mode="MarkdownV2")
        return
    p_id = context.args[0]
    zip_data = await create_project_zip(p_id)
    if zip_data:
        await update.message.reply_document(document=zip_data, filename=f"{p_id}.zip")
    else:
        await update.message.reply_text("❌ Project not found\\.", parse_mode="MarkdownV2")

async def storage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    used_bytes = await get_user_storage_size(update.effective_user.id)
    msg = f"📊 *Storage Breakdown*\n\nUsed: `{human_size(used_bytes)}` / `{human_size(MAX_TOTAL_STORAGE)}`"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users_cnt, proj_cnt = await get_stats()
    msg = f"🟢 *Bot Status:* Operational\n\n👥 *Total Users:* {users_cnt}\n🌐 *Total Websites:* {proj_cnt}"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized admin access\\.", parse_mode="MarkdownV2")
        return
    users_cnt, proj_cnt = await get_stats()
    msg = f"👑 *Admin Metrics*\n\nTotal Users: {users_cnt}\nTotal Projects: {proj_cnt}\nServer Node: Render Free Tier"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in USER_STATE:
        state = USER_STATE[user_id]
        p_id = state["project_id"]
        filename = state["filename"]

        content = ""
        if update.message.document:
            doc = update.message.document
            if doc.file_size > MAX_FILE_SIZE:
                await update.message.reply_text("❌ File exceeds 500 KB limit\\.", parse_mode="MarkdownV2")
                return
            file_obj = await context.bot.get_file(doc.file_id)
            downloaded = await file_obj.download_as_bytearray()
            content = downloaded.decode("utf-8", errors="ignore")
        elif update.message.text:
            content = update.message.text

        await update_project_file(p_id, filename, content)
        del USER_STATE[user_id]
        await update.message.reply_text(f"✅ Saved `{esc(filename)}` successfully\\!", parse_mode="MarkdownV2", reply_markup=project_menu_kb(p_id))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "menu_back":
        await query.edit_message_text("✨ *Main Menu*", parse_mode="MarkdownV2", reply_markup=main_menu_kb())
    elif data == "menu_list":
        projects = await get_user_projects(user_id)
        if not projects:
            await query.edit_message_text("📂 You have no active projects\\.", parse_mode="MarkdownV2", reply_markup=main_menu_kb())
        else:
            await query.edit_message_text("📁 *Your Web Projects:*", parse_mode="MarkdownV2", reply_markup=projects_list_kb(projects))
    elif data == "menu_templates":
        await query.edit_message_text("🎨 *Ready Web Templates:*", parse_mode="MarkdownV2", reply_markup=templates_kb())
    elif data.startswith("open_"):
        p_id = data.replace("open_", "")
        project = await get_project(p_id)
        await query.edit_message_text(f"🌐 *Project:* {esc(project['name'])}\n🆔 *ID:* `{esc(p_id)}`", parse_mode="MarkdownV2", reply_markup=project_menu_kb(p_id))
    elif data.startswith("file_"):
        p_id = data.replace("file_", "")
        project = await get_project(p_id)
        await query.edit_message_text("📄 *Project Files:*", parse_mode="MarkdownV2", reply_markup=files_list_kb(p_id, project.get("files", {})))
    elif data.startswith("prev_"):
        p_id = data.replace("prev_", "")
        await query.message.reply_text(f"🔗 *Preview URL:* {WEBHOOK_URL}/preview/{p_id}", parse_mode="MarkdownV2")
    elif data.startswith("deploy_"):
        p_id = data.replace("deploy_", "")
        await query.message.reply_text(f"🚀 *Live Deployed Site:* {WEBHOOK_URL}/s/{p_id}", parse_mode="MarkdownV2")
    elif data.startswith("zip_"):
        p_id = data.replace("zip_", "")
        zip_data = await create_project_zip(p_id)
        if zip_data:
            await query.message.reply_document(document=zip_data, filename=f"{p_id}.zip")

def register_handlers(app):
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newproject", newproject_cmd))
    app.add_handler(CommandHandler("myprojects", myprojects_cmd))
    app.add_handler(CommandHandler("openproject", openproject_cmd))
    app.add_handler(CommandHandler("addfile", addfile_cmd))
    app.add_handler(CommandHandler("editfile", editfile_cmd))
    app.add_handler(CommandHandler("deletefile", deletefile_cmd))
    app.add_handler(CommandHandler("viewfile", viewfile_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("deploy", deploy_cmd))
    app.add_handler(CommandHandler("exportzip", exportzip_cmd))
    app.add_handler(CommandHandler("storage", storage_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_message))
