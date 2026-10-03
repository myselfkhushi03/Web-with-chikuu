import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "changeme")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

DB_NAME = "webbuilder_bot"

MAX_PROJECTS_FREE = 5
MAX_FILE_SIZE = 5 * 1024 * 1024       # 5 MB
MAX_PROJECT_SIZE = 50 * 1024 * 1024   # 50 MB

DEFAULT_FILES = {
    "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My Website</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>Hello World 🚀</h1>
  <p>Built with WebBuilder Bot</p>
  <script src="script.js"></script>
</body>
</html>""",
    "style.css": """* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: system-ui, sans-serif;
  background: linear-gradient(135deg, #667eea, #764ba2);
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: white;
  text-align: center;
}
h1 { font-size: 3rem; }""",
    "script.js": """console.log("Website loaded 🚀");"""
}
