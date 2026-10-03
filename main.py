import os
import random
import shutil
import logging
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)

from utils import SITES_DIR, generate_site_code, extract_zip, inject_audio_script
from web_app import web_app, SITE_PASSWORDS, SITE_METADATA

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-app.onrender.com").rstrip('/')
PORT = int(os.environ.get("PORT", 8080))

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "✨ **Welcome to WebCraft Modular Site Builder Bot!** ✨\n\nNiche buttons se site create/manage karein:"
    keyboard = [
        [InlineKeyboardButton("➕ Create Site", callback_data="btn_new_site"), InlineKeyboardButton("🗂 My Sites", callback_data="btn_my_sites")],
        [InlineKeyboardButton("❓ Help", callback_data="btn_help")]
    ]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def newsite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    site_code = generate_site_code()
    site_path = os.path.join(SITES_DIR, site_code)
    os.makedirs(site_path, exist_ok=True)

    default_html = f"<html><body style='background:#0d1117; color:white; text-align:center;'><h1>Site Code: {site_code}</h1></body></html>"
    with open(os.path.join(site_path, "index.html"), "w", encoding="utf-8") as f:
        f.write(default_html)

    context.user_data["active_site"] = site_code
    SITE_METADATA[site_code] = {"visits": 0}
    site_url = f"{RENDER_EXTERNAL_URL}/site/{site_code}/"

    msg = f"🎉 **New Website Created!**\n🔑 **Code:** `{site_code}`\n🌐 **URL:** {site_url}"
    keyboard = [[InlineKeyboardButton("🌐 Open Site", url=site_url)]]
    
    if update.callback_query:
        await update.callback_query.message.edit_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def select_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/select <SITE_CODE>`", parse_mode="Markdown")
        return
    code = context.args[0].upper()
    if not os.path.exists(os.path.join(SITES_DIR, code)):
        await update.message.reply_text("❌ Invalid Code!")
        return
    context.user_data["active_site"] = code
    await update.message.reply_text(f"✅ **Site `{code}` Selected!**\nAb files bhej kar site update karein.", parse_mode="Markdown")

async def deletesite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Use: `/deletesite <SITE_CODE>`", parse_mode="Markdown")
        return
    code = context.args[0].upper()
    site_path = os.path.join(SITES_DIR, code)
    if os.path.exists(site_path):
        shutil.rmtree(site_path)
        await update.message.reply_text(f"🗑 **Site `{code}` Deleted!**", parse_mode="Markdown")

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_code = context.user_data.get("active_site")
    if not active_code:
        await update.message.reply_text("⚠️ Pehle `/select <CODE>` se site select karein.")
        return

    site_path = os.path.join(SITES_DIR, active_code)
    document, photo, audio = update.message.document, update.message.photo, update.message.audio or update.message.voice

    if document:
        file_obj = await document.get_file()
        file_name = document.file_name
    elif photo:
        file_obj = await photo[-1].get_file()
        file_name = f"img_{random.randint(100,999)}.jpg"
    elif audio:
        file_obj = await audio.get_file()
        file_name = "bg_music.mp3"
    else:
        return

    dest = os.path.join(site_path, file_name)
    await file_obj.download_to_drive(dest)

    if file_name.endswith('.zip'):
        extract_zip(dest, site_path)
        os.remove(dest)
    elif file_name.endswith(('.mp3', '.wav', '.ogg')):
        inject_audio_script(site_path, file_name)

    await update.message.reply_text(f"✅ **File Uploaded to `{active_code}`!**", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "btn_new_site":
        await newsite_command(update, context)

def main():
    Thread(target=lambda: web_app.run(host="0.0.0.0", port=PORT), daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("newsite", newsite_command))
    app.add_handler(CommandHandler("select", select_command))
    app.add_handler(CommandHandler("deletesite", deletesite_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.AUDIO, file_handler))
    
    app.run_polling()

if __name__ == "__main__":
    main()
