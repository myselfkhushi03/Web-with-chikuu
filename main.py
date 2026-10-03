import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from bot import config
from bot import handlers
from web.app import web


# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("webbuilder-bot")


# ---------------- GLOBAL APP ----------------
ptb_app: Application = None


# ---------------- LIFESPAN ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app

    # Build PTB application (webhook mode)
    ptb_app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .updater(None)  # disable polling, webhook use karenge
        .build()
    )

    # Register command handlers
    ptb_app.add_handler(CommandHandler("start", handlers.start))
    ptb_app.add_handler(CommandHandler("help", handlers.help_cmd))
    ptb_app.add_handler(CommandHandler("newproject", handlers.newproject))
    ptb_app.add_handler(CommandHandler("myprojects", handlers.myprojects))
    ptb_app.add_handler(CommandHandler("openproject", handlers.openproject))
    ptb_app.add_handler(CommandHandler("deleteproject", handlers.deleteproject_cmd))
    ptb_app.add_handler(CommandHandler("renameproject", handlers.renameproject))
    ptb_app.add_handler(CommandHandler("cloneproject", handlers.cloneproject))
    ptb_app.add_handler(CommandHandler("addfile", handlers.addfile))
    ptb_app.add_handler(CommandHandler("editfile", handlers.editfile))
    ptb_app.add_handler(CommandHandler("deletefile", handlers.deletefile_cmd))
    ptb_app.add_handler(CommandHandler("listfiles", handlers.listfiles))
    ptb_app.add_handler(CommandHandler("viewfile", handlers.viewfile))
    ptb_app.add_handler(CommandHandler("renamefile", handlers.renamefile))
    ptb_app.add_handler(CommandHandler("preview", handlers.preview))
    ptb_app.add_handler(CommandHandler("deploy", handlers.deploy))
    ptb_app.add_handler(CommandHandler("exportzip", handlers.exportzip))
    ptb_app.add_handler(CommandHandler("templates", handlers.templates_cmd))
    ptb_app.add_handler(CommandHandler("storage", handlers.storage))
    ptb_app.add_handler(CommandHandler("status", handlers.status))
    ptb_app.add_handler(CommandHandler("admin", handlers.admin_stats))

    # Callback + Message handlers (last me)
    ptb_app.add_handler(CallbackQueryHandler(handlers.callback_handler))
    ptb_app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handlers.handle_message)
    )

    # Init + start bot
    await ptb_app.initialize()
    await ptb_app.start()

    # Set webhook if URL present
    if config.WEBHOOK_URL:
        webhook_url = f"{config.WEBHOOK_URL}/webhook/{config.WEBHOOK_SECRET}"
        await ptb_app.bot.set_webhook(
            webhook_url,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )
        log.info(f"✅ Webhook set: {webhook_url}")
    else:
        log.warning("⚠️ WEBHOOK_URL not set — bot won't receive updates")

    log.info("🚀 Bot started successfully")

    yield  # app running

    # Shutdown
    log.info("🛑 Shutting down bot...")
    try:
        if config.WEBHOOK_URL:
            await ptb_app.bot.delete_webhook()
        await ptb_app.stop()
        await ptb_app.shutdown()
    except Exception as e:
        log.error(f"Shutdown error: {e}")


# ---------------- FASTAPI APP ----------------
app = FastAPI(
    title="WebBuilder Bot",
    description="Telegram bot that builds websites",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------- WEBHOOK ENDPOINT ----------------
@app.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Telegram sends updates here."""
    if secret != config.WEBHOOK_SECRET:
        log.warning(f"❌ Invalid webhook secret: {secret}")
        return Response(status_code=403)

    if ptb_app is None:
        return Response(status_code=503)

    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        log.exception(f"Webhook processing error: {e}")

    return {"ok": True}


@app.get("/health")
async def health():
    """Health check for Render / UptimeRobot."""
    return {
        "status": "ok",
        "bot": "running" if ptb_app else "stopped",
    }


# ---------------- MOUNT WEB ROUTES ----------------
# web/app.py ke routes (/, /preview/{pid}, /s/{pid})
app.mount("/", web)


# ---------------- LOCAL RUN ----------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=False,
        log_level="info",
    )
