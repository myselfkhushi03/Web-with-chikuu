import os
import json
import random
import string
import time
from datetime import datetime

# ================= CONFIG =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITES_DIR = os.path.join(BASE_DIR, "sites")
SITES_FILE = os.path.join(BASE_DIR, "sites.json")
MAX_FILE_SIZE_MB = 50  # safety limit

os.makedirs(SITES_DIR, exist_ok=True)

# ================= CORE UTILS =================
def load_json(path):
    """Safely load json"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except:
        return {}

def save_json(path, data):
    """Safely save json"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[SAVE_ERROR] {e}")
        return False

def new_id(length=8):
    """Generate aesthetic + strong unique ID"""
    # first char always letter to look cool
    first = random.choice(string.ascii_lowercase)
    rest = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length-1))
    final_id = first + rest
    
    # ensure not duplicate
    sites = load_json(SITES_FILE)
    if final_id in sites:
        return new_id(length)
    return final_id

def get_file_size_mb(path):
    if not os.path.exists(path):
        return 0
    return os.path.getsize(path) / (1024*1024)

def create_site_entry(owner_id, file_name, folder_path):
    """Create pro metadata entry"""
    return {
        "owner": str(owner_id),
        "file": file_name,
        "views": 0,
        "created_at": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "timestamp": int(time.time()),
        "size": f"{get_file_size_mb(folder_path):.2f} MB" if os.path.isfile(folder_path) else "N/A",
        "is_zip": file_name.lower().endswith(".
