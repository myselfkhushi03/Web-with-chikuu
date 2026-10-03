import os, asyncio, threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from web_app import web
from utils import *

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL", "https://web-with-chikuu.onrender.com")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("File bhejo, main link bana dunga ❤️\n\nCommands:\n/create <name> - custom name\n/mysites - tumhari sites\n/delete <id>\n/setpassword <id> <pass>")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    site_id = context.user_data.get("custom_name") or new_id()
    context.user_data.pop("custom_name", None)

    folder = os.path.join(SITES_DIR, site_id)
    os.makedirs(folder, exist_ok=True)

    file = update.message.document or update.message.photo or update.message.video
    if update.message.photo:
        file = update.message.photo[-1]

    tg_file = await file.get_file()
    file_path = os.path.join(folder, file.file_name if hasattr(file, 'file_name') and file.file_name else f"file{os.path.splitext(tg_file.file_path)[1]}")
    await tg_file.download_to_drive(file_path)

    # zip extract
    if file_path.endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(file_path, 'r') as z:
            z.extractall(folder)
        os.remove(file_path)

    sites = load_json(SITES_FILE)
    sites[site_id] = {"owner": user_id, "views": 0, "password": None}
    save_json(SITES_FILE, sites)

    link = f"{BASE_URL}/site/{site_id}"
    await update.message.reply_text(f"✅ Ban gaya!\n\n🔗 Link: {link}\n\n/qr {site_id} - QR banao\n/setpassword {site_id} 1234 - Lock lagao")

async def create_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /create mylove")
        return
    context.user_data["custom_name"] = context.args[0]
    await update.message.reply_text(f"Ok ab file bhejo, naam hoga: {context.args[0]}")

async def mysites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sites = load_json(SITES_FILE)
    user_id = str(update.effective_user.id)
    my = [k for k,v in sites.items() if v['owner']==user_id]
    if not my:
        await update.message.reply_text("Tumhari koi site nahi hai")
        return
    txt = "\n".join([f"{BASE_URL}/site/{s} - Views: {sites[s]['views']}" for s in my])
    await update.message.reply_text(txt)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

async def main_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_cmd))
    app.add_handler(CommandHandler("mysites", mysites))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_file))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main_bot())
