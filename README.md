# 🚀 WebBuilder Bot

Telegram bot jo kisi bhi type ki website bana, edit, aur deploy kar sakta hai — sab Telegram se, bina laptop kholne ke.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green)

---

## ✨ Features

- 🎨 **Multi-file projects** — HTML, CSS, JS, JSON, MD, kuch bhi
- 📦 **5 ready templates** — portfolio, blog, landing, ecommerce, admin
- 🎯 **Inline buttons UI** — full aesthetic experience
- 👁 **Live preview URL** — instant link generate
- 🚀 **Deploy to public URL** — shareable link
- 📥 **ZIP export** — poora project download
- 🗂 **File CRUD** — add, edit, delete, rename files
- 🎭 **Clone projects** — duplicate with one command
- 💾 **Storage tracking** — kitna use hua
- 🔐 **Admin panel** — stats + broadcast
- 🌐 **Webhook mode** — Render-compatible
- ⚡ **Async** — fast responses

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Bot | `python-telegram-bot` v21 |
| Web | `FastAPI` + `uvicorn` |
| Database | `MongoDB Atlas` (motor async) |
| Hosting | `Render.com` (free tier) |
| Language | Python 3.11+ |

---

## 📁 Project Structure

```
web-builder-bot/
├── main.py                 # Entry point (FastAPI + bot)
├── bot/
│   ├── __init__.py
│   ├── config.py           # Env vars + constants
│   ├── handlers.py         # All command handlers
│   ├── keyboards.py        # Inline keyboards
│   ├── database.py         # MongoDB operations
│   ├── filemanager.py      # File operations
│   ├── templates.py        # Website templates
│   └── utils.py            # Helpers (escape, size)
├── web/
│   ├── __init__.py
│   ├── app.py              # FastAPI routes
│   └── static/
├── requirements.txt
├── render.yaml
├── .env.example
└── README.md
```

---

## 🚀 Quick Deploy (5 Steps)

### 1️⃣ Bot banao
- Telegram me `@BotFather` kholo
- `/newbot` bhejo → naam do → **token copy** karo

### 2️⃣ MongoDB Atlas setup
- https://cloud.mongodb.com pe free account
- **Free cluster** banao (M0)
- **Database Access** → new user (username + password yaad rakho)
- **Network Access** → `0.0.0.0/0` add karo (allow all)
- **Connect → Drivers** → connection string copy karo
- `<password>` ki jagah apna password daalo
- End me `/webbuilder` add kar do (database name)

Example:
```
mongodb+srv://user:pass@cluster0.abc12.mongodb.net/webbuilder?retryWrites=true&w=majority
```

### 3️⃣ GitHub push
```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/USERNAME/web-builder-bot.git
git push -u origin main
```

### 4️⃣ Render deploy
- https://render.com → **New** → **Web Service**
- GitHub repo connect karo
- Settings:
  - **Name:** `webbuilder-bot`
  - **Region:** `Singapore` (India ke liye best)
  - **Branch:** `main`
  - **Build Command:** `pip install -r requirements.txt`
  - **Start Command:** `python main.py`
  - **Plan:** `Free`
  - **Health Check Path:** `/health`
- **Environment Variables** add karo (niche dekho)
- **Create Web Service** click karo

### 5️⃣ UptimeRobot (keep-alive)
- Render free tier **15 min inactivity** pe sleep ho jata hai
- https://uptimerobot.com pe free account banao
- **Add Monitor** → HTTP(s)
- URL: `https://your-app.onrender.com/health`
- Interval: **5 minutes**
- Save → bot 24x7 alive rahega

---

## 🔐 Environment Variables

Render → **Environment** tab me ye daalo:

| Key | Value | Kaha se |
|-----|-------|---------|
| `BOT_TOKEN` | `7123456789:AAH...` | @BotFather |
| `MONGO_URI` | `mongodb+srv://...` | MongoDB Atlas |
| `WEBHOOK_URL` | `https://your-app.onrender.com` | Render (deploy ke baad) |
| `WEBHOOK_SECRET` | `webbuilder_secret_2025_a8f3k2m9x7p4` | Fixed (koi bhi random) |
| `ADMIN_ID` | `123456789` | @userinfobot |
| `PORT` | `10000` | Fixed |

⚠️ `WEBHOOK_URL` me **trailing slash `/` mat lagana**

---

## 📖 Commands Guide

### 🎯 Project Commands

| Command | Description |
|---------|-------------|
| `/start` | Bot start karo |
| `/help` | Full command list |
| `/newproject <name> <type>` | Naya project banao |
| `/myprojects` | Apne saare projects dekho |
| `/openproject <id>` | Project kholo (file menu) |
| `/deleteproject <id>` | Project delete karo |
| `/renameproject <id> <new>` | Project rename |
| `/cloneproject <id>` | Duplicate project |

### 📄 File Commands

| Command | Description |
|---------|-------------|
| `/listfiles <id>` | Saari files dekho |
| `/addfile <id> <file>` | Nayi file add karo |
| `/editfile <id> <file>` | File content edit karo |
| `/deletefile <id> <file>` | File delete karo |
| `/viewfile <id> <file>` | File content dekho |
| `/renamefile <id> <old> <new>` | File rename karo |

### 🌐 Preview & Deploy

| Command | Description |
|---------|-------------|
| `/preview <id>` | Live preview link lo |
| `/deploy <id>` | Public deploy URL lo |
| `/exportzip <id>` | Poora project ZIP me |

### 🎨 Templates

| Command | Description |
|---------|-------------|
| `/templates` | Ready templates list |
| `/newproject <name> portfolio` | Portfolio template |
| `/newproject <name> blog` | Blog template |
| `/newproject <name> landing` | Landing page |
| `/newproject <name> ecommerce` | E-commerce |
| `/newproject <name> admin` | Admin dashboard |

### ⚙️ Utility

| Command | Description |
|---------|-------------|
| `/storage` | Storage usage |
| `/status` | Bot status |
| `/admin` | Admin stats (sirf admin) |

---

## 🎨 Project Types

| Type | Description |
|------|-------------|
| `portfolio` | Personal portfolio site |
| `blog` | Blog layout |
| `landing` | Product landing page |
| `ecommerce` | Shop with products |
| `admin` | Admin dashboard |
| `custom` | Blank starter (editable) |

---

## 💡 Usage Example

```
1. /newproject MyPortfolio portfolio
   → Project ban gaya: WEB-A3F9K2

2. /listfiles WEB-A3F9K2
   → index.html, style.css

3. /editfile WEB-A3F9K2 index.html
   → Naya content bhejo
   → File save ho gayi ✅

4. /preview WEB-A3F9K2
   → https://your-app.onrender.com/preview/WEB-A3F9K2

5. /deploy WEB-A3F9K2
   → https://your-app.onrender.com/s/WEB-A3F9K2

6. /exportzip WEB-A3F9K2
   → ZIP download
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Bot reply nahi karta | `/health` check karo, logs dekho |
| Webhook error | `WEBHOOK_URL` me trailing slash hatao |
| MongoDB error | IP whitelist me `0.0.0.0/0` add karo |
| MarkdownV2 error | `esc()` function use hua? |
| Port error | `PORT=10000` set karo |
| 404 preview | `project_id` sahi hai? |
| Bot sleep ho raha | UptimeRobot setup karo |

---

## 📊 Limits

| Limit | Free Tier |
|-------|-----------|
| Max projects per user | 5 |
| Max file size | 5 MB |
| Max project size | 50 MB |
| Storage | ~500 MB |

---

## 🔧 Local Development

```bash
# Clone
git clone https://github.com/USERNAME/web-builder-bot.git
cd web-builder-bot

# Venv
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows

# Install
pip install -r requirements.txt

# Env
cp .env.example .env
# .env edit karo — BOT_TOKEN, MONGO_URI, etc.

# Run
python main.py
```

Bot locally chalega `http://localhost:10000` pe.

---

## 🚀 Deployment URLs

Deploy hone ke baad ye URLs milega:

| URL | Purpose |
|-----|---------|
| `https://your-app.onrender.com/` | Landing page |
| `https://your-app.onrender.com/health` | Health check |
| `https://your-app.onrender.com/preview/{pid}` | Live preview |
| `https://your-app.onrender.com/s/{pid}` | Deployed site |
| `https://your-app.onrender.com/webhook/{secret}` | Telegram webhook |

---

## 🛡️ Security

- ✅ Webhook secret token verification
- ✅ Owner-only project access
- ✅ File size limits (DoS prevention)
- ✅ No arbitrary code execution
- ✅ MongoDB injection-safe queries
- ✅ MarkdownV2 escape for XSS prevention

---

## 📝 License

MIT License — free to use, modify, distribute.

---

## 🤝 Contributing

1. Fork karo
2. Feature branch banao (`git checkout -b feature/amazing`)
3. Commit karo (`git commit -m 'Add amazing feature'`)
4. Push karo (`git push origin feature/amazing`)
5. Pull Request bhejo

---

## 💬 Support

- Telegram: @yourusername
- Issues: [GitHub Issues](https://github.com/USERNAME/web-builder-bot/issues)

---

## ⭐ Credits

Built with ❤️ using:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [FastAPI](https://fastapi.tiangolo.com/)
- [MongoDB](https://www.mongodb.com/)
- [Render](https://render.com/)

---

**🚀 Happy Building!**
