from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from bot.database import get_project, increment_views
from bot.filemanager import build_inline_bundle

web = FastAPI(
    title="WebBuilder Preview",
    description="Live preview + deployed sites",
    version="1.0.0",
)


# ---------------- LANDING PAGE ----------------

@web.get("/", response_class=HTMLResponse)
async def root():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebBuilder Bot 🚀</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: system-ui, -apple-system, sans-serif;
    background: radial-gradient(circle at top, #1a1a2e, #0f0f0f);
    min-height: 100vh;
    display: grid;
    place-items: center;
    color: #fff;
    padding: 20px;
  }
  .card {
    text-align: center;
    padding: 60px 40px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 24px;
    backdrop-filter: blur(10px);
    max-width: 500px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  h1 { font-size: 2.5rem; margin-bottom: 12px; }
  .gradient {
    background: linear-gradient(135deg, #667eea, #764ba2, #f093fb);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  p { color: #aaa; line-height: 1.7; margin-bottom: 24px; }
  a {
    display: inline-block;
    padding: 14px 32px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff;
    text-decoration: none;
    border-radius: 50px;
    font-weight: 600;
    transition: transform 0.2s;
  }
  a:hover { transform: translateY(-3px); }
  .emoji { font-size: 4rem; margin-bottom: 20px; }
</style>
</head>
<body>
  <div class="card">
    <div class="emoji">🚀</div>
    <h1 class="gradient">WebBuilder Bot</h1>
    <p>Build, edit, and deploy websites directly from Telegram.</p>
    <a href="https://t.me/BotFather" target="_blank">Open Telegram</a>
  </div>
</body>
</html>
    """


# ---------------- HEALTH CHECK ----------------

@web.get("/health")
async def health():
    return {"status": "ok", "service": "webbuilder-preview"}


# ---------------- LIVE PREVIEW ----------------

@web.get("/preview/{pid}", response_class=HTMLResponse)
async def preview(pid: str):
    """Live preview of a project."""
    p = await get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")

    await increment_views(pid)
    html = build_inline_bundle(p)
    return HTMLResponse(content=html)


# ---------------- DEPLOYED SITE ----------------

@web.get("/s/{pid}", response_class=HTMLResponse)
async def serve(pid: str):
    """Public deployed site."""
    p = await get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="Site not found")

    if not p.get("is_public", True):
        raise HTTPException(status_code=403, detail="This site is private")

    await increment_views(pid)
    html = build_inline_bundle(p)
    return HTMLResponse(content=html)


# ---------------- 404 HANDLER ----------------

@web.exception_handler(404)
async def not_found(request, exc):
    return HTMLResponse(
        content="""
        <html><body style="font-family:sans-serif;background:#0f0f0f;color:#fff;
        display:grid;place-items:center;height:100vh;margin:0;text-align:center">
        <div>
          <h1>404 🔍</h1>
          <p>Page not found</p>
          <a href="/" style="color:#667eea">Go Home</a>
        </div>
        </body></html>
        """,
        status_code=404,
    )
