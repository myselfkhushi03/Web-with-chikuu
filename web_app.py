from flask import Flask, send_from_directory, request
import os
from utils import SITES_DIR, SITES_FILE, load_json, save_json

web = Flask(__name__)

@web.route('/')
def home():
    return """<body style="font-family:sans-serif;background:#FFF0F5;text-align:center;padding:50px">
    <h1>File-to-Web Bot Alive</h1><p>Telegram me file bhej, link banega</p></body>"""

@web.route('/site/<site_id>')
@web.route('/site/<site_id>/')
def serve_index(site_id):
    sites = load_json(SITES_FILE)
    if site_id not in sites:
        return "Site not found", 404

    if sites[site_id].get("password"):
        pwd = request.args.get("pwd")
        if pwd!= sites[site_id]["password"]:
            return """
            <body style="background:#FFF0F5;display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif">
            <form style="background:white;padding:30px;border-radius:20px;text-align:center">
            <h2>🔒 Protected</h2>
            <input name="pwd" type="password" placeholder="Password" style="padding:10px;border-radius:10px;border:1px solid #ddd">
            <br><button style="margin-top:10px;background:black;color:white;padding:10px 20px;border-radius:20px">Unlock</button>
            </form></body>
            """

    sites[site_id]["views"] += 1
    save_json(SITES_FILE, sites)
    base = os.path.join(SITES_DIR, site_id)
    if os.path.exists(os.path.join(base, "index.html")):
        return send_from_directory(base, "index.html")
    files = os.listdir(base)
    if files:
        return send_from_directory(base, files[0])
    return "Empty"

@web.route('/site/<site_id>/<path:filename>')
def serve_file(site_id, filename):
    return send_from_directory(os.path.join(SITES_DIR, site_id), filename)
