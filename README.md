# ✨ Webify Bot

Publish websites from Telegram. Send an `.html` file, a `.zip` or paste code and get a live
link at `https://<your-app>.onrender.com/s/<slug>/` — plus offline, scanner-safe QR codes,
file manager, analytics, VIP tier, and a full admin panel.

One process, one port: **FastAPI** (static hosting + webhook) and **aiogram 3** (bot) share a
single asyncio loop; data lives in **MongoDB (Motor)**.

## Project layout

```
config.py                 environment + limits + security allow/deny lists
database.py               Motor client, indexes, CRUD helpers
ui.py                     aesthetic texts + inline keyboards
middlewares.py            user registration + ban enforcement
services/deployment.py    sanitiser, ZIP extractor, static hosting router
services/qr_generator.py  Pillow QR styles + scan pre-flight validation
handlers/user.py          user commands, FSM flows, callbacks
handlers/admin.py         dashboard, moderation, broadcast engine
main.py                   FastAPI + bot entrypoint
requirements.txt  Procfile  .python-version  render.yaml  .env.example
```

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `BOT_TOKEN` | ✅ | from @BotFather |
| `MONGO_URI` | ✅ | MongoDB Atlas connection string |
| `ADMIN_IDS` | recommended | comma-separated Telegram IDs allowed to use `/admin` |
| `RENDER_EXTERNAL_URL` | auto | Render sets it; used for links, webhook and QR codes |
| `PORT` | auto | Render sets it (default 8080) |
| `DATA_DIR` | optional | storage root; use your disk mount (`/var/data`) on Render |
| `USE_WEBHOOK` | optional | default: webhook on https hosts, polling otherwise |
| `KEEP_ALIVE` | optional | self-ping `/health` every 10 min (default on for https hosts) |
| `WILDCARD_DOMAIN` | optional | lets VIPs pick `prefix.<domain>` subdomains |

## Deploy on Render (24/7 Web Service)

1. **MongoDB**: create a free Atlas cluster → Database Access user → Network Access allow
   `0.0.0.0/0` (Render IPs change) → copy the connection string into `MONGO_URI`.
2. **Bot**: create a bot in @BotFather, copy the token into `BOT_TOKEN`. Get your numeric ID
   from @userinfobot and put it in `ADMIN_IDS`.
3. **Push** this folder to a GitHub repository.
4. On Render: **New → Web Service** → connect the repo.
   * Runtime: **Python 3** · Build: `pip install -r requirements.txt` · Start: `python main.py`
   * Health check path: `/health`
   * Environment: add `BOT_TOKEN`, `MONGO_URI`, `ADMIN_IDS`, `PYTHON_VERSION=3.11.9`
   * Or use **New → Blueprint** to import `render.yaml` automatically.
5. **Persistent storage (important):** Render's filesystem is wiped on every deploy/restart
   unless you attach a **Disk** (paid plans). Add a disk mounted at `/var/data` and set
   `DATA_DIR=/var/data`. Without a disk, hosted sites disappear on redeploy (the database
   keeps the records, the files are gone).
6. Deploy. Logs should show `Webhook mode: https://…/webhook/<secret>`. Open the bot, send `/start`.

**Keeping it awake:** Free web services sleep after ~15 minutes without inbound traffic.
`KEEP_ALIVE` (on by default) pings the public `/health` URL every 10 minutes; for extra
reliability also add a free UptimeRobot/cron-job.org monitor on `https://<app>.onrender.com/health`.
Webhook mode also wakes the service when a Telegram update arrives.

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then export the variables (or use your shell / direnv)
export BOT_TOKEN=... MONGO_URI=... ADMIN_IDS=...
python main.py              # no https URL → automatic long polling; sites at http://localhost:8080/s/<slug>/
```
(QR codes embed `RENDER_EXTERNAL_URL`; locally they point to `http://localhost:8080`, which phones can't reach.)

## Feature notes

* **Deploy**: `.html`, `.zip` (auto-extract; missing `index.html` → modern default page; a single
  wrapper folder is flattened) or pasted code (snippets are wrapped into a full page).
* **Security**: whitelist of static types only; `.py .exe .sh .php .bat …` refused; ZIP traversal,
  symlinks, hidden files and zip-bombs handled; path + extension re-checked on every request;
  SVGs are served sandboxed; per-tier size/file limits.
* **QR codes**: `qrcode` + Pillow, offline. Plain `https://` payload, ECC-H, 4-module quiet
  zone, dark-on-light modules (even in the Neon theme the scan panel is light, because payment
  apps often fail on inverted codes), optional logo (<5 % of area), contrast check on every render.
  If OpenCV happens to be installed, a round-trip decode is added to the scan report.
* **Custom domains (VIP)**: point a CNAME at your Render hostname *and* add the domain in
  Render's *Custom Domains*; the bot then serves the site by `Host` header.
* **Admin**: `/admin` → live CPU/RAM/disk, users, sites (lock / unlock / delete), user ban / VIP,
  broadcast (as-is, HTML or Markdown) with a live progress badge.

## Known limitations (read before going public)

* All hosted sites share one origin (`/s/<slug>/`), so JavaScript on one site could read another
  site's `localStorage`/cookies. Fine for personal use; for a public multi-tenant service serve
  each site on its own (sub)domain (use `WILDCARD_DOMAIN`) and consider a CSP.
* FSM state is in memory (`MemoryStorage`): half-finished flows reset on restart.
* Telegram bots can download files up to 20 MB, which caps uploads.