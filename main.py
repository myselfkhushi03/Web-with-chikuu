from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
from bot.handlers import register_handlers
from web.app import fastapi_app

# Modern Lifespan Event Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Bot & Set Webhook
    if BOT_TOKEN:
        await ptb_app.initialize()
        await ptb_app.start()
        if WEBHOOK_URL:
            endpoint = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
            await ptb_app.bot.set_webhook(url=endpoint, secret_token=WEBHOOK_SECRET)
    yield
    # Shutdown: Stop Bot
    if BOT_TOKEN:
        await ptb_app.stop()
        await ptb_app.shutdown()

app = fastapi_app
app.router.lifespan_context = lifespan

# Initialize Bot
ptb_app = Application.builder().token(BOT_TOKEN or "DUMMY_TOKEN").build()
register_handlers(ptb_app)

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
