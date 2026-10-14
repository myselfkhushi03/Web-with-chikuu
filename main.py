"""
main.py — Single async entrypoint for Webify Bot.

One process, one event loop, one port:
    * FastAPI serves the landing page, /health, the Telegram webhook and every
      hosted site at /s/<slug>/ (plus custom domains via the Host header).
    * The Telegram bot runs on the same loop — via webhook when a public https
      URL is available (Render), otherwise via long polling.

Run:  python main.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Optional

import aiohttp
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent, Update
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

import config
from database import db
from handlers import admin as admin_handlers
from handlers import user as user_handlers
from middlewares import AccessMiddleware
from services import deployment as dep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("webify")

bot: Optional[Bot] = None
dp: Optional[Dispatcher] = None
_tasks: set[asyncio.Task] = set()   # strong references to background tasks


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return task


# --------------------------------------------------------------------------- #
# Bot / dispatcher construction
# --------------------------------------------------------------------------- #
def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.outer_middleware(AccessMiddleware())
    dispatcher.callback_query.outer_middleware(AccessMiddleware())

    # Order matters: admin first, then the non-admin guard, then regular users.
    dispatcher.include_router(admin_handlers.router)
    dispatcher.include_router(admin_handlers.guard_router)
    dispatcher.include_router(user_handlers.router)

    @dispatcher.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Unhandled error while processing update", exc_info=event.exception)
        return True

    return dispatcher


async def _set_commands(b: Bot) -> None:
    await b.set_my_commands([
        BotCommand(command="start", description="Open the dashboard"),
        BotCommand(command="new", description="Publish a new website"),
        BotCommand(command="mysites", description="Manage your websites"),
        BotCommand(command="profile", description="Your plan and stats"),
        BotCommand(command="help", description="How it works"),
        BotCommand(command="cancel", description="Cancel the current action"),
    ])


async def _keep_alive_loop() -> None:
    """Ping our own public /health so Render doesn't put the service to sleep."""
    url = f"{config.BASE_URL}/health"
    await asyncio.sleep(60)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
        while True:
            try:
                async with session.get(url) as resp:
                    log.debug("keep-alive %s -> %s", url, resp.status)
            except Exception as exc:
                log.warning("keep-alive ping failed: %s", exc)
            await asyncio.sleep(config.KEEP_ALIVE_INTERVAL)


# --------------------------------------------------------------------------- #
# FastAPI app + lifespan
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot, dp
    config.validate()
    config.ensure_dirs()
    await db.connect()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = build_dispatcher()
    me = await bot.get_me()
    log.info("Bot authorised as @%s", me.username)
    await _set_commands(bot)

    polling_task: Optional[asyncio.Task] = None
    if config.USE_WEBHOOK:
        await bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        log.info("Webhook mode: %s/webhook/<secret>", config.BASE_URL)
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        polling_task = _spawn(
            dp.start_polling(bot, handle_signals=False,
                             allowed_updates=dp.resolve_used_update_types())
        )
        log.info("Long-polling mode")

    if config.KEEP_ALIVE:
        _spawn(_keep_alive_loop())

    log.info("Webify Bot is up on %s:%s (public: %s)", config.HOST, config.PORT, config.BASE_URL)
    try:
        yield
    finally:
        log.info("Shutting down…")
        if polling_task is not None:
            try:
                await dp.stop_polling()
            except Exception:
                pass
            try:
                await asyncio.wait_for(polling_task, timeout=10)
            except Exception:
                polling_task.cancel()
        for t in list(_tasks):
            t.cancel()
        try:
            await bot.session.close()
        except Exception:
            pass
        await db.close()


app = FastAPI(title="Webify Bot", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
_LANDING = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Webify</title>
<style>*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#e9ecff;padding:24px;
background:radial-gradient(1100px 600px at 15% 0%,#3a2a8a 0%,transparent 60%),
radial-gradient(900px 500px at 100% 100%,#0b6b8a 0%,transparent 55%),#0b0f1f}
main{max-width:520px;text-align:center;padding:44px 32px;border-radius:26px;background:rgba(255,255,255,.06);
border:1px solid rgba(255,255,255,.12);box-shadow:0 20px 60px rgba(0,0,0,.45)}
h1{margin:0 0 10px;font-size:2.2rem}p{color:#aab1d6;line-height:1.55}
.pill{display:inline-block;margin-top:16px;padding:8px 16px;border-radius:999px;background:linear-gradient(90deg,#6a11cb,#2575fc);color:#fff;font-size:.9rem}
</style></head><body><main><h1>✨ Webify</h1>
<p>Publish websites straight from Telegram — send an HTML file, a ZIP or paste code and get a live link in seconds.</p>
<span class="pill">🟢 Online</span></main></body></html>"""


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def landing(request: Request):
    host = request.headers.get("host", "").split(":")[0].lower()
    if host and host != config.MAIN_HOST and host not in ("localhost", "127.0.0.1"):
        site = await db.get_site_by_domain(host)
        if site:
            return await dep.serve_site_path(request, site, "")
    return HTMLResponse(_LANDING)


@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.post(config.WEBHOOK_PATH, include_in_schema=False)
async def telegram_webhook(request: Request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.WEBHOOK_SECRET:
        return Response(status_code=403)
    if bot is None or dp is None:
        return Response(status_code=503)
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
    except Exception:
        return Response(status_code=400)

    async def process() -> None:
        try:
            await dp.feed_update(bot, update)
        except Exception:
            log.exception("update processing failed")

    _spawn(process())     # ack immediately; Telegram retries on slow responses
    return Response(status_code=200)


# Hosted sites: /s/<slug>/...
app.include_router(dep.router)


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def custom_domain_router(request: Request, full_path: str):
    """Serve sites mapped to custom domains / subdomains by Host header."""
    host = request.headers.get("host", "").split(":")[0].lower()
    if host and host != config.MAIN_HOST:
        site = await db.get_site_by_domain(host)
        if site:
            return await dep.serve_site_path(request, site, full_path)
    return dep.message_page("404", "Page not found.", 404)


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
async def main() -> None:
    config.validate()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.HOST,
            port=config.PORT,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
    )
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass