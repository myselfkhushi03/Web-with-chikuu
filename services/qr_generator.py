import os
import uuid
import qrcode
from PIL import Image, ImageOps

QR_DIR = "qr_storage"
os.makedirs(QR_DIR, exist_ok=True)

def generate_aesthetic_qr(url: str, style_type: str = "Neon Dark Theme") -> str:
    qr_id = str(uuid.uuid4())[:8]
    file_path = os.path.join(QR_DIR, f"qr_{qr_id}.png")

    qr = qrcode.QRCode(
        version=4,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    if style_type == "Neon Dark Theme":
        img = qr.make_image(fill_color="#38bdf8", back_color="#0f172a").convert('RGB')
    elif style_type == "Rounded Dot Gradient":
        img = qr.make_image(fill_color="#6366f1", back_color="#ffffff").convert('RGB')
    else:
        img = qr.make_image(fill_color="#000000", back_color="#ffffff").convert('RGB')

    img = ImageOps.expand(img, border=20, fill='white' if style_type != "Neon Dark Theme" else '#0f172a')
    img.save(file_path)
    return file_path
