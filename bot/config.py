import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/')
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "super_secret_webhook_token_123")
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.getenv("PORT", 10000))
DEV_USERNAME = "@myselfkhushi03"
INSTA_LINK = "https://instagram.com/myselfkhushi03"
