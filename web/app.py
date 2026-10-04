from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from bot.database import get_project

fastapi_app = FastAPI(title="Web Service Engine")

@fastapi_app.get("/", response_class=HTMLResponse)
async def home():
    return "<h1>Web Builder Engine Online</h1>"

# Ye wala route add karein UptimeRobot ping ke liye
@fastapi_app.get("/health")
async def health():
    return {"status": "active", "message": "Bot server is running fast"}

@fastapi_app.get("/preview/{project_id}", response_class=HTMLResponse)
@fastapi_app.get("/s/{project_id}", response_class=HTMLResponse)
async def serve_project(project_id: str):
    project = await get_project(project_id)
    if not project or "files" not in project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project["files"].get("index.html", "<h1>Empty Project</h1>")
