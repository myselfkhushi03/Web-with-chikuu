import os, asyncio
from flask import Flask, request, send_from_directory, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from utils import *

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL","")
app = Flask(__name__)

application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("File bhejo ❤️")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid=str(update.effective_user.id)
    sid=new_id()
    folder=os.path.join(SITES_DIR,sid)
    os.makedirs(folder,exist_ok=True)
    f=update.message.document or update.message.photo or update.message.video
    if update.message.photo: f=update.message.photo[-1]
    if not f: return
    tg=await f.get_file()
    name=getattr(f,'file_name',None) or f"{f.file_id}.bin"
    if update.message.photo: name=f"{f.file_id}.jpg"
    path=os.path.join(folder,name)
    await tg.download_to_drive(path)
    sites=load_json(SITES_FILE)
    sites[sid]={"owner":uid,"views":0}
    save_json(SITES_FILE,sites)
    await update.message.reply_text(f"✅ Ban gaya!\n{BASE_URL}/site/{sid}")

application.add_handler(CommandHandler("start",start))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_file))

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data=request.get_json(force=True)
    upd=Update.de_json(data, application.bot)
    asyncio.run(application.process_update(upd))
    return "ok"

@app.route("/site/<site_id>/")
@app.route("/site/<site_id>/<path:filename>")
def serve_site(site_id, filename="index.html"):
    folder=os.path.join(SITES_DIR,site_id)
    if not os.path.exists(folder): abort(404)
    return send_from_directory(folder, filename)

@app.route("/")
def home(): return "Bot Live ❤️"
