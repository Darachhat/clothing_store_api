"""Product API handlers delegating to PRODUCT_SERVICE."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import User
from app.schemas.inventory_schema import STOCK_MATRIX_RESPONSE_SCHEMA
from app.schemas.product_schema import (
    PRODUCT_ATTRIBUTE_CREATE_SCHEMA
    , PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA
    , PRODUCT_ATTRIBUTE_UPDATE_SCHEMA
    , PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA
    , PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA
    , PRODUCT_BULK_ARCHIVE_SCHEMA
    , PRODUCT_CREATE_SCHEMA
    , PRODUCT_IMAGE_CREATE_SCHEMA
    , PRODUCT_IMAGE_RESPONSE_SCHEMA
    , PRODUCT_IMAGE_UPDATE_SCHEMA
    , PRODUCT_VARIANT_BULK_CREATE_SCHEMA
    , PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA
    , PRODUCT_VARIANT_BULK_UPDATE_SCHEMA
    , PRODUCT_RESPONSE_SCHEMA
    , PRODUCT_PAGINATION_RESPONSE_SCHEMA
    , PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA
    , PRODUCT_UPDATE_SCHEMA
    , PRODUCT_VARIANT_CREATE_SCHEMA
    , PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA
    , PRODUCT_VARIANT_RESPONSE_SCHEMA
    , PRODUCT_VARIANT_STATUS_PATCH_SCHEMA
    , PRODUCT_VARIANT_UPDATE_SCHEMA
    , PRODUCT_WITH_VARIANTS_SCHEMA
    , VARIANT_SCAN_RESPONSE_SCHEMA
)
from app.services.product_service import PRODUCT_SERVICE
from app.utils.qr import generate_barcode_png, generate_barcode_svg, generate_qr_png, generate_qr_svg

router                      = APIRouter(prefix="/products", tags=["Products"])
variant_router              = APIRouter(prefix="/product-variants", tags=["Product Variants"])
attribute_router            = APIRouter(prefix="/product-attributes", tags=["Product Attributes"])
public_variant_media_router = APIRouter(prefix="/product-variants", tags=["Product Variants"])


# ─── Products ─────────────────────────────────────────────────────────────────
@router.get("", include_in_schema=False)
@router.get("/")
async def list_products(
    response           : Response
    , page             : int | None  = Query(None, ge=1)
    , page_size        : int | None  = Query(None, ge=1, le=100)
    , search           : str | None  = Query(None)
    , q                : str | None  = Query(None)
    , category         : str | None  = Query(None)
    , category_id      : UUID | None = None
    , brand            : str | None  = Query(None)
    , brand_id         : UUID | None = None
    , status           : str | None  = Query(None)
    , sort             : str         = Query("created_at")
    , sort_direction   : str         = Query("desc")
    , branch_id        : UUID | None = None
    , warehouse_id     : UUID | None = None
    , include_stock    : bool        = Query(False)
    , include_variants : bool        = Query(False, description="Include variant data in response (for POS grid)")
    , skip             : int | None  = Query(None, ge=0)
    , limit            : int | None  = Query(None, le=200)
    , db               : AsyncSession = Depends(get_db)
    , _                : User         = Depends(require_permission("product.read"))
) -> PRODUCT_PAGINATION_RESPONSE_SCHEMA | PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA:
    raw_params = {
        "page"               : page
        , "page_size"        : page_size
        , "search"           : search
        , "q"                : q
        , "category"         : category
        , "category_id"      : category_id
        , "brand"            : brand
        , "brand_id"         : brand_id
        , "status"           : status
        , "sort"             : sort
        , "sort_direction"   : sort_direction
        , "branch_id"        : branch_id
        , "warehouse_id"     : warehouse_id
        , "include_stock"    : include_stock
        , "include_variants" : include_variants
        , "skip"             : skip
        , "limit"            : limit
    }
    data, is_hit, cur_ver               = await PRODUCT_SERVICE.get_paginated_products(db, raw_params)
    response.headers["X-Cache"]         = "HIT" if is_hit else "MISS"
    response.headers["X-Cache-Version"] = str(cur_ver)
    return data


@router.post("", response_model=PRODUCT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=PRODUCT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_product(
    body           : PRODUCT_CREATE_SCHEMA
    , db           : AsyncSession = Depends(get_db)
    , current_user : User         = Depends(require_permission("product.create"))
) -> PRODUCT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.create_product(db=db, body=body)


@router.post("/bulk-archive")
async def bulk_archive_products(
    body : PRODUCT_BULK_ARCHIVE_SCHEMA
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.delete"))
) -> dict:
    return await PRODUCT_SERVICE.bulk_archive_products(db=db, product_ids=body.product_ids)


@router.get("/attributes", response_model=list[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA])
async def list_product_attributes_alias(
    include_inactive : bool         = Query(False)
    , db             : AsyncSession = Depends(get_db)
    , _              : User         = Depends(require_permission("product.read"))
) -> list[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA]:
    return await PRODUCT_SERVICE.list_product_attributes(db=db, include_inactive=include_inactive)


@router.get("/variants", response_model=list[PRODUCT_VARIANT_RESPONSE_SCHEMA])
async def list_all_variants_alias(
    q            : str | None   = Query(None)
    , product_id : UUID | None  = None
    , color_id   : UUID | None  = None
    , size_id    : UUID | None  = None
    , skip       : int          = Query(0, ge=0)
    , limit      : int          = Query(50, le=500)
    , db         : AsyncSession = Depends(get_db)
    , _          : User         = Depends(require_permission("product.read"))
) -> list[PRODUCT_VARIANT_RESPONSE_SCHEMA]:
    """List all variants across products (alias for /product-variants to support /products/variants)."""
    return await PRODUCT_SERVICE.list_variants(
        db           = db
        , q          = q
        , product_id = product_id
        , color_id   = color_id
        , size_id    = size_id
        , skip       = skip
        , limit      = limit
    )


@router.post("/variants", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_variant_alias(
    body : PRODUCT_VARIANT_CREATE_SCHEMA
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.create"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    """Create a variant (alias for /product-variants to support /products/variants)."""
    return await PRODUCT_SERVICE.create_variant(db=db, body=body)


@router.get("/{id}", response_model=PRODUCT_WITH_VARIANTS_SCHEMA)
async def get_product(
    id   : UUID
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.read"))
) -> PRODUCT_WITH_VARIANTS_SCHEMA:
    return await PRODUCT_SERVICE.get_product(db=db, product_id=id)


@router.put("/{id}", response_model=PRODUCT_RESPONSE_SCHEMA)
@router.patch("/{id}", response_model=PRODUCT_RESPONSE_SCHEMA)
async def update_product(
    id     : UUID
    , body : PRODUCT_UPDATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> PRODUCT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.update_product(db=db, product_id=id, body=body)


@router.get("/{id}/variants", response_model=list[PRODUCT_VARIANT_RESPONSE_SCHEMA])
async def get_product_variants(
    id   : UUID
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.read"))
) -> list[PRODUCT_VARIANT_RESPONSE_SCHEMA]:
    return await PRODUCT_SERVICE.list_variants(db=db, product_id=id, limit=500)


@router.get("/{id}/stock-matrix", response_model=STOCK_MATRIX_RESPONSE_SCHEMA)
async def get_product_stock_matrix(
    id             : UUID
    , warehouse_id : UUID | None  = None
    , db           : AsyncSession = Depends(get_db)
    , _            : User         = Depends(require_permission("inventory.read"))
) -> STOCK_MATRIX_RESPONSE_SCHEMA:
    """On-hand stock of one product by color x size, optionally for a single warehouse."""
    data = await PRODUCT_SERVICE.get_stock_matrix(db=db, product_id=id, warehouse_id=warehouse_id)
    return STOCK_MATRIX_RESPONSE_SCHEMA(**data)


@router.post("/{id}/variants/bulk", response_model=PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
@router.post("/{id}/variants/generate", response_model=PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_product_variants_bulk(
    id     : UUID
    , body : PRODUCT_VARIANT_BULK_CREATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.create"))
) -> PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA:
    """Create a color x size grid of variants (with opening stock) in one transaction."""
    result = await PRODUCT_SERVICE.create_variants_bulk(db=db, product_id=id, body=body)
    return PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA(**result)


@router.patch("/{id}/variants/bulk-update", response_model=list[PRODUCT_VARIANT_RESPONSE_SCHEMA])
async def bulk_update_product_variants(
    id     : UUID
    , body : PRODUCT_VARIANT_BULK_UPDATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> list[PRODUCT_VARIANT_RESPONSE_SCHEMA]:
    """Bulk update selling price, cost price, or status across variants of a product."""
    return await PRODUCT_SERVICE.bulk_update_variants(db=db, product_id=id, body=body)


@router.post("/{id}/images", response_model=PRODUCT_IMAGE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def add_product_image(
    id     : UUID
    , body : PRODUCT_IMAGE_CREATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> PRODUCT_IMAGE_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.add_product_image(db=db, product_id=id, body=body)


@router.put("/{id}/images/{image_id}", response_model=PRODUCT_IMAGE_RESPONSE_SCHEMA)
@router.patch("/{id}/images/{image_id}", response_model=PRODUCT_IMAGE_RESPONSE_SCHEMA)
async def update_product_image(
    id         : UUID
    , image_id : UUID
    , body     : PRODUCT_IMAGE_UPDATE_SCHEMA
    , db       : AsyncSession = Depends(get_db)
    , _        : User         = Depends(require_permission("product.update"))
) -> PRODUCT_IMAGE_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.update_product_image(db=db, product_id=id, image_id=image_id, body=body)


@router.delete("/{id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_product_image(
    id         : UUID
    , image_id : UUID
    , db       : AsyncSession = Depends(get_db)
    , _        : User         = Depends(require_permission("product.update"))
) -> Response:
    await PRODUCT_SERVICE.delete_product_image(db=db, product_id=id, image_id=image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/variants", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_product_variant_for_product(
    id     : UUID
    , body : PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.create"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    payload = body.model_dump()
    payload["product_id"] = id
    return await PRODUCT_SERVICE.create_variant(db=db, body=PRODUCT_VARIANT_CREATE_SCHEMA(**payload))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_product(
    id   : UUID
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.delete"))
) -> Response:
    await PRODUCT_SERVICE.delete_product(db=db, product_id=id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Product Variants ─────────────────────────────────────────────────────────
@variant_router.get("", response_model=list[PRODUCT_VARIANT_RESPONSE_SCHEMA], include_in_schema=False)
@variant_router.get("/", response_model=list[PRODUCT_VARIANT_RESPONSE_SCHEMA])
async def list_variants(
    q            : str | None   = Query(None)
    , product_id : UUID | None  = None
    , color_id   : UUID | None  = None
    , size_id    : UUID | None  = None
    , skip       : int          = Query(0, ge=0)
    , limit      : int          = Query(50, le=500)
    , db         : AsyncSession = Depends(get_db)
    , _          : User         = Depends(require_permission("product.read"))
) -> list[PRODUCT_VARIANT_RESPONSE_SCHEMA]:
    return await PRODUCT_SERVICE.list_variants(
        db           = db
        , q          = q
        , product_id = product_id
        , color_id   = color_id
        , size_id    = size_id
        , skip       = skip
        , limit      = limit
    )


@variant_router.post("", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@variant_router.post("/", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_variant(
    body : PRODUCT_VARIANT_CREATE_SCHEMA
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.create"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.create_variant(db=db, body=body)


@variant_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_variant(
    id   : UUID
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.delete"))
) -> Response:
    """Delete a variant. If it still has stock or movement history it is deactivated instead
    (HTTP 200 with ``deactivated: true``) so stock and the audit trail are preserved."""
    removed = await PRODUCT_SERVICE.delete_variant(db=db, variant_id=id)
    if removed:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "deleted": False,
            "deactivated": True,
            "detail": "Variant has stock or movement history, so it was set to INACTIVE instead of deleted.",
        },
    )


@variant_router.get("/scan", response_model=VARIANT_SCAN_RESPONSE_SCHEMA)
async def scan_variant_or_product(
    code           : str         = Query(..., description="Scanned 1D barcode, 2D QR code/URL, SKU, or Product code")
    , warehouse_id : UUID | None = Query(None)
    , db           : AsyncSession = Depends(get_db)
    , _            : User         = Depends(get_current_active_user)
) -> VARIANT_SCAN_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.scan_lookup(db=db, code=code, warehouse_id=warehouse_id)


@variant_router.get("/lookup", response_model=VARIANT_SCAN_RESPONSE_SCHEMA)
async def lookup_variant_or_product(
    barcode        : str | None   = Query(None, description="Barcode or SKU to look up")
    , code         : str | None   = Query(None, description="Alias for barcode/QR/SKU")
    , warehouse_id : UUID | None  = Query(None)
    , db           : AsyncSession = Depends(get_db)
    , _            : User         = Depends(get_current_active_user)
) -> VARIANT_SCAN_RESPONSE_SCHEMA:
    lookup_val = (barcode or code or "").strip()
    return await PRODUCT_SERVICE.scan_lookup(db=db, code=lookup_val, warehouse_id=warehouse_id)


@variant_router.get("/by-qr/{reference:path}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
@variant_router.get("/qr/{reference:path}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, include_in_schema=False)
async def get_variant_by_qr(
    reference : str
    , db      : AsyncSession = Depends(get_db)
    , _       : User         = Depends(get_current_active_user)
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.get_variant_by_qr(db=db, reference=reference)


@variant_router.get("/by-barcode/{barcode}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
@variant_router.get("/barcode/{barcode}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, include_in_schema=False)
async def get_variant_by_barcode(
    barcode : str
    , db    : AsyncSession = Depends(get_db)
    , _     : User         = Depends(get_current_active_user)
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.get_variant_by_barcode(db=db, barcode=barcode)


@variant_router.get("/by-sku/{sku}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
@variant_router.get("/sku/{sku}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA, include_in_schema=False)
async def get_variant_by_sku(
    sku  : str
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(get_current_active_user)
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.get_variant_by_sku(db=db, sku=sku)


@variant_router.post("/{id}/regenerate-codes", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
async def regenerate_variant_codes(
    id             : UUID
    , db           : AsyncSession = Depends(get_db)
    , current_user : User         = Depends(require_permission("product.update"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.regenerate_variant_codes(db=db, variant_id=id, user_id=current_user.id)


@variant_router.patch("/{id}/status", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
async def patch_variant_status(
    id     : UUID
    , body : PRODUCT_VARIANT_STATUS_PATCH_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.patch_variant_status(db=db, variant_id=id, status_code=body.status_code)


@variant_router.get("/{id}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
async def get_variant(
    id   : UUID
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.read"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.get_variant(db=db, variant_id=id)


@public_variant_media_router.get("/{id}/qr")
@variant_router.get("/{id}/qr")
async def get_variant_qr(
    id       : UUID
    , format : str          = Query("png", pattern="^(png|svg)$")
    , db     : AsyncSession = Depends(get_db)
) -> Response:
    variant = await PRODUCT_SERVICE.get_variant(db=db, variant_id=id)
    if format == "svg":
        content = generate_qr_svg(variant.qr_reference)
        return Response(content=content, media_type="image/svg+xml")
    else:
        content = generate_qr_png(variant.qr_reference)
        return Response(content=content, media_type="image/png")


@public_variant_media_router.get("/{id}/barcode")
@variant_router.get("/{id}/barcode")
async def get_variant_barcode(
    id           : UUID
    , format     : str          = Query("svg", pattern="^(png|svg)$")
    , write_text : bool         = Query(False)
    , db         : AsyncSession = Depends(get_db)
) -> Response:
    variant  = await PRODUCT_SERVICE.get_variant(db=db, variant_id=id)
    code_val = variant.barcode or variant.sku
    if format == "svg":
        content = generate_barcode_svg(code_val, write_text=write_text)
        return Response(content=content, media_type="image/svg+xml")
    else:
        content = generate_barcode_png(code_val, write_text=write_text)
        return Response(content=content, media_type="image/png")


@variant_router.put("/{id}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
@variant_router.patch("/{id}", response_model=PRODUCT_VARIANT_RESPONSE_SCHEMA)
async def update_variant(
    id     : UUID
    , body : PRODUCT_VARIANT_UPDATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> PRODUCT_VARIANT_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.update_variant(db=db, variant_id=id, body=body)


# ─── Product Attributes ───────────────────────────────────────────────────────
@attribute_router.get("", response_model=list[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA], include_in_schema=False)
@attribute_router.get("/", response_model=list[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA])
async def list_product_attributes(
    include_inactive : bool         = Query(False)
    , db             : AsyncSession = Depends(get_db)
    , _              : User         = Depends(require_permission("product.read"))
) -> list[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA]:
    return await PRODUCT_SERVICE.list_product_attributes(db=db, include_inactive=include_inactive)


@attribute_router.post("", response_model=PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@attribute_router.post("/", response_model=PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_product_attribute(
    body : PRODUCT_ATTRIBUTE_CREATE_SCHEMA
    , db : AsyncSession = Depends(get_db)
    , _  : User         = Depends(require_permission("product.create"))
) -> PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.create_product_attribute(db=db, body=body)


@attribute_router.put("/{id}", response_model=PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA)
@attribute_router.patch("/{id}", response_model=PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA)
async def update_product_attribute(
    id     : UUID
    , body : PRODUCT_ATTRIBUTE_UPDATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.update"))
) -> PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.update_product_attribute(db=db, attribute_id=id, body=body)


@attribute_router.post("/{id}/values", response_model=PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def add_product_attribute_value(
    id     : UUID
    , body : PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA
    , db   : AsyncSession = Depends(get_db)
    , _    : User         = Depends(require_permission("product.create"))
) -> PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA:
    return await PRODUCT_SERVICE.add_product_attribute_value(db=db, attribute_id=id, body=body)


