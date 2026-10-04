from bot.config import INSTA_LINK, DEV_USERNAME

def get_base_wrapper(title: str, content: str, css_custom: str = "") -> str:
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
            --card-bg: rgba(255, 255, 255, 0.04);
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
            flex-direction: column;
            justify-content: space-between;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
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
            margin-bottom: 16px;
        }}
        p {{ color: var(--muted); line-height: 1.6; margin-bottom: 20px; }}
        .btn {{
            display: inline-block;
            padding: 12px 24px;
            background: var(--gradient);
            color: #fff;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
        }}
        footer {{
            text-align: center;
            margin-top: 40px;
            color: var(--muted);
            font-size: 0.85rem;
        }}
        footer a {{ color: #a855f7; text-decoration: none; font-weight: 600; }}
        {css_custom}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
    <footer>
        Deployed via <b>Web-with-chikuu</b> | Built by <a href="{INSTA_LINK}" target="_blank">{DEV_USERNAME}</a>
    </footer>
</body>
</html>"""

def get_template_files(p_type: str, name: str) -> dict:
    p_type = p_type.lower()
    if p_type == "portfolio":
        html = get_base_wrapper(
            f"{name} - Portfolio",
            f"<h1>Hello, I'm {name} 👋</h1><p>Welcome to my personal developer portfolio site.</p><a href='#contact' class='btn'>Get In Touch</a>"
        )
    elif p_type == "blog":
        html = get_base_wrapper(
            f"{name} Blog",
            f"<h1>{name} Tech Blog</h1><p>Articles on web engineering and automation bots.</p><a href='#read' class='btn'>Read Latest Post</a>"
        )
    elif p_type == "landing":
        html = get_base_wrapper(
            f"{name} Product",
            f"<h1>Launch Your Next App Fast</h1><p>High converting landing page generated via Telegram Bot.</p><a href='#buy' class='btn'>Get Started Free</a>"
        )
    elif p_type == "ecommerce":
        html = get_base_wrapper(
            f"{name} Store",
            f"<h1>Welcome to {name} Store 🛒</h1><p>Premium Digital Products Marketplace.</p><a href='#shop' class='btn'>Browse Products</a>"
        )
    elif p_type == "admin":
        html = get_base_wrapper(
            f"{name} Admin Panel",
            f"<h1>Dashboard Overview</h1><p>System metrics and project management stats.</p><a href='#stats' class='btn'>View Analytics</a>"
        )
    else:  # Custom default
        html = get_base_wrapper(
            name,
            f"<h1>Welcome to {name}</h1><p>Edit this site easily using <code>/addfile</code> or <code>/editfile</code>.</p>"
        )

    css = "/* Add your custom styles here */\nbody { background-color: #0b0f19; }"
    js = "// Add your custom scripts here\nconsole.log('Web-with-chikuu site loaded');"

    return {
        "index.html": html,
        "style.css": css,
        "script.js": js
    }
