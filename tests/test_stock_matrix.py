"""Stock by color x size: matrix, bulk variant creation, safe variant deletion, atomic stock rows, and barcode/QR conflict checks."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CONFLICT_EXCEPTION
from app.models import Branch, BRAND_MODEL, CATEGORY_MODEL, Color, Product, Size, Warehouse
from app.repositories.inventory_repository import InventoryStockRepository
from app.schemas.product_schema import (
    PRODUCT_VARIANT_BULK_CREATE_SCHEMA,
    PRODUCT_VARIANT_BULK_ITEM_SCHEMA,
    PRODUCT_VARIANT_CREATE_SCHEMA,
    PRODUCT_VARIANT_UPDATE_SCHEMA,
)
from app.services.inventory_service import INVENTORY_SERVICE
from app.services.product_service import PRODUCT_SERVICE


async def _setup(db: AsyncSession):
    branch = Branch(code="MX", name="Matrix Branch")
    db.add(branch)
    await db.flush()
    warehouse = Warehouse(branch_id=branch.id, name="Main", is_default=True)
    db.add(warehouse)
    category = CATEGORY_MODEL(name="Tees", slug="tees-mx")
    brand = BRAND_MODEL(name="MxBrand", slug="mxbrand")
    black = Color(name="Black", hex_code="#000000")
    white = Color(name="White", hex_code="#FFFFFF")
    small = Size(name="S", type="LETTER")
    medium = Size(name="M", type="LETTER")
    db.add_all([category, brand, black, white, small, medium])
    await db.flush()
    product = Product(code="MX-001", name="Matrix Tee", slug="matrix-tee", category_id=category.id, brand_id=brand.id)
    db.add(product)
    await db.commit()
    return warehouse, product, (black, white), (small, medium)


def _bulk(colors, sizes, stock=5, warehouse_id=None):
    return PRODUCT_VARIANT_BULK_CREATE_SCHEMA(
        items=[
            PRODUCT_VARIANT_BULK_ITEM_SCHEMA(color_id=c.id, size_id=s.id, initial_stock=stock)
            for c in colors
            for s in sizes
        ],
        default_selling_price=Decimal("19.99"),
        default_cost_price=Decimal("8.00"),
        warehouse_id=warehouse_id,
    )


@pytest.mark.asyncio
async def test_bulk_create_builds_full_grid_with_stock(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors, sizes, 5, wh.id))

    assert len(result["created"]) == 4
    assert result["skipped"] == []
    assert len({v.sku for v in result["created"]}) == 4           # unique SKUs
    assert len({v.barcode for v in result["created"]}) == 4       # unique barcodes

    matrix = await PRODUCT_SERVICE.get_stock_matrix(db, product.id)
    assert len(matrix["cells"]) == 4                              # 2 colors × 2 sizes
    assert matrix["total_quantity"] == 20                         # 4 × 5
    assert {c["quantity"] for c in matrix["cells"]} == {5}
    assert {c["name"] for c in matrix["colors"]} == {"Black", "White"}
    assert {s["name"] for s in matrix["sizes"]} == {"S", "M"}


@pytest.mark.asyncio
async def test_bulk_create_skips_existing_and_missing_price(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes[:1], 1, wh.id))

    body = _bulk(colors[:1], sizes, 2, wh.id)   # (black,S) exists; (black,M) is new
    body.items.append(PRODUCT_VARIANT_BULK_ITEM_SCHEMA(color_id=colors[1].id, size_id=sizes[0].id))
    body.default_selling_price = None           # no default price → all unpriced items skipped
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, body)

    assert result["created"] == []
    reasons = {s["reason"] for s in result["skipped"]}
    assert reasons == {"Variant already exists", "No selling price provided"}


@pytest.mark.asyncio
async def test_matrix_flags_low_and_out(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes, 10, wh.id))
    low_v, out_v = result["created"]

    repo = InventoryStockRepository(db)
    low_stock = await repo.get_stock(low_v.id, wh.id)
    low_stock.reorder_level = 10               # quantity (10) <= reorder (10) → LOW
    await INVENTORY_SERVICE(db).adjust_stock(out_v.id, wh.id, -10, "ADJUSTMENT")  # → 0
    await db.commit()

    matrix = await PRODUCT_SERVICE.get_stock_matrix(db, product.id)
    states = {c["variant_id"]: c["stock_status"] for c in matrix["cells"]}

    assert states[low_v.id] == "LOW"
    assert states[out_v.id] == "OUT"
    assert matrix["low_count"] == 1 and matrix["out_count"] == 1


@pytest.mark.asyncio
async def test_variant_with_stock_is_deactivated_not_deleted(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes[:1], 7, wh.id))
    variant = result["created"][0]

    removed = await PRODUCT_SERVICE.delete_variant(db, variant.id)

    assert removed is False
    kept = await PRODUCT_SERVICE.get_variant(db, variant.id)
    assert kept.status_code == "INACTIVE"
    matrix = await PRODUCT_SERVICE.get_stock_matrix(db, product.id)
    assert matrix["total_quantity"] == 7      # stock preserved


@pytest.mark.asyncio
async def test_variant_without_stock_or_history_is_deleted(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes[:1], 0, wh.id))
    variant = result["created"][0]

    assert await PRODUCT_SERVICE.delete_variant(db, variant.id) is True
    matrix = await PRODUCT_SERVICE.get_stock_matrix(db, product.id)
    assert matrix["cells"] == []


@pytest.mark.asyncio
async def test_get_or_create_stock_is_idempotent_and_locks(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes[:1], 0, wh.id))
    variant = result["created"][0]

    repo = InventoryStockRepository(db)
    first  = await repo.get_or_create_stock(variant.id, wh.id, lock=True)
    second = await repo.get_or_create_stock(variant.id, wh.id, lock=True)
    assert first.id == second.id
    assert first.quantity == 0


@pytest.mark.asyncio
async def test_insufficient_stock_is_rejected(db: AsyncSession) -> None:
    from fastapi import HTTPException

    wh, product, colors, sizes = await _setup(db)
    result = await PRODUCT_SERVICE.create_variants_bulk(db, product.id, _bulk(colors[:1], sizes[:1], 3, wh.id))
    variant = result["created"][0]

    with pytest.raises(HTTPException) as exc:
        await INVENTORY_SERVICE(db).adjust_stock(variant.id, wh.id, -4, "SALE")
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_barcode_and_qr_code_rejected_with_conflict(db: AsyncSession) -> None:
    wh, product, colors, sizes = await _setup(db)
    v1 = await PRODUCT_SERVICE.create_variant(
        db,
        PRODUCT_VARIANT_CREATE_SCHEMA(
            product_id=product.id,
            color_id=colors[0].id,
            size_id=sizes[0].id,
            selling_price=Decimal("25.00"),
            barcode="https://store.local/p/8859990001",
        ),
    )
    assert v1.barcode == "8859990001"

    # Creating another variant with the same barcode (even via URL) raises 409 CONFLICT
    with pytest.raises(CONFLICT_EXCEPTION) as exc_bc:
        await PRODUCT_SERVICE.create_variant(
            db,
            PRODUCT_VARIANT_CREATE_SCHEMA(
                product_id=product.id,
                color_id=colors[0].id,
                size_id=sizes[1].id,
                selling_price=Decimal("25.00"),
                barcode="8859990001",
            ),
        )
    assert exc_bc.value.status_code == 409

    # Creating another variant whose barcode collides with an existing QR reference raises 409 CONFLICT
    with pytest.raises(CONFLICT_EXCEPTION) as exc_qr:
        await PRODUCT_SERVICE.create_variant(
            db,
            PRODUCT_VARIANT_CREATE_SCHEMA(
                product_id=product.id,
                color_id=colors[0].id,
                size_id=sizes[1].id,
                selling_price=Decimal("25.00"),
                barcode=v1.qr_reference,
            ),
        )
    assert exc_qr.value.status_code == 409

    # Updating a second variant to use v1's barcode also raises 409 CONFLICT
    v2 = await PRODUCT_SERVICE.create_variant(
        db,
        PRODUCT_VARIANT_CREATE_SCHEMA(
            product_id=product.id,
            color_id=colors[1].id,
            size_id=sizes[0].id,
            selling_price=Decimal("25.00"),
        ),
    )
    with pytest.raises(CONFLICT_EXCEPTION) as exc_upd:
        await PRODUCT_SERVICE.update_variant(
            db,
            v2.id,
            PRODUCT_VARIANT_UPDATE_SCHEMA(barcode="8859990001"),
        )
    assert exc_upd.value.status_code == 409
