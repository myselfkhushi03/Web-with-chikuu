import os, time, zipfile, shutil, qrcode
from io import BytesIO
from threading import Thread
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from web_app import web
from utils import *

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_HOSTNAME", "localhost:10000")
PENDING_CUSTOM = {}

Thread(target=lambda: web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))), daemon=True).start()

async def setup(app):
    await app.bot.set_my_commands([
        BotCommand("start","🚀 Start"),
        BotCommand("create","✨ Custom link"),
        BotCommand("mysites","📁 My Sites"),
        BotCommand("delete","🗑️ Delete"),
        BotCommand("setpassword","🔒 Password"),
        BotCommand("qr","📱 QR Code"),
        BotCommand("stats","📊 Stats"),
    ])

async def start(update, context):
    await update.message.reply_text(
        "💖 **File-to-Web Bot - Full Power**\n━━━━━━━━━━━━\n"
        "📤 File bhej = Website link\n\n"
        "✨ /create mylove -> custom naam\n"
        "📁 /mysites -> teri sites\n"
        "🔒 /setpassword id 1234\n"
        "📱 /qr id -> QR code\n"
        "🗑️ /delete id\n\n"
        "ZIP, HTML, Photo, Video sab support hai!"
    )

async def create_cmd(update, context):
    if not context.args:
        await update.message.reply_text("Use: /create mylovepage"); return
    PENDING_CUSTOM[update.effective_user.id] = context.args[0]
    await update.message.reply_text(f"✅ Agli file ka link: `{context.args[0]}`\nAb file bhej!", parse_mode="Markdown")

async def handle_files(update, context):
    user_id = update.effective_user.id
    custom = PENDING_CUSTOM.pop(user_id, None)
    site_id, path = create_site(user_id, custom)
    if not site_id:
        await update.message.reply_text(path); return

    status = await update.message.reply_text("⏳ Bana raha hu website...")

    if update.message.photo:
        f = await update.message.photo[-1].get_file()
        fname = f"photo_{int(time.time())}.jpg"
    elif update.message.document:
        f = await update.message.document.get_file()
        fname = update.message.document.file_name
    elif update.message.video:
        f = await update.message.video.get_file()
        fname = f"video_{int(time.time())}.mp4"
    else:
        await status.edit_text("❌ File type support nahi"); return

    fpath = os.path.join(SITES_DIR, site_id, fname)
    await f.download_to_drive(fpath)

    if fname.endswith(".zip"):
        with zipfile.ZipFile(fpath, 'r') as z:
            z.extractall(os.path.join(SITES_DIR, site_id))
        os.remove(fpath)

    add_file_to_site(site_id, fname)
    all_files = [x for x in os.listdir(os.path.join(SITES_DIR, site_id)) if x!= "index.html"]
    if not any(x.endswith(".html") for x in all_files):
        make_gallery_html(site_id, all_files)

    link = f"https://{RENDER_URL}/site/{site_id}"
    qr = qrcode.make(link)
    qr_path = os.path.join(SITES_DIR, site_id, "_qr.png")
    qr.save(qr_path)

    await status.delete()
    await update.message.reply_photo(
        photo=open(qr_path, "rb"),
        caption=f"🎉 **Website Ready!**\n📁 ID: `{site_id}`\n🔗 {link}\n\n🔒 `/setpassword {site_id} 1234`",
        parse_mode="Markdown"
    )

async def my_sites(update, context):
    sites = get_user_sites(update.effective_user.id)
    if not sites: await update.message.reply_text("📭 Koi site nahi"); return
    txt = "📁 **Your Sites:**\n"
    for sid,d in sites.items():
        txt += f"• `{sid}` - {d['views']} views - https://{RENDER_URL}/site/{sid}\n"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def delete_site(update, context):
    if not context.args: return
    sid = context.args[0]
    sites = load_json(SITES_FILE)
    if sid not in sites or sites[sid]["owner"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not yours"); return
    shutil.rmtree(os.path.join(SITES_DIR, sid), ignore_errors=True)
    sites.pop(sid); save_json(SITES_FILE, sites)
    await update.message.reply_text(f"🗑️ {sid} deleted")

async def set_pwd(update, context):
    if len(context.args)<2: await update.message.reply_text("Use: /setpassword id pwd"); return
    sid,pwd = context.args[0], context.args[1]
    sites = load_json(SITES_FILE)
    if sid not in sites or sites[sid]["owner"]!= update.effective_user.id:
        await update.message.reply_text("❌ Not yours"); return
    sites[sid]["password"]=pwd; save_json(SITES_FILE, sites)
    await update.message.reply_text(f"🔒 Password set: https://{RENDER_URL}/site/{sid}?pwd={pwd}")

async def qr_cmd(update, context):
    if not context.args: return
    sid = context.args[0]
    link = f"https://{RENDER_URL}/site/{sid}"
    qr = qrcode.make(link)
    bio = BytesIO(); qr.save(bio,"PNG"); bio.seek(0)
    await update.message.reply_photo(bio, caption=f"📱 QR for {sid}\n{link}")

async def stats_cmd(update, context):
    sites = load_json(SITES_FILE)
    await update.message.reply_text(f"📊 Total: {len(sites)}\nYour: {len(get_user_sites(update.effective_user.id))}")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(setup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_cmd))
    app.add_handler(CommandHandler("mysites", my_sites))
    app.add_handler(CommandHandler("delete", delete_site))
    app.add_handler(CommandHandler("setpassword", set_pwd))
    app.add_handler(CommandHandler("qr", qr_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL | filters.VIDEO, handle_files))
    print("Bot Started")
    app.run_polling()

if __name__ == "__main__": main()
