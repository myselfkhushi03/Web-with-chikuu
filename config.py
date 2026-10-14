import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "webify_db")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8080")
PORT = int(os.getenv("PORT", 8080))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
HOSTED_SITES_DIR = "hosted_sites"

os.makedirs(HOSTED_SITES_DIR, exist_ok=True)
os.makedirs("qr_storage", exist_ok=True)
os.makedirs("temp_uploads", exist_ok=True)
