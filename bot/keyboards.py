from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_kb():
    keyboard = [
        [InlineKeyboardButton("➕ New Project", callback_data="menu_new"), InlineKeyboardButton("📁 My Projects", callback_data="menu_list")],
        [InlineKeyboardButton("🎨 Templates", callback_data="menu_templates"), InlineKeyboardButton("📊 Storage Usage", callback_data="menu_storage")],
        [InlineKeyboardButton("❓ Help & Commands", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def projects_list_kb(projects):
    keyboard = []
    for p in projects:
        keyboard.append([InlineKeyboardButton(f"🌐 {p['name']} ({p['project_id']})", callback_data=f"open_{p['project_id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="menu_back")])
    return InlineKeyboardMarkup(keyboard)

def project_menu_kb(project_id: str):
    keyboard = [
        [InlineKeyboardButton("📄 File List", callback_data=f"file_{project_id}"), InlineKeyboardButton("➕ Add File", callback_data=f"addf_{project_id}")],
        [InlineKeyboardButton("👁️ Preview", callback_data=f"prev_{project_id}"), InlineKeyboardButton("🚀 Deploy Link", callback_data=f"deploy_{project_id}")],
        [InlineKeyboardButton("✏️ Rename Project", callback_data=f"renp_{project_id}"), InlineKeyboardButton("📥 Export ZIP", callback_data=f"zip_{project_id}")],
        [InlineKeyboardButton("🗑️ Delete Project", callback_data=f"delp_{project_id}")],
        [InlineKeyboardButton("🔙 Projects List", callback_data="menu_list")]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_delete_kb(project_id: str):
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Delete", callback_data=f"confdel_{project_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"open_{project_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def files_list_kb(project_id: str, files: dict):
    keyboard = []
    for fname in files.keys():
        keyboard.append([
            InlineKeyboardButton(f"📄 {fname}", callback_data=f"view_{project_id}_{fname}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{project_id}_{fname}"),
            InlineKeyboardButton("🗑️", callback_data=f"delf_{project_id}_{fname}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 Project Menu", callback_data=f"open_{project_id}")])
    return InlineKeyboardMarkup(keyboard)

def file_actions_kb(project_id: str, filename: str):
    keyboard = [
        [InlineKeyboardButton("📥 Download File", callback_data=f"dl_{project_id}_{filename}"), InlineKeyboardButton("✏️ Rename File", callback_data=f"ren_{project_id}_{filename}")],
        [InlineKeyboardButton("🗑️ Delete File", callback_data=f"delf_{project_id}_{filename}")],
        [InlineKeyboardButton("🔙 Back to Files", callback_data=f"file_{project_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def templates_kb():
    keyboard = [
        [InlineKeyboardButton("Portfolio", callback_data="tpl_portfolio"), InlineKeyboardButton("Blog", callback_data="tpl_blog")],
        [InlineKeyboardButton("Landing Page", callback_data="tpl_landing"), InlineKeyboardButton("E-commerce", callback_data="tpl_ecommerce")],
        [InlineKeyboardButton("Admin Dashboard", callback_data="tpl_admin")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="menu_back")]
    ]
    return InlineKeyboardMarkup(keyboard)
