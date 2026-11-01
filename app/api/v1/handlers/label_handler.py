"""Label generation API endpoint."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.repositories.product_repository import ProductVariantRepository
from app.schemas.base_schema import BASE_SCHEMA
from app.utils.labels import LabelData, generate_labels_pdf

router = APIRouter(prefix="/labels", tags=["Labels"])


class LabelVariantRequest(BASE_SCHEMA):
    variant_id: UUID
    quantity: int = Field(ge=1, le=500)


class LabelGenerateRequest(BASE_SCHEMA):
    variants: list[LabelVariantRequest]
    paper_size: str = "THERMAL_50x30"
    label_width_mm: float = 50.0
    label_height_mm: float = 30.0
    columns: int = 1
    code_type: str = "BARCODE"  # "BARCODE" | "QR"
    show_khr: bool = True
    store_name_override: str | None = None


@router.get("/presets")
async def list_label_presets(
    _: User = Depends(require_permission("product.read")),
) -> list[dict]:
    """Return standard garment sticker and sheet presets."""
    return [
        {
            "id": "THERMAL_50x30",
            "name": "Thermal Sticker Roll — 50 × 30 mm (Default)",
            "paper_size": "THERMAL_50x30",
            "label_width_mm": 50.0,
            "label_height_mm": 30.0,
            "columns": 1,
        },
        {
            "id": "THERMAL_40x30",
            "name": "Thermal Sticker Roll — 40 × 30 mm (Compact)",
            "paper_size": "THERMAL_40x30",
            "label_width_mm": 40.0,
            "label_height_mm": 30.0,
            "columns": 1,
        },
        {
            "id": "THERMAL_60x40",
            "name": "Thermal Sticker Roll — 60 × 40 mm (Large)",
            "paper_size": "THERMAL_60x40",
            "label_width_mm": 60.0,
            "label_height_mm": 40.0,
            "columns": 1,
        },
        {
            "id": "A4",
            "name": "A4 Sticker Sheet (Grid — 4 Columns • 48 × 30 mm)",
            "paper_size": "A4",
            "label_width_mm": 48.0,
            "label_height_mm": 30.0,
            "columns": 4,
        },
        {
            "id": "A5",
            "name": "A5 Sticker Sheet (Grid — 3 Columns • 45 × 28 mm)",
            "paper_size": "A5",
            "label_width_mm": 45.0,
            "label_height_mm": 28.0,
            "columns": 3,
        },
    ]


@router.post("/generate")
@router.post("/download", include_in_schema=False)
async def generate_labels(
    body: LabelGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> Response:
    """Generate a PDF with QR code or Code128 barcode stickers for selected variants."""
    repo = ProductVariantRepository(db)
    labels: list[LabelData] = []

    for item in body.variants:
        variant = await repo.get_by_id(item.variant_id)
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variant {item.variant_id} not found",
            )

        brand_or_store = (
            body.store_name_override.strip()
            if body.store_name_override and body.store_name_override.strip()
            else "ហាងលក់សម្លៀកបំពាក់ ភ្នំពេញ"
        )

        label = LabelData(
            brand_name=brand_or_store,
            product_name=variant.product.name if variant.product else variant.sku,
            sku=variant.sku,
            barcode=variant.barcode,
            color_name=variant.color.name if variant.color else None,
            size_name=variant.size.name if variant.size else None,
            selling_price=variant.selling_price,
            qr_reference=variant.qr_reference,
        )
        labels.extend([label] * item.quantity)

    pdf_bytes = generate_labels_pdf(
        labels=labels,
        paper_size=body.paper_size,
        label_width_mm=body.label_width_mm,
        label_height_mm=body.label_height_mm,
        columns=body.columns,
        code_type=body.code_type,
        show_khr=body.show_khr,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=product-stickers.pdf",
            "Content-Length": str(len(pdf_bytes)),
        },
    )
