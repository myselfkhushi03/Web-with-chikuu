import psutil
from aiogram import Router, F
from aiogram.types import Message
from database import users_collection, sites_collection
from config import ADMIN_IDS

router = Router()

@router.message(F.text == "/admin", F.from_user.id.in_(ADMIN_IDS))
async def admin_dashboard(message: Message):
    total_users = await users_collection.count_documents({})
    total_sites = await sites_collection.count_documents({})
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent

    text = (
        f"👑 **ΛDΜIИ DΛSΗBΘΛRD** 👑\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"📂 Hosted Sites: `{total_sites}`\n"
        f"💻 CPU Usage: `{cpu_usage}%`\n"
        f"🧠 RAM Usage: `{ram_usage}%`\n"
    )
    await message.answer(text, parse_mode="Markdown")
