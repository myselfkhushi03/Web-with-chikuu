import os, asyncio, traceback, zipfile, shutil
from flask import Flask, request, send_from_directory, abort
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from utils import *

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL","").rstrip("/")
app = Flask(__name__)

application = Application.builder().token(BOT_TOKEN).build()

# --- Aesthetic Messages ---
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 My Sites", callback_data="mysites"),
         InlineKeyboardButton("💡 Help", callback_data="help")],
        [InlineKeyboardButton("🌐 Visit Render", url=BASE_URL)]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "✨ **Welcome to Chikuu's Web Bot** ✨\n\n"
        "👋 Hey! I'm your personal website maker bot.\n\n"
        "🚀 **What I can do:**\n"
        "• 📄 Upload any HTML / TXT / ZIP\n"
        "• 🖼️ Send Photos, Videos, PDFs\n"
        "• 🔗 Get instant public link\n"
        "• 📊 Track views & manage sites\n\n"
        "📤 **Just send me a file as Document and I’ll make it live!**\n\n"
        "___Made with 💖 by Chikuu___"
    )
    await update.message.reply_text(msg, reply_markup=main_menu(), parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💎 **How to use ChikuuWeb**\n\n"
        "1️⃣ Send any file (HTML, ZIP, image)\n"
        "2️⃣ I’ll host it instantly\n"
        "3️⃣ You get a link like:\n"
        f"`{BASE_URL}/site/abc123`\n\n"
        "📦 **ZIP TIP:** If your ZIP has `index.html`, it will be a full website!\n\n"
        "🔧 **Commands:**\n"
        "/start - Start bot\n"
        "/mysites - List your sites\n"
        "/help - This help\n"
        "/delete <id> - Delete a site\n\n"
        "⚡ Files are public, anyone with link can view."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def mysites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    sites = load_json(SITES_FILE)
    my = {k:v for k,v in sites.items() if v.get("owner")==uid}
    if not my:
        await update.message.reply_text("😕 **No sites yet!**\nSend me a file to create your first one ✨", parse_mode="Markdown")
        return
    text = "🌟 **Your Magical Sites** 🌟\n\n"
    for sid, info in list(my.items())[-10:]:
        text += f"🔗 `/{sid}` - {info.get('file','site')} 👁️ {info.get('views',0)} views\n➡️ {BASE_URL}/site/{sid}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid=str(update.effective_user.id)
        sid=new_id()
        folder=os.path.join(SITES_DIR,sid)
        os.makedirs(folder,exist_ok=True)

        file_obj=None
        file_name="index.html"

        if update.message.document:
            file_obj=update.message.document
            file_name=file_obj.file_name
        elif update.message.photo:
            file_obj=update.message.photo[-1]
            file_name=f"photo_{file_obj.file_id}.jpg"
        else:
            await update.message.reply_text("⚠️ Please send file as **Document** 📁", parse_mode="Markdown")
            return

        status_msg = await update.message.reply_text("⚙️ _Uploading your magic..._ ✨", parse_mode="Markdown")

        tg_file=await file_obj.get_file()
        path=os.path.join(folder,file_name)
        await tg_file.download_to_drive(path)

        # If ZIP, extract it
        if file_name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(path, 'r') as z:
                    z.extractall(folder)
                os.remove(path)
                file_name = "ZIP Website 📦"
            except Exception as e:
                await status_msg.edit_text(f"❌ Zip extract failed: {e}")
                return
        else:
            # Make copy as index.html if needed
            index_path=os.path.join(folder,"index.html")
            if file_name!="index.html" and not os.path.exists(index_path):
                if file_name.lower().endswith(('.html','.txt','.htm')):
                    shutil.copy(path, index_path)

        sites=load_json(SITES_FILE)
        sites[sid]={"owner":uid,"file":file_name,"views":0}
        save_json(SITES_FILE,sites)

        link = f"{BASE_URL}/site/{sid}"

        success_text = (
            f"✅ **Boom! Your site is LIVE!** 🚀\n\n"
            f"📄 **File:** `{file_name}`\n"
            f"🆔 **ID:** `{sid}`\n"
            f"👁️ **Views:** `0`\n\n"
            f"🌐 **Your Link:**\n{link}\n\n"
            f"💡 _Share this link anywhere, it works for everyone!_\n\n"
            f"✨ _Tip: Send ZIP with index.html for full website_"
        )
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Open Site", url=link)],
            [InlineKeyboardButton("📁 My Sites", callback_data="mysites")]
        ])
        await status_msg.edit_text(success_text, reply_markup=btn, parse_mode="Markdown", disable_web_page_preview=True)

    except Exception as e:
        traceback.print_exc()
        await update.message.reply_text(f"❌ **Oops! Something broke** 💔\n`{e}`\n\nTry again with another file.", parse_mode="Markdown")

# Callbacks
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    await q.answer()
    if q.data=="mysites":
        uid=str(q.from_user.id)
        sites=load_json(SITES_FILE)
        my={k:v for k,v in sites.items() if v.get("owner")==uid}
        if not my:
            await q.edit_message_text("😕 No sites yet! Send a file ✨")
            return
        text="🌟 **Your Sites** 🌟\n\n"
        for sid,info in list(my.items())[-10:]:
            text+=f"🔗 `{sid}` - {info.get('file')} 👁️ {info.get('views',0)}\n{link}\n".replace("{link}", f"{BASE_URL}/site/{sid}")
        await q.edit_message_text(text, parse_mode="Markdown")
    elif q.data=="help":
        await help_cmd(q, context)

application.add_handler(CommandHandler("start",start))
application.add_handler(CommandHandler("help",help_cmd))
application.add_handler(CommandHandler("mysites",mysites))
application.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(application.initialize())
loop.run_until_complete(application.start())

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data=request.get_json(force=True)
    upd=Update.de_json(data, application.bot)
    loop.run_until_complete(application.process_update(upd))
    return "ok"

@app.route("/site/<site_id>")
@app.route("/site/<site_id>/<path:filename>")
def serve_site(site_id, filename="index.html"):
    folder=os.path.join(SITES_DIR,site_id)
    if not os.path.exists(folder): abort(404)
    # views++
    try:
        sites=load_json(SITES_FILE)
        if site_id in sites:
            sites[site_id]["views"]=sites[site_id].get("views",0)+1
            save_json(SITES_FILE,sites)
    except: pass

    full_path=os.path.join(folder, filename)
    if not os.path.exists(full_path):
        files=os.listdir(folder)
        if files: return send_from_directory(folder, files[0])
    return send_from_directory(folder, filename)

@app.route("/")
def home(): return "✨ ChikuuWeb Bot is Live ✨"
