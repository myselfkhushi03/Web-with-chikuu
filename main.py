import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET
from bot.handlers import register_handlers
from web.app import fastapi_app

logging.basicConfig(level=logging.INFO)

# Global bot application object
ptb_app = None

if BOT_TOKEN and len(BOT_TOKEN.split(":")) == 2:
    try:
        ptb_app = Application.builder().token(BOT_TOKEN).build()
        register_handlers(ptb_app)
        logging.info("Telegram Bot App Initialized Successfully")
    except Exception as e:
        logging.error(f"Failed to initialize Bot: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if ptb_app:
        try:
            await ptb_app.initialize()
            await ptb_app.start()
            if WEBHOOK_URL:
                endpoint = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
                await ptb_app.bot.set_webhook(url=endpoint, secret_token=WEBHOOK_SECRET)
                logging.info(f"Webhook set to {endpoint}")
        except Exception as e:
            logging.error(f"Webhook setup failed: {e}")
    yield
    if ptb_app:
        try:
            await ptb_app.stop()
            await ptb_app.shutdown()
        except Exception as e:
            logging.error(f"Shutdown error: {e}")

app = fastapi_app
app.router.lifespan_context = lifespan

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    if not ptb_app:
        raise HTTPException(status_code=500, detail="Bot not initialized")
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
