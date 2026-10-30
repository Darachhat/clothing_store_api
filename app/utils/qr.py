"""QR code and barcode generation utilities."""
from __future__ import annotations

import io

import qrcode
import qrcode.image.svg

from app.core.config import settings


def generate_qr_png(reference: str, size: int = 10) -> bytes:
    """Generate a QR code as PNG bytes."""
    url = f"{settings.NUXT_PUBLIC_STORE_DOMAIN}/p/{reference}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_svg(reference: str) -> bytes:
    """Generate a QR code as SVG bytes."""
    url = f"{settings.NUXT_PUBLIC_STORE_DOMAIN}/p/{reference}"
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.make(url, image_factory=factory)

    buffer = io.BytesIO()
    qr.save(buffer)
    return buffer.getvalue()


def generate_barcode_png(barcode_value: str, write_text: bool = False) -> bytes:
    """Generate a Code128 barcode as PNG bytes."""
    import barcode as python_barcode
    from barcode.writer import ImageWriter

    clean_val = (barcode_value or "SKU").strip()
    code128 = python_barcode.get("code128", clean_val, writer=ImageWriter())
    buffer = io.BytesIO()
    code128.write(
        buffer,
        options={
            "write_text": write_text,
            "module_width": 0.28,
            "module_height": 9.0,
            "quiet_zone": 1.5,
            "font_size": 7,
            "text_distance": 2.0,
        },
    )
    return buffer.getvalue()


def generate_barcode_svg(barcode_value: str, write_text: bool = True) -> bytes:
    """Generate a Code128 barcode as SVG bytes."""
    import barcode as python_barcode
    from barcode.writer import SVGWriter

    clean_val = (barcode_value or "SKU").strip()
    code128 = python_barcode.get("code128", clean_val, writer=SVGWriter())
    buffer = io.BytesIO()
    code128.write(
        buffer,
        options={
            "write_text": write_text,
            "module_width": 0.3,
            "module_height": 10.0,
            "quiet_zone": 2.0,
            "font_size": 8,
            "text_distance": 3.0,
        },
    )
    return buffer.getvalue()
