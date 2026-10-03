import os, json, time, random, string

DATA_DIR = "/data" if os.path.exists("/data") else "."
SITES_DIR = os.path.join(DATA_DIR, "sites")
os.makedirs(SITES_DIR, exist_ok=True)
SITES_FILE = os.path.join(DATA_DIR, "sites.json")

def load_json(f):
    try: return json.load(open(f,"r"))
    except: return {}

def save_json(f,d):
    json.dump(d, open(f,"w"), indent=2)

def gen_id(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def create_site(owner_id, custom=None):
    site_id = custom.lower().replace(" ","-") if custom else gen_id()
    path = os.path.join(SITES_DIR, site_id)
    if os.path.exists(path):
        return None, "❌ Ye naam already hai, dusra naam try kar /create se"
    os.makedirs(path, exist_ok=True)
    sites = load_json(SITES_FILE)
    sites[site_id] = {"owner":owner_id,"created":time.time(),"views":0,"files":[],"password":None}
    save_json(SITES_FILE, sites)
    return site_id, path

def add_file_to_site(site_id, filename):
    sites = load_json(SITES_FILE)
    if site_id in sites and filename not in sites[site_id]["files"]:
        sites[site_id]["files"].append(filename)
        save_json(SITES_FILE, sites)

def get_user_sites(user_id):
    sites = load_json(SITES_FILE)
    return {k:v for k,v in sites.items() if v["owner"]==user_id}

def make_gallery_html(site_id, files):
    items = ""
    for f in files:
        if f == "index.html" or f.startswith("_"): continue
        ext = f.split('.')[-1].lower()
        if ext in ['jpg','jpeg','png','webp','gif']:
            items += f'<div class="rounded-[18px] overflow-hidden shadow"><img src="/site/{site_id}/{f}" class="w-full h-64 object-cover"><p class="p-2 text-xs bg-white">{f}</p></div>'
        elif ext in ['mp4','mov']:
            items += f'<div class="rounded-[18px] overflow-hidden bg-black"><video src="/site/{site_id}/{f}" controls class="w-full h-64"></video></div>'
        else:
            items += f'<a href="/site/{site_id}/{f}" class="p-4 rounded-2xl bg-white border block">📄 {f}</a>'
    html = f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="bg-[#FFF0F5] p-6"><div class="max-w-6xl mx-auto">
    <h1 class="text-3xl font-bold">💖 {site_id}</h1>
    <p class="text-zinc-500">{len(files)} files • File-to-Web Bot</p>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">{items}</div></div></body></html>"""
    with open(os.path.join(SITES_DIR, site_id, "index.html"), "w", encoding="utf-8") as fw:
        fw.write(html)
