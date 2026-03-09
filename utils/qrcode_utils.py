import qrcode
from PIL import Image
import io
import base64


def generate_qr(data: str, size: int = 200) -> bytes:
    """Generate a QR code image as PNG bytes."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def qr_to_base64(data: str, size: int = 200) -> str:
    """Return a base64-encoded PNG string for embedding in HTML."""
    png_bytes = generate_qr(data, size)
    return base64.b64encode(png_bytes).decode()


def qr_download_button(mat_id: str, nom: str, app_url: str = ""):
    """Return PNG bytes ready for st.download_button."""
    label = f"ID: {mat_id}\n{nom}"
    if app_url:
        content = f"{app_url}?mat_id={mat_id}"
    else:
        content = f"ERGO-STOCK:{mat_id}"
    return generate_qr(content, size=300)
