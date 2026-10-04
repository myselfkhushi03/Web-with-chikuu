from bot.config import INSTA_LINK, DEV_USERNAME

def get_template_files(p_type: str, name: str) -> dict:
    p_type = p_type.lower()

    # Aesthetic Interactive Question Flow Template with Autoplay Music
    index_html = f"""<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} ✨</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{
            background: #0d0d15;
            color: #fff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow: hidden;
            position: relative;
        }}
        .bg-glow {{
            position: absolute;
            width: 320px;
            height: 320px;
            background: linear-gradient(135deg, #ff758c, #ff7eb3);
            filter: blur(140px);
            border-radius: 50%;
            z-index: 0;
            opacity: 0.4;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px 28px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
            z-index: 1;
            position: relative;
        }}
        h2 {{
            font-size: 1.35rem;
            font-weight: 600;
            margin-bottom: 24px;
            line-height: 1.5;
            background: linear-gradient(135deg, #ffffff, #a1a1aa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .btn {{
            display: inline-block;
            width: 100%;
            padding: 14px;
            margin-top: 12px;
            background: linear-gradient(135deg, #ff758c, #ff7eb3);
            color: #fff;
            border: none;
            border-radius: 14px;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            box-shadow: 0 8px 20px rgba(255, 117, 140, 0.3);
            transition: all 0.2s ease;
        }}
        .btn-secondary {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: none;
        }}
        .btn:active {{ transform: scale(0.97); }}
        .question-step {{ display: none; }}
        .question-step.active {{
            display: block;
            animation: fadeIn 0.5s ease-in-out;
        }}
        footer {{
            position: absolute;
            bottom: 20px;
            z-index: 1;
            font-size: 0.8rem;
            color: rgba(255,255,255,0.4);
        }}
        footer a {{ color: #ff7eb3; text-decoration: none; font-weight: 600; }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(12px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
    </style>
</head>
<body>
    <div class="bg-glow"></div>

    <!-- Hidden Audio for Background Music -->
    <audio id="bgSong" loop preload="auto">
        <source src="https://files.catbox.moe/55k4hh.mp3" type="audio/mpeg">
    </audio>

    <div class="card">
        <!-- Step 1 -->
        <div class="question-step active" id="step1">
            <h2>Aapke liye ek chota sa surprise hai... ✨</h2>
            <button class="btn" onclick="nextStep(2)">Tap to Begin 💖</button>
        </div>

        <!-- Step 2 -->
        <div class="question-step" id="step2">
            <h2>Kya aapko pata hai aap kitni special ho? 🌸</h2>
            <button class="btn" onclick="nextStep(3)">Haan, pata hai! 😄</button>
            <button class="btn btn-secondary" onclick="nextStep(3)">Nahi Toh... 🤔</button>
        </div>

        <!-- Step 3 -->
        <div class="question-step" id="step3">
            <h2>Ek question aur... Barish pasand hai ya ye song? 🌧️</h2>
            <button class="btn" onclick="nextStep(4)">Dono Hi Pasand Hain! ✨</button>
        </div>

        <!-- Final Step -->
        <div class="question-step" id="step4">
            <h2>Always stay happy and keep smiling! ❤️✨</h2>
        </div>
    </div>

    <footer>
        Made with ❤️️ via <a href="{INSTA_LINK}" target="_blank">{DEV_USERNAME}</a>
    </footer>

    <script>
        function playAudio() {{
            var audio = document.getElementById("bgSong");
            if (audio && audio.paused) {{
                audio.play().catch(function(e) {{ console.log("Audio waiting for user gesture"); }});
            }}
        }}

        function nextStep(step) {{
            playAudio();
            document.querySelectorAll('.question-step').forEach(el => el.classList.remove('active'));
            var target = document.getElementById('step' + step);
            if (target) target.classList.add('active');
        }}

        // Direct tap on screen triggers audio if not started
        document.body.addEventListener('click', playAudio, {{ once: true }});
    </script>
</body>
</html>"""

    css = "/* Aesthetic Custom Styles */\nbody { background-color: #0d0d15; }"
    js = "// Custom Interactivity Script\nconsole.log('Site initialized smoothly');"

    return {
        "index.html": index_html,
        "style.css": css,
        "script.js": js
    }
