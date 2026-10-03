from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.templates import list_templates


def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 New Project", callback_data="menu_new"),
         InlineKeyboardButton("📁 My Projects", callback_data="menu_list")],
        [InlineKeyboardButton("🎨 Templates", callback_data="menu_templates"),
         InlineKeyboardButton("💾 Storage", callback_data="menu_storage")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")],
    ])


def project_menu(pid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Files", callback_data=f"files_{pid}"),
         InlineKeyboardButton("👁 Preview", callback_data=f"prev_{pid}")],
        [InlineKeyboardButton("➕ Add File", callback_data=f"addf_{pid}"),
         InlineKeyboardButton("🌐 Deploy", callback_data=f"deploy_{pid}")],
        [InlineKeyboardButton("📥 Download ZIP", callback_data=f"zip_{pid}"),
         InlineKeyboardButton("✏️ Rename", callback_data=f"renp_{pid}")],
        [InlineKeyboardButton("🗑 Delete Project", callback_data=f"delp_{pid}"),
         InlineKeyboardButton("⬅️ Back", callback_data="menu_list")],
    ])


def confirm_delete(pid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confdel_{pid}"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"open_{pid}")]
    ])


def file_actions(pid: str, fname: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{pid}_{fname}"),
         InlineKeyboardButton("👁 View", callback_data=f"view_{pid}_{fname}")],
        [InlineKeyboardButton("📥 Download", callback_data=f"dl_{pid}_{fname}"),
         InlineKeyboardButton("📝 Rename", callback_data=f"ren_{pid}_{fname}")],
        [InlineKeyboardButton("🗑 Delete", callback_data=f"delf_{pid}_{fname}"),
         InlineKeyboardButton("⬅️ Back", callback_data=f"files_{pid}")],
    ])


def projects_list(projects: list):
    buttons = []
    for p in projects[:10]:
        buttons.append([InlineKeyboardButton(
            f"📁 {p['name']} ({p['project_id']})",
            callback_data=f"open_{p['project_id']}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)


def files_list(pid: str, files: list):
    buttons = []
    for f in files[:20]:
        buttons.append([InlineKeyboardButton(
            f"📄 {f['name']} ({f['size']} B)",
            callback_data=f"file_{pid}_{f['name']}"
        )])
    buttons.append([InlineKeyboardButton("➕ Add File", callback_data=f"addf_{pid}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"open_{pid}")])
    return InlineKeyboardMarkup(buttons)


def templates_kb():
    buttons = []
    for t in list_templates():
        buttons.append([InlineKeyboardButton(f"🎨 {t.title()}", callback_data=f"tpl_{t}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)
