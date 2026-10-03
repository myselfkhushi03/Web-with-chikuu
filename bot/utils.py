from telegram.constants import ParseMode

MD_SPECIALS = r"_*[]()~`>#+-=|{}.!"


def esc(text) -> str:
    """Escape MarkdownV2 special characters."""
    return "".join(f"\\{c}" if c in MD_SPECIALS else c for c in str(text))


def human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes/1024:.2f} KB"
    return f"{num_bytes/(1024*1024):.2f} MB"


def md_bold(text: str) -> str:
    return f"*{esc(text)}*"


def md_code(text: str) -> str:
    return f"`{esc(text)}`"


__all__ = ["esc", "human_size", "md_bold", "md_code", "ParseMode"]
