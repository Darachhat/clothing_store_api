"""Tests for the public storefront catalog (/api/store/v1/catalog)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Category, Product


@pytest.mark.asyncio
async def test_public_catalog_lists_active_products(client: AsyncClient, db: AsyncSession) -> None:
    category = Category(name="Store Tees", slug="store-tees")
    brand = Brand(name="StoreBrand", slug="storebrand")
    db.add_all([category, brand])
    await db.flush()
    db.add(Product(code="STORE-001", name="Store Tee", slug="store-tee",
                   category_id=category.id, brand_id=brand.id))
    await db.commit()

    resp = await client.get("/api/store/v1/catalog/products")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page"] == 1
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["name"] == "Store Tee")
    assert item["category"] == "Store Tees"
    assert item["brand"] == "StoreBrand"
    assert "cost_price" not in item


@pytest.mark.asyncio
async def test_public_catalog_unknown_product_is_404(client: AsyncClient) -> None:
    resp = await client.get("/api/store/v1/catalog/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404

