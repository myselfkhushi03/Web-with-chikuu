import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
from bot.handlers import register_handlers, set_bot_commands
from web.app import fastapi_app

logging.basicConfig(level=logging.INFO)

ptb_app = None

if BOT_TOKEN:
    ptb_app = Application.builder().token(BOT_TOKEN).build()
    register_handlers(ptb_app)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if ptb_app:
        await ptb_app.initialize()
        await ptb_app.start()
        await set_bot_commands(ptb_app)
        if WEBHOOK_URL:
            endpoint = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
            await ptb_app.bot.set_webhook(url=endpoint, secret_token=WEBHOOK_SECRET)
            logging.info(f"Webhook registered at {endpoint}")
    yield
    if ptb_app:
        await ptb_app.stop()
        await ptb_app.shutdown()

app = fastapi_app
app.router.lifespan_context = lifespan

# Render Health Check Routes (Fixes 405 Method Not Allowed)
@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "message": "Web-with-chikuu Bot Service is Running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    if not ptb_app:
        raise HTTPException(status_code=500, detail="Bot Application Not Initialized")
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized Secret Token")
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
