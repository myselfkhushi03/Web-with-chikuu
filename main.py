from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
from bot.config import BOT_TOKEN, WEBHOOK_URL, WEBHOOK_SECRET, PORT
from bot.handlers import register_handlers
from web.app import fastapi_app

app = fastapi_app
ptb_app = Application.builder().token(BOT_TOKEN).build()
register_handlers(ptb_app)

@app.on_event("startup")
async def startup():
    await ptb_app.initialize()
    await ptb_app.start()
    endpoint = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"
    await ptb_app.bot.set_webhook(url=endpoint, secret_token=WEBHOOK_SECRET)

@app.on_event("shutdown")
async def shutdown():
    await ptb_app.stop()
    await ptb_app.shutdown()

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return {"status": "ok"}
