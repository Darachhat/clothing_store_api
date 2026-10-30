"""Inventory consistency tests — core business logic."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.branch import Branch, Warehouse
from app.models.product import Brand, Category, Color, Product, ProductVariant, Size
from app.models.user import Role, User
from app.repositories.inventory_repository import InventoryStockRepository
from app.services.inventory_service import InventoryService


async def create_test_infra(db: AsyncSession):
    branch = Branch(code="TEST", name="Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Test Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    category = Category(name="T-Shirts", slug="t-shirts")
    db.add(category)
    brand = Brand(name="TestBrand", slug="testbrand")
    db.add(brand)
    color = Color(name="Black", hex_code="#000000")
    db.add(color)
    size = Size(name="M", type="LETTER")
    db.add(size)
    await db.flush()

    product = Product(
        code="TEST-PROD-001",
        name="Test T-Shirt",
        slug="test-t-shirt",
        category_id=category.id,
        brand_id=brand.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="TEST-BLK-M-001",
        qr_reference="VAR-999999",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(variant)

    role = Role(name="ADMIN_TEST", is_system=True)
    db.add(role)
    await db.flush()

    user = User(
        username="inv_tester",
        email="inv@test.com",
        full_name="Inventory Tester",
        hashed_password=hash_password("pass"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()
    await db.commit()

    return branch, warehouse, variant, user


@pytest.mark.asyncio
async def test_initial_stock_is_zero(db: AsyncSession) -> None:
    _, warehouse, variant, _ = await create_test_infra(db)
    repo = InventoryStockRepository(db)
    stock = await repo.get_stock(variant.id, warehouse.id)
    assert stock is None  # not yet initialized


@pytest.mark.asyncio
async def test_initial_stock_creation(db: AsyncSession) -> None:
    _, warehouse, variant, user = await create_test_infra(db)
    service = InventoryService(db)

    stock, movement = await service.adjust_stock(
        variant_id=variant.id,
        warehouse_id=warehouse.id,
        quantity_delta=100,
        movement_type="INITIAL_STOCK",
        note="Initial setup",
        created_by=user.id,
    )
    await db.commit()

    assert stock.quantity == 100
    assert movement.before_quantity == 0
    assert movement.after_quantity == 100
    assert movement.movement_type == "INITIAL_STOCK"


@pytest.mark.asyncio
async def test_stock_sale_return_consistency(db: AsyncSession) -> None:
    """Test: Initial 100 → Sale 5 → 95 → Return 2 → 97 → Adjustment -3 → 94."""
    _, warehouse, variant, user = await create_test_infra(db)
    service = InventoryService(db)

    # Initial stock = 100
    stock, _ = await service.adjust_stock(variant.id, warehouse.id, 100, "INITIAL_STOCK", created_by=user.id)
    await db.commit()
    assert stock.quantity == 100

    # Sale 5 → 95
    stock, _ = await service.adjust_stock(variant.id, warehouse.id, -5, "SALE", created_by=user.id)
    await db.commit()
    assert stock.quantity == 95

    # Return 2 → 97
    stock, _ = await service.adjust_stock(variant.id, warehouse.id, 2, "RETURN", created_by=user.id)
    await db.commit()
    assert stock.quantity == 97

    # Adjustment -3 → 94
    stock, _ = await service.adjust_stock(variant.id, warehouse.id, -3, "ADJUSTMENT", created_by=user.id)
    await db.commit()
    assert stock.quantity == 94


@pytest.mark.asyncio
async def test_cannot_go_below_zero(db: AsyncSession) -> None:
    _, warehouse, variant, user = await create_test_infra(db)
    service = InventoryService(db)

    await service.adjust_stock(variant.id, warehouse.id, 5, "INITIAL_STOCK", created_by=user.id)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):  # HTTPException 400
        await service.adjust_stock(variant.id, warehouse.id, -10, "SALE", created_by=user.id)
