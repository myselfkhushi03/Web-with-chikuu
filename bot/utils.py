def esc(text: str) -> str:
    """MarkdownV2 safe escaping helper"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)
