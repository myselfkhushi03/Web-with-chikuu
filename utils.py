import os
import random
import string
import zipfile

SITES_DIR = os.path.join(os.getcwd(), "user_sites")

if not os.path.exists(SITES_DIR):
    os.makedirs(SITES_DIR)

def generate_site_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def extract_zip(file_path, extract_to):
    with zipfile.ZipFile(file_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def inject_audio_script(site_path, audio_filename):
    index_path = os.path.join(site_path, "index.html")
    if os.path.exists(index_path):
        audio_script = f"""
        <audio id="bgMusic" autoplay loop hidden>
            <source src="{audio_filename}" type="audio/mpeg">
        </audio>
        <script>
            document.addEventListener('click', function() {{
                var audio = document.getElementById('bgMusic');
                if(audio) audio.play();
            }}, {{ once: true }});
        </script>
        </body>
        """
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if "bgMusic" not in content:
            content = content.replace("</body>", audio_script)
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(content)
