from bot.config import MAX_FILE_SIZE, MAX_PROJECT_SIZE


def validate_file_size(content: str) -> bool:
    return len(content.encode()) <= MAX_FILE_SIZE


def validate_project_size(files: list) -> bool:
    return sum(f["size"] for f in files) <= MAX_PROJECT_SIZE


def find_file(project: dict, filename: str):
    for f in project.get("files", []):
        if f["name"] == filename:
            return f
    return None


def add_or_update_file(project: dict, filename: str, content: str):
    size = len(content.encode())
    for f in project["files"]:
        if f["name"] == filename:
            f["content"] = content
            f["size"] = size
            return project["files"]
    project["files"].append({"name": filename, "content": content, "size": size})
    return project["files"]


def delete_file(project: dict, filename: str):
    project["files"] = [f for f in project["files"] if f["name"] != filename]
    return project["files"]


def rename_file(project: dict, old: str, new: str):
    for f in project["files"]:
        if f["name"] == old:
            f["name"] = new
    return project["files"]


def get_index_html(project: dict) -> str:
    for f in project.get("files", []):
        if f["name"] == "index.html":
            return f["content"]
    return "<h1>No index.html found</h1>"


def build_inline_bundle(project: dict) -> str:
    """Combine css/js into a single html preview."""
    html = get_index_html(project)
    for f in project.get("files", []):
        if f["name"].endswith(".css"):
            html = html.replace(
                f'<link rel="stylesheet" href="{f["name"]}">',
                f"<style>{f['content']}</style>"
            )
        if f["name"].endswith(".js"):
            html = html.replace(
                f'<script src="{f["name"]}"></script>',
                f"<script>{f['content']}</script>"
            )
    return html
