"""Label generation API endpoint."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.repositories.product_repository import ProductVariantRepository
from app.schemas.base import BaseSchema
from app.utils.labels import LabelData, generate_labels_pdf

router = APIRouter(prefix="/labels", tags=["Labels"])


class LabelVariantRequest(BaseSchema):
    variant_id: UUID
    quantity: int = Field(ge=1, le=500)


class LabelGenerateRequest(BaseSchema):
    variants: list[LabelVariantRequest]
    paper_size: str = "THERMAL_50x30"
    label_width_mm: float = 50.0
    label_height_mm: float = 30.0
    columns: int = 1
    code_type: str = "BARCODE"  # "BARCODE" | "QR"
    show_khr: bool = True
    store_name_override: str | None = None


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
