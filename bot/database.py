import sys
from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import MONGO_URI, MAX_PROJECTS_PER_USER

# Sanitize and validate MONGO_URI string
clean_uri = (MONGO_URI or "").strip().strip('"').strip("'")

if not clean_uri:
    print("❌ ERROR: MONGO_URI is empty or not set in Environment Variables!", file=sys.stderr)
    # Default fallback to prevent immediate crash if variable is missing
    clean_uri = "mongodb://localhost:27017"

try:
    client = AsyncIOMotorClient(clean_uri)
    db = client["web_builder_chikuu"]
    projects_collection = db["projects"]
except Exception as e:
    print(f"❌ MongoDB Connection Initialization Error: {e}", file=sys.stderr)

async def create_project(user_id: int, project_id: str, name: str, p_type: str, initial_files: dict) -> bool:
    count = await projects_collection.count_documents({"user_id": user_id})
    if count >= MAX_PROJECTS_PER_USER:
        return False
    doc = {
        "user_id": user_id,
        "project_id": project_id,
        "name": name,
        "type": p_type,
        "is_public": True,
        "files": initial_files
    }
    await projects_collection.insert_one(doc)
    return True

async def get_project(project_id: str):
    return await projects_collection.find_one({"project_id": project_id})

async def get_user_projects(user_id: int):
    cursor = projects_collection.find({"user_id": user_id})
    return await cursor.to_list(length=100)

async def update_project_file(project_id: str, filename: str, content: str):
    await projects_collection.update_one(
        {"project_id": project_id},
        {"$set": {f"files.{filename}": content}}
    )

async def delete_project_file(project_id: str, filename: str):
    await projects_collection.update_one(
        {"project_id": project_id},
        {"$unset": {f"files.{filename}": ""}}
    )

async def rename_project_file(project_id: str, old_filename: str, new_filename: str):
    project = await get_project(project_id)
    if not project or old_filename not in project.get("files", {}):
        return False
    content = project["files"][old_filename]
    await projects_collection.update_one(
        {"project_id": project_id},
        {
            "$unset": {f"files.{old_filename}": ""},
            "$set": {f"files.{new_filename}": content}
        }
    )
    return True

async def delete_project_db(project_id: str, user_id: int):
    return await projects_collection.delete_one({"project_id": project_id, "user_id": user_id})

async def rename_project_db(project_id: str, new_name: str):
    await projects_collection.update_one(
        {"project_id": project_id},
        {"$set": {"name": new_name}}
    )

async def get_user_storage_size(user_id: int) -> int:
    projects = await get_user_projects(user_id)
    total_bytes = 0
    for p in projects:
        for f_name, f_content in p.get("files", {}).items():
            total_bytes += len(f_content.encode("utf-8"))
    return total_bytes

async def get_stats():
    total_projects = await projects_collection.count_documents({})
    users = await projects_collection.distinct("user_id")
    return len(users), total_projects
