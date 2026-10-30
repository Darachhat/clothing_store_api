"""Public store catalog endpoints — /api/store/v1/catalog/

Exposes a read-only, public-friendly view of the product catalog.
No auth required. Only ACTIVE products with ACTIVE variants are shown.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.product import Product, ProductVariant
from app.repositories.product_repository import ProductRepository

router = APIRouter(prefix="/catalog", tags=["Store Catalog"])


@router.get("/products")
async def list_public_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    search: str | None = Query(None),
    category_id: UUID | None = Query(None),
    brand_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List active products for the public storefront."""
    repo = ProductRepository(db)
    products, total = await repo.search_paginated(
        page=page,
        page_size=page_size,
        search=search,
        category_id=category_id,
        brand_id=brand_id,
        status="ACTIVE",
    )
    return {
        "items": [_serialize_product(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/products/{product_id}")
async def get_public_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get a single product detail for the storefront."""
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id, Product.status == "ACTIVE")
        .options(
            selectinload(Product.variants),
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _serialize_product(product, include_variants=True)


def _serialize_product(product: Product, include_variants: bool = False) -> dict:
    """Convert a Product model to a public-safe dict (no cost price)."""
    data: dict = {
        "id": str(product.id),
        "name": product.name,
        "description": getattr(product, "description", None),
        "category": product.category.name if product.category else None,
        "brand": product.brand.name if product.brand else None,
        "image_url": getattr(product, "image_url", None),
        "status": product.status,
    }
    if include_variants and hasattr(product, "variants"):
        data["variants"] = [
            {
                "id": str(v.id),
                "sku": v.sku,
                "color": v.color.name if getattr(v, "color", None) else None,
                "size": v.size.name if getattr(v, "size", None) else None,
                "price": float(v.selling_price) if hasattr(v, "selling_price") else None,
                "stock": v.stock_quantity if hasattr(v, "stock_quantity") else None,
                "barcode": v.barcode if hasattr(v, "barcode") else None,
            }
            for v in product.variants
            if getattr(v, "status", "ACTIVE") == "ACTIVE"
        ]
    return data
