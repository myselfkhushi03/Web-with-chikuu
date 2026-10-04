import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
from bot.handlers import register_handlers
from web.app import fastapi_app

# Modern FastAPI Lifespan Handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe Startup
    if BOT_TOKEN and BOT_TOKEN != "your_bot_token_here":
        try:
            await ptb_app.initialize()
            await ptb_app.start()
            if WEBHOOK_URL:
                endpoint = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
                await ptb_app.bot.set_webhook(url=endpoint, secret_token=WEBHOOK_SECRET)
        except Exception as e:
            print(f"Startup Webhook Error: {e}")
    yield
    # Safe Shutdown
    if BOT_TOKEN and BOT_TOKEN != "your_bot_token_here":
        try:
            await ptb_app.stop()
            await ptb_app.shutdown()
        except Exception as e:
            print(f"Shutdown Error: {e}")

# Base Application
app = fastapi_app
app.router.lifespan_context = lifespan

# Initialize Bot safely
token_to_use = BOT_TOKEN if BOT_TOKEN else "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
ptb_app = Application.builder().token(token_to_use).build()
register_handlers(ptb_app)

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
