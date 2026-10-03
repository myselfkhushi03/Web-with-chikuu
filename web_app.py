import os
from flask import Flask, send_from_directory, request, jsonify
from utils import SITES_DIR

web_app = Flask(__name__)

SITE_PASSWORDS = {}
SITE_METADATA = {}

@web_app.route('/')
def home():
    return "<h1>🚀 Advance Site Maker Server is Live!</h1>"

@web_app.route('/site/<site_code>/')
@web_app.route('/site/<site_code>/<path:filename>')
def serve_site(site_code, filename="index.html"):
    site_path = os.path.join(SITES_DIR, site_code)
    
    if not os.path.exists(site_path):
        return "<h1 style='color:red;text-align:center;'>404: Website Not Found</h1>", 404

    # Password Protection Lock
    if site_code in SITE_PASSWORDS:
        provided_pass = request.args.get('pass')
        if provided_pass != SITE_PASSWORDS[site_code]:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Protected</title></head>
            <body style='background:#0f172a; color:white; font-family:sans-serif; text-align:center; padding-top:100px;'>
                <h2>🔒 Password Protected Website</h2>
                <form method="GET">
                    <input type="password" name="pass" placeholder="Enter Password" style='padding:10px;'>
                    <button type="submit" style='padding:10px 20px;'>Unlock</button>
                </form>
            </body>
            </html>
            """, 401

    # Update Visit Stats
    if site_code in SITE_METADATA:
        SITE_METADATA[site_code]["visits"] += 1
    else:
        SITE_METADATA[site_code] = {"visits": 1}

    return send_from_directory(site_path, filename)
