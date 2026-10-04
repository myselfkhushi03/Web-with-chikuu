import zipfile
import io
from bot.database import get_project

async def create_project_zip(project_id: str) -> io.BytesIO:
    project = await get_project(project_id)
    if not project or "files" not in project:
        return None
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_name, content in project["files"].items():
            zip_file.writestr(file_name, content)
            
    zip_buffer.seek(0)
    return zip_buffer
