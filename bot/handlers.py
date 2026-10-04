import secrets
import html
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.database import create_project, get_project
from bot.config import WEBHOOK_URL, DEV_USERNAME
from bot.templates import get_aesthetic_html
from bot.keyboards import get_project_menu_keyboard
from bot.filemanager import create_project_zip

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✨ <b>Welcome to Web Builder Bot!</b> ✨\n\n"
        "Build, manage, and deploy high-performance web applications easily.\n\n"
        "<b>Quick Actions:</b>\n"
        "• Use /help to see all available commands\n"
        "• Use /newproject <code>&lt;name&gt;</code> <code>&lt;type&gt;</code> to start\n\n"
        f"👤 <b>Developer:</b> {DEV_USERNAME}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🚀 <b>Commands Guide</b>\n\n"
        "<b>Project Commands:</b>\n"
        "• /newproject <code>&lt;name&gt; &lt;type&gt;</code> - Create project\n"
        "• /preview <code>&lt;id&gt;</code> - Generate preview link\n"
        "• /deploy <code>&lt;id&gt;</code> - Get public URL\n"
        "• /exportzip <code>&lt;id&gt;</code> - Download ZIP archive\n\n"
        "<b>Templates:</b> portfolio | blog | landing | ecommerce | admin"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def newproject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ <b>Usage:</b> /newproject <code>&lt;name&gt; &lt;type&gt;</code>", parse_mode="HTML")
        return

    p_name = context.args[0]
    p_type = context.args[1].lower()
    p_id = f"WEB-{secrets.token_hex(3).upper()}"
    
    html_body = f"<p>Welcome to your aesthetic <b>{html.escape(p_type)}</b> project!</p>"
    formatted_html = get_aesthetic_html(p_name, html_body)

    await create_project(update.effective_user.id, p_id, p_name, p_type, formatted_html)

    reply = (
        f"✅ <b>Project Initialized!</b>\n\n"
        f"<b>ID:</b> <code>{p_id}</code>\n"
        f"<b>Name:</b> {html.escape(p_name)}\n"
        f"<b>Type:</b> {html.escape(p_type)}"
    )
    await update.message.reply_text(reply, parse_mode="HTML", reply_markup=get_project_menu_keyboard(p_id))

async def preview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ <b>Usage:</b> /preview <code>&lt;id&gt;</code>", parse_mode="HTML")
        return
    p_id = context.args[0]
    await update.message.reply_text(f"🔗 <b>Preview URL:</b> {WEBHOOK_URL}/preview/{p_id}", parse_mode="HTML")

async def deploy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ <b>Usage:</b> /deploy <code>&lt;id&gt;</code>", parse_mode="HTML")
        return
    p_id = context.args[0]
    await update.message.reply_text(f"🚀 <b>Live Site:</b> {WEBHOOK_URL}/s/{p_id}", parse_mode="HTML")

async def exportzip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ <b>Usage:</b> /exportzip <code>&lt;id&gt;</code>", parse_mode="HTML")
        return
    p_id = context.args[0]
    zip_data = await create_project_zip(p_id)
    if zip_data:
        await update.message.reply_document(document=zip_data, filename=f"{p_id}.zip")
    else:
        await update.message.reply_text("❌ Project not found!")

def register_handlers(app):
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("newproject", newproject_cmd))
    app.add_handler(CommandHandler("preview", preview_cmd))
    app.add_handler(CommandHandler("deploy", deploy_cmd))
    app.add_handler(CommandHandler("exportzip", exportzip_cmd))
