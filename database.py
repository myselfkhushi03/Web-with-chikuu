from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME
from datetime import datetime

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users_collection = db["users"]
sites_collection = db["sites"]
qr_collection = db["qr_codes"]

async def init_indexes():
    await users_collection.create_index("telegram_id", unique=True)
    await sites_collection.create_index("site_id", unique=True)
    await sites_collection.create_index("slug", unique=True)
    await qr_collection.create_index("qr_id", unique=True)

async def get_or_create_user(telegram_id: int, username: str = None):
    user = await users_collection.find_one({"telegram_id": telegram_id})
    if not user:
        user = {
            "telegram_id": telegram_id,
            "username": username or f"user_{telegram_id}",
            "tier": "Free",
            "joined_at": datetime.utcnow(),
            "custom_domain_prefix": f"site-{telegram_id}"
        }
        await users_collection.insert_one(user)
    return user
