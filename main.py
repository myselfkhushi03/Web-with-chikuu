import os, threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from web_app import web
from utils import *

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL", "https://web-with-chikuu.onrender.com")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("File bhejo, main link bana dunga ❤️\n\n/create <name> - custom name\n/mysites - list\n/delete <id>")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    site_id = context.user_data.get("custom_name") or new_id()
    context.user_data.pop("custom_name", None)
    folder = os.path.join(SITES_DIR, site_id)
    os.makedirs(folder, exist_ok=True)

    f = update.message.document or update.message.photo or update.message.video or update.message.audio
    if update.message.photo:
        f = update.message.photo[-1]
    if not f:
        await update.message.reply_text("Koi file bhejo")
        return

    tg_file = await f.get_file()
    name = getattr(f, 'file_name', None) or f.file_id + ".bin"
    if update.message.photo:
        name = f.file_id + ".jpg"
    path = os.path.join(folder, name)
    await tg_file.download_to_drive(path)

    if path.endswith(".zip"):
        import zipfile
        try:
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(folder)
            os.remove(path)
        except: pass

    sites = load_json(SITES_FILE)
    sites[site_id] = {"owner": user_id, "views": 0, "password": None}
    save_json(SITES_FILE, sites)

    link = f"{BASE_URL}/site/{site_id}"
    await update.message.reply_text(f"✅ Ho gaya!\n\nLink: {link}")

async def create_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /create mylove")
        return
    context.user_data["custom_name"] = context.args[0]
    await update.message.reply_text(f"Ok, ab file bhejo. Naam: {context.args[0]}")

async def mysites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sites = load_json(SITES_FILE)
    uid = str(update.effective_user.id)
    my = [k for k,v in sites.items() if v['owner']==uid]
    if not my:
        await update.message.reply_text("Koi site nahi hai")
        return
    txt = "\n".join([f"{BASE_URL}/site/{s}" for s in my])
    await update.message.reply_text(txt)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_cmd))
    app.add_handler(CommandHandler("mysites", mysites))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_file))
    app.run_polling()
