"""PDF label / product sticker generation for product variants with embedded Khmer Unicode TTF font."""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.utils.qr import generate_barcode_png, generate_qr_png

KHR_EXCHANGE_RATE = 4100
KHMER_STORE_HEADER = "ហាងលក់សម្លៀកបំពាក់ ភ្នំពេញ"

_KHMER_FONT_REGISTERED = False
_KHMER_FONT_REGULAR = "Helvetica"
_KHMER_FONT_BOLD = "Helvetica-Bold"


def _ensure_khmer_fonts() -> tuple[str, str]:
    """Register bundled Khmer Unicode TrueType fonts (Battambang / KhmerUI) for ReportLab PDF output."""
    global _KHMER_FONT_REGISTERED, _KHMER_FONT_REGULAR, _KHMER_FONT_BOLD
    if _KHMER_FONT_REGISTERED:
        return _KHMER_FONT_REGULAR, _KHMER_FONT_BOLD

    fonts_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    reg_path = fonts_dir / "Battambang-Regular.ttf"
    bold_path = fonts_dir / "KhmerUI-Bold.ttf"

    try:
        if reg_path.exists():
            pdfmetrics.registerFont(TTFont("KhmerBattambang", str(reg_path)))
            _KHMER_FONT_REGULAR = "KhmerBattambang"
            _KHMER_FONT_BOLD = "KhmerBattambang"
        if bold_path.exists():
            pdfmetrics.registerFont(TTFont("KhmerUIBold", str(bold_path)))
            _KHMER_FONT_BOLD = "KhmerUIBold"
    except Exception:
        _KHMER_FONT_REGULAR = "Helvetica"
        _KHMER_FONT_BOLD = "Helvetica-Bold"

    _KHMER_FONT_REGISTERED = True
    return _KHMER_FONT_REGULAR, _KHMER_FONT_BOLD


@dataclass
class LabelData:
    brand_name: str
    product_name: str
    sku: str
    barcode: str | None
    color_name: str | None
    size_name: str | None
    selling_price: Decimal
    qr_reference: str


def _truncate_text(c: canvas.Canvas, text: str, font_name: str, font_size: float, max_width: float) -> str:
    """Truncate text with ellipsis so it fits within max_width points."""
    if not text:
        return ""
    if c.stringWidth(text, font_name, font_size) <= max_width:
        return text
    ellipsis = "..."
    trimmed = text
    while trimmed and c.stringWidth(trimmed + ellipsis, font_name, font_size) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else text[:8]


def _draw_single_sticker(
    c: canvas.Canvas,
    label: LabelData,
    x: float,
    y: float,
    label_w: float,
    label_h: float,
    draw_border: bool = True,
    code_type: str = "BARCODE",
    show_khr: bool = True,
) -> None:
    """
    Draw Template C: Modern Khmer Product Sticker inside (x, y, label_w, label_h).
    Supports 50x30mm (default), 40x30mm, and 60x40mm sizes.
    """
    kh_reg, kh_bold = _ensure_khmer_fonts()

    is_large = label_w >= 58 * mm and label_h >= 38 * mm
    is_compact = label_w <= 42 * mm

    pad_x = (2.8 if is_large else (1.8 if is_compact else 2.2)) * mm
    pad_y = (2.2 if is_large else 1.6) * mm
    inner_w = max(10 * mm, label_w - 2 * pad_x)

    if draw_border:
        c.setStrokeColor(colors.HexColor("#D1D5DB"))
        c.setLineWidth(0.4)
        c.roundRect(x, y, label_w, label_h, radius=1.2 * mm, stroke=1, fill=0)

    # 1. Top Store Header: ហាងលក់សម្លៀកបំពាក់ ភ្នំពេញ
    store_fs = 6.5 if is_large else (5.0 if is_compact else 5.5)
    top_y = y + label_h - pad_y - store_fs
    store_title = label.brand_name.strip() if label.brand_name and label.brand_name != "Clothing Store" else KHMER_STORE_HEADER
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont(kh_bold, store_fs)
    c.drawString(
        x + pad_x,
        top_y,
        _truncate_text(c, store_title, kh_bold, store_fs, inner_w),
    )

    # Subtle header divider
    div_y = top_y - 1.2 * mm
    c.setStrokeColor(colors.HexColor("#E5E7EB"))
    c.setLineWidth(0.3)
    c.line(x + pad_x, div_y, x + label_w - pad_x, div_y)

    # 2. Product Name (Khmer / English) + Price on right
    prod_fs = 8.0 if is_large else (6.2 if is_compact else 7.0)
    price_fs = 10.5 if is_large else (8.2 if is_compact else 9.2)
    usd_price_str = f"${float(label.selling_price):.2f}"
    khr_val = int(round(float(label.selling_price) * KHR_EXCHANGE_RATE))
    khr_price_str = f"{khr_val:,} ៛"

    # Measure price width so product name never overlaps price
    c.setFont("Helvetica-Bold", price_fs)
    price_w = c.stringWidth(usd_price_str, "Helvetica-Bold", price_fs) + 2.5 * mm
    prod_max_w = max(12 * mm, inner_w - price_w)

    row1_y = div_y - (3.2 if is_large else 2.6) * mm
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont(kh_bold, prod_fs)
    c.drawString(
        x + pad_x,
        row1_y,
        _truncate_text(c, label.product_name or label.sku, kh_bold, prod_fs, prod_max_w),
    )

    # Price right-aligned
    c.setFont("Helvetica-Bold", price_fs)
    c.drawRightString(x + label_w - pad_x, row1_y - 0.5, usd_price_str)

    # 3. SKU row + optional KHR price on right
    meta_fs = 6.0 if is_large else (4.8 if is_compact else 5.2)
    row2_y = row1_y - (3.0 if is_large else 2.4) * mm
    c.setFillColor(colors.HexColor("#374151"))
    c.setFont("Helvetica", meta_fs)
    c.drawString(
        x + pad_x,
        row2_y,
        _truncate_text(c, f"SKU: {label.sku}", "Helvetica", meta_fs, prod_max_w),
    )

    if show_khr:
        c.setFillColor(colors.HexColor("#4B5563"))
        c.setFont(kh_reg, meta_fs)
        c.drawRightString(x + label_w - pad_x, row2_y, khr_price_str)

    # 4. Khmer Color & Size row: ពណ៌: ខ្មៅ   ទំហំ: ៤០
    row3_y = row2_y - (3.0 if is_large else 2.4) * mm
    color_val = label.color_name or "—"
    size_val = label.size_name or "—"
    variant_line = f"ពណ៌: {color_val}    ទំហំ: {size_val}"
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont(kh_reg, meta_fs)
    c.drawString(
        x + pad_x,
        row3_y,
        _truncate_text(c, variant_line, kh_reg, meta_fs, inner_w),
    )

    # 5. Bottom Barcode (Code 128) + Human-readable SKU below barcode
    code_mode = (code_type or "BARCODE").upper()
    encoded_code = label.barcode or label.sku

    sku_text_fs = 6.0 if is_large else (5.0 if is_compact else 5.5)
    sku_text_y = y + pad_y
    bc_bottom_y = sku_text_y + (2.3 if is_large else 1.9) * mm
    bc_avail_h = max(5.0 * mm, (row3_y - 1.0 * mm) - bc_bottom_y)

    if code_mode == "QR":
        qr_bytes = generate_qr_png(label.qr_reference or encoded_code, size=4)
        qr_reader = ImageReader(io.BytesIO(qr_bytes))
        qr_sz = min(bc_avail_h + 1.5 * mm, 12.0 * mm)
        c.drawImage(
            qr_reader,
            x + (label_w - qr_sz) / 2,
            sku_text_y + 1.8 * mm,
            width=qr_sz,
            height=qr_sz,
            preserveAspectRatio=True,
            mask="auto",
        )
    else:
        bc_bytes = generate_barcode_png(encoded_code, write_text=False)
        bc_reader = ImageReader(io.BytesIO(bc_bytes))
        bc_h = min(11.0 * mm if is_large else 7.8 * mm, bc_avail_h)
        bc_w = inner_w * 0.92
        c.drawImage(
            bc_reader,
            x + (label_w - bc_w) / 2,
            bc_bottom_y,
            width=bc_w,
            height=bc_h,
            preserveAspectRatio=True,
            mask="auto",
        )

    # Human-readable SKU centered at the bottom of the sticker
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", sku_text_fs)
    c.drawCentredString(x + label_w / 2, sku_text_y, encoded_code)


def generate_labels_pdf(
    labels: list[LabelData],
    paper_size: str = "THERMAL_50x30",
    label_width_mm: float = 50.0,
    label_height_mm: float = 30.0,
    columns: int = 1,
    code_type: str = "BARCODE",
    show_khr: bool = True,
) -> bytes:
    """Generate a PDF with Khmer product stickers for thermal label rolls or A4/A5 sheets."""
    buffer = io.BytesIO()
    label_w = max(25.0, float(label_width_mm)) * mm
    label_h = max(18.0, float(label_height_mm)) * mm

    mode = (paper_size or "THERMAL_50x30").upper()

    # Thermal single-sticker roll mode (50x30mm, 40x30mm, 60x40mm, 58mm, 80mm)
    if (
        mode in ("THERMAL_ROLL", "THERMAL_50X30", "THERMAL_40X30", "THERMAL_60X40", "CUSTOM_58MM", "CUSTOM_80MM")
        or columns == 1
    ):
        if mode == "CUSTOM_58MM":
            page_w = 58.0 * mm
        elif mode == "CUSTOM_80MM":
            page_w = 80.0 * mm
        else:
            page_w = label_w

        page_h = label_h
        c = canvas.Canvas(buffer, pagesize=(page_w, page_h))
        offset_x = max(0.0, (page_w - label_w) / 2.0)

        for idx, label in enumerate(labels):
            if idx > 0:
                c.showPage()
            _draw_single_sticker(
                c=c,
                label=label,
                x=offset_x,
                y=0.0,
                label_w=label_w,
                label_h=label_h,
                draw_border=(page_w > label_w),
                code_type=code_type,
                show_khr=show_khr,
            )

        if not labels:
            c.showPage()
        c.save()
        return buffer.getvalue()

    # Sheet Grid Mode (A4 / A5)
    page_size = A5 if mode == "A5" else A4
    c = canvas.Canvas(buffer, pagesize=page_size)

    page_width, page_height = page_size
    margin = 8 * mm
    col_gap = 3 * mm
    row_gap = 3 * mm

    fit_cols = max(1, int((page_width - 2 * margin + col_gap) // (label_w + col_gap)))
    max_cols = max(1, min(int(columns or fit_cols), fit_cols))

    total_grid_w = max_cols * label_w + (max_cols - 1) * col_gap
    start_x = max(margin, (page_width - total_grid_w) / 2.0)

    col = 0
    row = 0

    for label in labels:
        x = start_x + col * (label_w + col_gap)
        y = page_height - margin - (row + 1) * label_h - row * row_gap

        if y < margin:
            c.showPage()
            col, row = 0, 0
            x = start_x
            y = page_height - margin - label_h

        _draw_single_sticker(
            c=c,
            label=label,
            x=x,
            y=y,
            label_w=label_w,
            label_h=label_h,
            draw_border=True,
            code_type=code_type,
            show_khr=show_khr,
        )

        col += 1
        if col >= max_cols:
            col = 0
            row += 1

    c.save()
    return buffer.getvalue()
