TEMPLATES = {
    "portfolio": {
        "index.html": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Portfolio</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<header><h1>John Doe</h1><p>Full Stack Developer</p></header>
<section id="about"><h2>About Me</h2><p>I build amazing websites.</p></section>
<section id="projects"><h2>Projects</h2><div class="grid">
<div class="card">Project 1</div><div class="card">Project 2</div>
</div></section>
<footer><p>© 2025 John Doe</p></footer>
</body></html>""",
        "style.css": """body{font-family:sans-serif;margin:0;background:#0f0f0f;color:#fff}
header{padding:80px 20px;text-align:center;background:linear-gradient(135deg,#667eea,#764ba2)}
h1{font-size:3rem;margin:0}section{padding:40px 20px;max-width:900px;margin:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
.card{padding:30px;background:#1a1a1a;border-radius:12px;text-align:center}
footer{text-align:center;padding:20px;background:#000}"""
    },
    "blog": {
        "index.html": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>My Blog</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<header><h1>📝 My Blog</h1></header>
<main>
<article><h2>First Post</h2><p>Welcome to my blog!</p></article>
<article><h2>Second Post</h2><p>More content coming soon.</p></article>
</main></body></html>""",
        "style.css": """body{font-family:Georgia,serif;max-width:700px;margin:auto;padding:20px;background:#fafafa}
header{text-align:center;padding:40px 0;border-bottom:2px solid #333}
article{padding:20px 0;border-bottom:1px solid #ddd}"""
    },
    "landing": {
        "index.html": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Landing</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<section class="hero"><h1>Launch Your Product 🚀</h1>
<p>The fastest way to grow</p><button>Get Started</button></section>
</body></html>""",
        "style.css": """body{margin:0;font-family:sans-serif}
.hero{min-height:100vh;display:grid;place-items:center;text-align:center;
background:linear-gradient(135deg,#00c6ff,#0072ff);color:#fff;padding:20px}
h1{font-size:3.5rem;margin:0}button{padding:14px 32px;font-size:1rem;border:none;
border-radius:30px;background:#fff;color:#0072ff;cursor:pointer;margin-top:20px}"""
    },
    "ecommerce": {
        "index.html": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Shop</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<header><h1>🛒 My Shop</h1></header>
<div class="products">
<div class="product"><h3>Product 1</h3><p>$19.99</p><button>Buy</button></div>
<div class="product"><h3>Product 2</h3><p>$29.99</p><button>Buy</button></div>
</div></body></html>""",
        "style.css": """body{margin:0;font-family:sans-serif;background:#f5f5f5}
header{padding:30px;background:#222;color:#fff;text-align:center}
.products{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
gap:20px;padding:40px;max-width:1000px;margin:auto}
.product{background:#fff;padding:20px;border-radius:10px;text-align:center}
button{padding:10px 20px;background:#222;color:#fff;border:none;border-radius:6px}"""
    },
    "admin": {
        "index.html": """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Admin</title>
<link rel="stylesheet" href="style.css"></head>
<body>
<aside><h2>⚙️ Admin</h2><nav><a>Dashboard</a><a>Users</a><a>Settings</a></nav></aside>
<main><h1>Dashboard</h1><div class="cards">
<div class="card"><h3>Users</h3><p>1,234</p></div>
<div class="card"><h3>Revenue</h3><p>$8,900</p></div>
</div></main></body></html>""",
        "style.css": """body{margin:0;font-family:sans-serif;display:flex;min-height:100vh;background:#f0f2f5}
aside{width:220px;background:#1e293b;color:#fff;padding:20px}
aside a{display:block;padding:10px;color:#cbd5e1;text-decoration:none}
main{flex:1;padding:30px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px}
.card{background:#fff;padding:20px;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.08)}"""
    }
}


def get_template(name: str):
    return TEMPLATES.get(name)


def list_templates():
    return list(TEMPLATES.keys())
