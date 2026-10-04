from motor.motor_asyncio import AsyncIOMotorClient
from bot.config import MONGO_URI

client = AsyncIOMotorClient(MONGO_URI)
db = client["web_builder_db"]
projects_collection = db["projects"]

async def create_project(user_id: int, project_id: str, name: str, p_type: str, initial_content: str):
    doc = {
        "user_id": user_id,
        "project_id": project_id,
        "name": name,
        "type": p_type,
        "files": {
            "index.html": initial_content,
            "style.css": "body { font-family: sans-serif; background: #0b0f19; color: #fff; }"
        }
    }
    await projects_collection.insert_one(doc)

async def get_project(project_id: str):
    return await projects_collection.find_one({"project_id": project_id})
