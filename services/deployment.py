import os
import shutil
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from config import HOSTED_SITES_DIR

app = FastAPI(title="Webify Hosting Engine")

# Mount static hosting directory securely
app.mount("/s", StaticFiles(directory=HOSTED_SITES_DIR), name="hosted_sites")

FORBIDDEN_EXTENSIONS = {".py", ".exe", ".sh", ".php", ".bat", ".scr", ".js.map"}

def sanitize_and_extract(file_path: str, extract_to: str) -> str:
    os.makedirs(extract_to, exist_ok=True)
    if zipfile.is_zipfile(file_path):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                ext = os.path.splitext(filename)[1].lower()
                if ext in FORBIDDEN_EXTENSIONS:
                    raise HTTPException(status_code=400, detail=f"Malicious file type blocked: {ext}")
            zip_ref.extractall(extract_to)
    else:
        dest_file = os.path.join(extract_to, "index.html")
        shutil.copy(file_path, dest_file)

    index_path = os.path.join(extract_to, "index.html")
    if not os.path.exists(index_path):
        found = False
        for root, dirs, files in os.walk(extract_to):
            if "index.html" in files:
                for f in files:
                    shutil.move(os.path.join(root, f), extract_to)
                found = True
                break
        if not found:
            with open(index_path, "w", encoding="utf-8") as f:
                f.write("""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Webify Hosted Site</title>
<style>body{background:#0f172a;color:#f8fafc;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
.card{background:#1e293b;padding:2rem;border-radius:1rem;box-shadow:0 10px 25px -5px rgba(0,0,0,0.3);text-align:center;}
h1{color:#38bdf8;margin-bottom:0.5rem;}</style></head>
<body><div class="card"><h1>✨ Hosted via Webify Bot ✨</h1><p>Your static site was deployed successfully!</p></div></body></html>""")
    return extract_to

@app.get("/")
async def root():
    return {"status": "online", "service": "Webify Dynamic Hosting Engine"}
