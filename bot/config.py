import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip('/').strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "chikuu_default_secret_999").strip()

# Clean MONGO_URI from unwanted quotes or trailing spaces
MONGO_URI = os.getenv("MONGO_URI", "").strip().strip('"').strip("'")

PORT = int(os.getenv("PORT", 10000))
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

DEV_USERNAME = "@myselfkhushi03"
INSTA_LINK = "https://instagram.com/myselfkhushi03"
GITHUB_ISSUES = "https://github.com/myselfkhushi03/web-builder-bot/issues"

MAX_PROJECTS_PER_USER = 5
MAX_FILE_SIZE = 500 * 1024  # 500 KB limit per file
MAX_TOTAL_STORAGE = 10 * 1024 * 1024  # 10 MB per user limit
