import os
import secrets
import html
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from motor.motor_asyncio import AsyncIOMotorClient

# Environment Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Must NOT end with '/'
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", secrets.token_urlsafe(16))
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.getenv("PORT", 10000))

# Initialize App & Database
app = FastAPI(title="Web Builder Service", version="2.0.0")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["web_builder_db"]
projects_collection = db["projects"]

# Initialize Telegram Bot
ptb_app = Application.builder().token(BOT_TOKEN).build()

# Beautiful Default Web Page Template
def generate_aesthetic_template(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            width: 100%;
            max-width: 800px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(16px);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
        }}
        h1 {{
            font-size: 2.5rem;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 16px;
        }}
        p {{ color: var(--text-muted); line-height: 1.6; font-size: 1.1rem; }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
            color: var(--text-muted);
        }}
        .footer a {{ color: #a855f7; text-decoration: none; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div>{content}</div>
        <div class="footer">
            <span>Built with Web-with-chikuu</span>
            <span>Created by <a href="https://instagram.com/myselfkhushi03" target="_blank">@myselfkhushi03</a></span>
        </div>
    </div>
</body>
</html>"""

# Bot Handlers (English)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = (
        "✨ <b>Welcome to Web Builder Bot!</b> ✨\n\n"
        "Create, preview, and deploy aesthetic websites effortlessly right from Telegram.\n\n"
        "<b>Quick Start:</b>\n"
        "• Send /help to view all available commands\n"
        "• Send /newproject <code>&lt;name&gt;</code> <code>&lt;type&gt;</code> to create a project\n\n"
        "👤 <b>Developer:</b> @myselfkhushi03"
    )
    await update.message.reply_text(welcome_msg, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_msg = (
        "🚀 <b>Web Builder Commands Guide</b>\n\n"
        "<b>📁 Project Commands:</b>\n"
        "• /newproject <code>&lt;name&gt;</code> <code>&lt;type&gt;</code> - Create new project\n"
        "• /myprojects - View all your active projects\n"
        "• /openproject <code>&lt;id&gt;</code> - Manage project files\n"
        "• /deleteproject <code>&lt;id&gt;</code> - Remove project\n\n"
        "<b>🌐 Preview & Deploy:</b>\n"
        "• /preview <code>&lt;id&gt;</code> - Generate live preview link\n"
        "• /deploy <code>&lt;id&gt;</code> - Publish project online\n"
        "• /exportzip <code>&lt;id&gt;</code> - Download source code as ZIP\n\n"
        "<b>🎨 Available Templates:</b>\n"
        "<code>portfolio</code> | <code>blog</code> | <code>landing</code> | <code>ecommerce</code> | <code>admin</code>\n\n"
        "📬 <b>Support:</b> @myselfkhushi03"
    )
    await update.message.reply_text(help_msg, parse_mode="HTML")

async def new_project_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ <b>Usage:</b> /newproject <code>&lt;name&gt;</code> <code>&lt;type&gt;</code>", parse_mode="HTML")
        return

    p_name = context.args[0]
    p_type = context.args[1].lower()
    p_id = f"WEB-{secrets.token_hex(3).upper()}"

    project_data = {
        "project_id": p_id,
        "user_id": user_id,
        "name": p_name,
        "type": p_type,
        "html_content": f"<p>Welcome to your new <b>{html.escape(p_type)}</b> project!</p>"
    }
    
    await projects_collection.insert_one(project_data)
    
    response = (
        f"✅ <b>Project Created Successfully!</b>\n\n"
        f"<b>ID:</b> <code>{p_id}</code>\n"
        f"<b>Name:</b> {html.escape(p_name)}\n"
        f"<b>Type:</b> {html.escape(p_type)}\n\n"
        f"Use /preview <code>{p_id}</code> to check your site."
    )
    await update.message.reply_text(response, parse_mode="HTML")

async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ <b>Usage:</b> /preview <code>&lt;project_id&gt;</code>", parse_mode="HTML")
        return

    p_id = context.args[0]
    base_url = WEBHOOK_URL.rstrip('/')
    preview_url = f"{base_url}/preview/{p_id}"
    
    await update.message.reply_text(
        f"🔗 <b>Live Preview URL:</b>\n{preview_url}",
        parse_mode="HTML"
    )

# Register Handlers
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("help", help_command))
ptb_app.add_handler(CommandHandler("newproject", new_project_command))
ptb_app.add_handler(CommandHandler("preview", preview_command))

# FastAPI Lifecycle Events
@app.on_event("startup")
async def startup_event():
    await ptb_app.initialize()
    await ptb_app.start()
    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook/{WEBHOOK_SECRET}"
    await ptb_app.bot.set_webhook(url=webhook_endpoint, secret_token=WEBHOOK_SECRET)

@app.on_event("shutdown")
async def shutdown_event():
    await ptb_app.stop()
    await ptb_app.shutdown()

# FastAPI Routes
@app.get("/", response_class=HTMLResponse)
async def landing_page():
    return generate_aesthetic_template(
        "Web Builder Bot Engine",
        "<p>System operational. Manage your web projects seamlessly through Telegram.</p>"
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "web-builder-bot"}

@app.get("/preview/{project_id}", response_class=HTMLResponse)
async def serve_preview(project_id: str):
    project = await projects_collection.find_one({"project_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return generate_aesthetic_template(project.get("name", "Web Project"), project.get("html_content", ""))

@app.get("/s/{project_id}", response_class=HTMLResponse)
async def serve_deployed(project_id: str):
    return await serve_preview(project_id)

@app.post(f"/webhook/{{WEBHOOK_SECRET}}")
async def telegram_webhook(request: Request):
    headers = request.headers
    if headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized request")
    
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
