"""
middlewares.py — Registers every user on first contact and blocks banned users.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

import config
from database import db

log = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user_doc = await db.upsert_user(tg_user.id, tg_user.username or "")
        data["db_user"] = user_doc

        if user_doc.get("is_banned") and tg_user.id not in config.ADMIN_IDS:
            text = "🚫 <b>Access denied.</b> Your account has been banned."
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 You are banned.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(text)
            except Exception:  # never let a ban notice crash the pipeline
                log.debug("could not notify banned user %s", tg_user.id)
            return None
        return await handler(event, data)