from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_project_menu_keyboard(project_id: str):
    keyboard = [
        [
            InlineKeyboardButton("📄 List Files", callback_data=f"list_{project_id}"),
            InlineKeyboardButton("👁️ Preview", callback_data=f"prev_{project_id}")
        ],
        [InlineKeyboardButton("🚀 Deploy Link", callback_data=f"dep_{project_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)
