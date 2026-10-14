import asyncio
import uvicorn
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, PORT
from database import init_indexes
from services.deployment import app as fastapi_app
from handlers.user import router as user_router
from handlers.admin import router as admin_router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(user_router)
dp.include_router(admin_router)

@fastapi_app.on_event("startup")
async def startup_event():
    await init_indexes()

async def run_telegram_polling():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_telegram_polling())
    uvicorn.run(fastapi_app, host="0.0.0.0", port=PORT)
