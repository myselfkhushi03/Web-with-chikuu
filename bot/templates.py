from bot.config import INSTA_LINK, DEV_USERNAME

def get_aesthetic_html(title: str, body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.08);
            --gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --text: #f8fafc;
            --muted: #94a3b8;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }}
        .card {{
            width: 100%;
            max-width: 800px;
            background: var(--card-bg);
            border: 1px solid var(--border);
            backdrop-filter: blur(16px);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }}
        h1 {{
            font-size: 2.5rem;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .footer a {{ color: #a855f7; text-decoration: none; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <div>{body_content}</div>
        <div class="footer">
            <span>Built via Web Builder Bot</span>
            <span>Created by <a href="{INSTA_LINK}" target="_blank">{DEV_USERNAME}</a></span>
        </div>
    </div>
</body>
</html>"""
