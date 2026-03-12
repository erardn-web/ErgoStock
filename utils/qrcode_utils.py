import qrcode
from qrcode.image.pil import PilImage
from PIL import Image
import io

# Brother DK-11221 : étiquette carrée 23mm x 23mm
# À 300 DPI : 23mm * 300 / 25.4 = 272 pixels
DK11221_PX  = 272   # pixels à 300 DPI
DK11221_DPI = 300


def generate_qr(data: str, size: int = DK11221_PX) -> bytes:
    """
    Génère un QR code carré adapté aux étiquettes Brother DK-11221 (23x23mm).
    Retourne les bytes PNG à 300 DPI.
    """
    qr = qrcode.QRCode(
        version=None,          # taille automatique
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,              # marge minimale (4 modules requis par spec, réduit ici pour maximiser la taille)
    )
    qr.add_data(data)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Redimensionner exactement à 272x272 px (23mm à 300 DPI)
    img = img.resize((DK11221_PX, DK11221_PX), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(DK11221_DPI, DK11221_DPI))
    buf.seek(0)
    return buf.getvalue()


def generate_qr_label(mat_id: str, nom: str) -> bytes:
    """
    Génère une étiquette complète pour DK-11221 avec QR code + texte tronqué.
    Le QR code occupe la majorité de l'espace, le nom est en dessous en petit.
    """
    from PIL import ImageDraw, ImageFont

    LABEL_PX = DK11221_PX  # 272px carré

    # QR code sur ~80% de la hauteur
    qr_size = int(LABEL_PX * 0.80)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(f"ERGO-STOCK:{mat_id}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

    # Canvas blanc
    label = Image.new("RGB", (LABEL_PX, LABEL_PX), "white")
    # Centrer le QR en haut
    offset_x = (LABEL_PX - qr_size) // 2
    label.paste(qr_img, (offset_x, 0))

    # Texte en bas
    draw = ImageDraw.Draw(label)
    text = nom[:18] if len(nom) > 18 else nom  # tronquer si trop long
    font_size = 14
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (LABEL_PX - text_w) // 2
    text_y = qr_size + 2
    draw.text((text_x, text_y), text, fill="black", font=font)

    buf = io.BytesIO()
    label.save(buf, format="PNG", dpi=(DK11221_DPI, DK11221_DPI))
    buf.seek(0)
    return buf.getvalue()
