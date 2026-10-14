import os
import uuid
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from database import get_or_create_user, sites_collection
from services.deployment import sanitize_and_extract, HOSTED_SITES_DIR
from config import RENDER_EXTERNAL_URL

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await get_or_create_user(message.from_user.id, message.from_user.username)
    text = (
        f"✨ **WΞBIFY DΛSΗBΘΛRD** ✨\n\n"
        f"Welcome back, **{message.from_user.first_name}**!\n"
        f"Tier: `[🟢 {user['tier']} Member]`\n\n"
        f"Deploy single HTML files or `.zip` archives instantly. Manage your sites and scale your web presence."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Deploy New Site", callback_data="deploy_menu"), InlineKeyboardButton(text="📂 My Sites", callback_data="my_sites")],
        [InlineKeyboardButton(text="👤 Profile & Stats", callback_data="profile")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "deploy_menu")
async def deploy_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚡ **WΞBIFY DΞPLΘYMΞИƬ ИЦ** ⚡\n\n"
        "Send me a `.html` file, raw HTML code, or a `.zip` archive containing your website files to deploy instantly.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Back to Dashboard", callback_data="back_home")]])
    )
    await callback.answer()

@router.message(F.document | F.text)
async def handle_deployment_or_text(message: Message):
    user_id = message.from_user.id
    site_id = str(uuid.uuid4())[:8]
    slug = f"site-{user_id}-{site_id}"
    site_dir = os.path.join(HOSTED_SITES_DIR, slug)

    temp_file_path = os.path.join("temp_uploads", f"{site_id}.tmp")
    os.makedirs("temp_uploads", exist_ok=True)

    if message.document:
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, temp_file_path)
        try:
            sanitize_and_extract(temp_file_path, site_dir)
        except Exception as e:
            await message.answer(f"❌ **Deployment Failed:** {str(e)}", parse_mode="Markdown")
            return
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    elif message.text and not message.text.startswith("/"):
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(message.text)
        try:
            sanitize_and_extract(temp_file_path, site_dir)
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        return

    live_url = f"{RENDER_EXTERNAL_URL}/s/{slug}/"
    await sites_collection.insert_one({
        "site_id": site_id,
        "owner_id": user_id,
        "slug": slug,
        "site_name": f"Site {site_id}",
        "file_path": site_dir,
        "custom_domain": "",
        "is_locked": False,
        "views_count": 0,
        "created_at": datetime.utcnow()
    })

    await message.answer(
        f"✅ **[⚡ PRΘCΞSSIИG] SUCCESS!**\n\n"
        f"Your website has been deployed successfully.\n\n"
        f"🌐 **Live URL:** {live_url}\n"
        f"🔑 **Site Slug:** `{slug}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« Back to Dashboard", callback_data="back_home")]])
    )

@router.callback_query(F.data == "back_home")
async def back_home(callback: CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()
