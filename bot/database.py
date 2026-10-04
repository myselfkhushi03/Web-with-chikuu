from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import random, string
from bot.config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,  # 5 sec me fail hoga, hang nahi
    connectTimeoutMS=5000
)
db = client[DB_NAME]
users_col = db.users
projects_col = db.projects

def gen_project_id() -> str:
    return "WEB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

async def get_user(user_id: int):
    return await users_col.find_one({"user_id": user_id})

async def create_user(user_id: int, username: str, first_name: str):
    try:
        user = await get_user(user_id)
        if user:
            return user
        user = {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "joined_at": datetime.utcnow(),
            "projects": [],
            "storage_used": 0,
            "is_premium": False,
            "is_banned": False,
        }
        await users_col.insert_one(user)
        return user
    except Exception as e:
        print(f"DB Error create_user: {e}")
        # Fallback taaki bot reply to de
        return {
            "user_id": user_id,
            "username": username or "",
            "first_name": first_name or "",
            "projects": [],
            "storage_used": 0,
            "is_premium": False,
        }

# ... baaki functions same rakho ...
async def create_project(owner_id: int, name: str, ptype: str, files: dict):
    pid = gen_project_id()
    while await projects_col.find_one({"project_id": pid}):
        pid = gen_project_id()
    files_arr = [{"name": k, "content": v, "size": len(v.encode())} for k, v in files.items()]
    total_size = sum(f["size"] for f in files_arr)
    project = {
        "project_id": pid,
        "owner_id": owner_id,
        "name": name,
        "type": ptype,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "files": files_arr,
        "is_public": True,
        "views": 0,
        "deploy_url": None,
    }
    await projects_col.insert_one(project)
    await users_col.update_one(
        {"user_id": owner_id},
        {"$push": {"projects": pid}, "$inc": {"storage_used": total_size}}
    )
    return project

async def get_project(pid: str):
    return await projects_col.find_one({"project_id": pid})

async def get_user_projects(user_id: int):
    cursor = projects_col.find({"owner_id": user_id}).sort("created_at", -1)
    return await cursor.to_list(length=100)

async def update_project(pid: str, update: dict):
    update["updated_at"] = datetime.utcnow()
    await projects_col.update_one({"project_id": pid}, {"$set": update})

async def delete_project(pid: str):
    p = await get_project(pid)
    if not p:
        return
    size = sum(f["size"] for f in p["files"])
    await projects_col.delete_one({"project_id": pid})
    await users_col.update_one(
        {"user_id": p["owner_id"]},
        {"$pull": {"projects": pid}, "$inc": {"storage_used": -size}}
    )

async def increment_views(pid: str):
    await projects_col.update_one({"project_id": pid}, {"$inc": {"views": 1}})

async def get_stats():
    total_users = await users_col.count_documents({})
    total_projects = await projects_col.count_documents({})
    return {"users": total_users, "projects": total_projects}
