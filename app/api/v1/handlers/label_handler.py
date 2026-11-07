"""Label generation API endpoint."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.handlers.setting_handler import resolve_brand_settings, resolve_sticker_settings, update_sticker_settings
from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.repositories.product_repository import ProductVariantRepository
from app.schemas.base_schema import BASE_SCHEMA
from app.schemas.setting_schema import STICKER_TEMPLATE_SCHEMA
from app.utils.labels import LabelData, generate_labels_pdf

router = APIRouter(prefix="/labels", tags=["Labels"])


class LabelVariantRequest(BASE_SCHEMA):
    variant_id: UUID
    quantity: int = Field(ge=1, le=500)


class LabelGenerateRequest(BASE_SCHEMA):
    variants: list[LabelVariantRequest]
    paper_size: str | None = None
    label_width_mm: float | None = None
    label_height_mm: float | None = None
    columns: int | None = None
    code_type: str | None = None  # "BARCODE" | "QR"
    show_khr: bool | None = None
    show_store_header: bool | None = None
    show_product_name: bool | None = None
    show_sku: bool | None = None
    show_variant_attrs: bool | None = None
    show_price_usd: bool | None = None
    khr_exchange_rate: int | None = None
    store_name_override: str | None = None


@router.get("/template", response_model=STICKER_TEMPLATE_SCHEMA)
async def get_label_template_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> dict:
    """Return active sticker/label template configuration."""
    return await resolve_sticker_settings(db)


@router.put("/template", response_model=STICKER_TEMPLATE_SCHEMA)
async def update_label_template_config(
    body: STICKER_TEMPLATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("product.write")),
) -> dict:
    """Update active sticker/label template configuration."""
    return await update_sticker_settings(body=body, db=db, _=current_user)


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
@router.post("/batch", include_in_schema=False)
@router.post("/download", include_in_schema=False)
async def generate_labels(
    body: LabelGenerateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> Response:
    """Generate a PDF with QR code or Code128 barcode stickers for selected variants."""
    repo = ProductVariantRepository(db)
    labels: list[LabelData] = []
    brand_cfg = await resolve_brand_settings(db)
    sticker_cfg = await resolve_sticker_settings(db)

    default_store_header = (
        sticker_cfg.get("store_header")
        or brand_cfg.get("store_name_kh")
        or brand_cfg.get("store_name")
        or "គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់"
    )

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
            else default_store_header
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
        paper_size=body.paper_size or str(sticker_cfg.get("paper_size", "THERMAL_50x30")),
        label_width_mm=float(body.label_width_mm if body.label_width_mm is not None else sticker_cfg.get("label_width_mm", 50.0)),
        label_height_mm=float(body.label_height_mm if body.label_height_mm is not None else sticker_cfg.get("label_height_mm", 30.0)),
        columns=int(body.columns if body.columns is not None else sticker_cfg.get("columns", 1)),
        code_type=body.code_type or str(sticker_cfg.get("code_type", "BARCODE")),
        show_khr=bool(body.show_khr if body.show_khr is not None else sticker_cfg.get("show_khr", True)),
        show_store_header=bool(body.show_store_header if body.show_store_header is not None else sticker_cfg.get("show_store_header", True)),
        show_product_name=bool(body.show_product_name if body.show_product_name is not None else sticker_cfg.get("show_product_name", True)),
        show_sku=bool(body.show_sku if body.show_sku is not None else sticker_cfg.get("show_sku", True)),
        show_variant_attrs=bool(body.show_variant_attrs if body.show_variant_attrs is not None else sticker_cfg.get("show_variant_attrs", True)),
        show_price_usd=bool(body.show_price_usd if body.show_price_usd is not None else sticker_cfg.get("show_price_usd", True)),
        khr_exchange_rate=int(body.khr_exchange_rate if body.khr_exchange_rate is not None else sticker_cfg.get("khr_exchange_rate", 4100)),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=product-stickers.pdf",
            "Content-Length": str(len(pdf_bytes)),
        },
    )
