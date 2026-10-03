import os
import requests
from web_app import app

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")

if __name__ == "__main__":
    # Webhook set karo - polling nahi chalega
    if BOT_TOKEN and BASE_URL:
        try:
            webhook_url = f"{BASE_URL}/webhook/{BOT_TOKEN}"
            r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
            print(f"Webhook set: {r.text}")
        except Exception as e:
            print(f"Webhook error: {e}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
