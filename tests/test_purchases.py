"""Purchasing and Goods Receipts tests."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Branch, Warehouse
from app.models import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.models import Role, User
from app.repositories.inventory_repository import InventoryStockRepository
from app.schemas.purchase_schema import (
    GOODS_RECEIPT_CREATE_SCHEMA,
    GOODS_RECEIPT_ITEM_CREATE_SCHEMA,
    PURCHASE_ITEM_CREATE_SCHEMA,
    PURCHASE_ORDER_CREATE_SCHEMA,
)
from app.services.purchase_service import PURCHASE_SERVICE


async def create_purchase_test_infra(db: AsyncSession):
    branch = Branch(code="PUR-TEST", name="Purchasing Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Purchasing Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    supplier = Supplier(code="SUPP-001", name="Alpha Supplier", phone="123456")
    db.add(supplier)

    category = Category(name="Pants", slug="pants")
    db.add(category)
    brand = Brand(name="DenimCo", slug="denimco")
    db.add(brand)
    color = Color(name="Blue", hex_code="#0000FF")
    db.add(color)
    size = Size(name="32", type="NUMERIC")
    db.add(size)
    await db.flush()

    product = Product(
        code="PANTS-001",
        name="Classic Jeans",
        slug="classic-jeans",
        category_id=category.id,
        brand_id=brand.id,
        supplier_id=supplier.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="PANTS-BLU-32-001",
        qr_reference="VAR-888888",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("10.00"),
        selling_price=Decimal("30.00"),
    )
    db.add(variant)

    role = Role(name="PURCHASE_MANAGER", is_system=True)
    db.add(role)
    await db.flush()

    user = User(
        username="purchaser",
        email="purchaser@example.com",
        full_name="Purchase Agent",
        hashed_password=hash_password("secret123"),
        branch_id=branch.id,
        roles=[role],
    )
    db.add(user)
    await db.flush()

    return {
        "branch": branch,
        "warehouse": warehouse,
        "supplier": supplier,
        "variant": variant,
        "user": user,
    }


@pytest.mark.asyncio
async def test_purchase_order_lifecycle_and_goods_receipt(db: AsyncSession):
    infra = await create_purchase_test_infra(db)
    service = PURCHASE_SERVICE(db)
    stock_repo = InventoryStockRepository(db)

    # 1. Create Purchase Order
    po_in = PURCHASE_ORDER_CREATE_SCHEMA(
        supplier_id=infra["supplier"].id,
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        notes="First order test",
        tax_amount=Decimal("5.00"),
        items=[
            PURCHASE_ITEM_CREATE_SCHEMA(
                variant_id=infra["variant"].id,
                quantity_ordered=20,
                unit_cost=Decimal("12.00"),
            )
        ],
    )
    po = await service.create_purchase_order(created_by=infra["user"].id, data=po_in)
    assert po.status == "DRAFT"
    assert po.subtotal == Decimal("240.00")
    assert po.total == Decimal("245.00")
    assert len(po.items) == 1
    assert po.items[0].quantity_ordered == 20
    assert po.items[0].quantity_received == 0

    # 2. Approve Purchase Order
    po = await service.approve_purchase_order(po_id=po.id, approved_by=infra["user"].id)
    assert po.status == "ORDERED"
    assert po.approved_by == infra["user"].id

    # 3. Partial Goods Receipt (receive 8 units)
    po_item = po.items[0]
    gr_in_1 = GOODS_RECEIPT_CREATE_SCHEMA(
        purchase_order_id=po.id,
        notes="Partial delivery received",
        items=[
            GOODS_RECEIPT_ITEM_CREATE_SCHEMA(
                purchase_item_id=po_item.id,
                variant_id=infra["variant"].id,
                quantity_received=8,
                unit_cost=Decimal("12.00"),
            )
        ],
    )
    gr1 = await service.create_goods_receipt(received_by=infra["user"].id, data=gr_in_1)
    assert gr1.status == "COMPLETED"
    assert len(gr1.items) == 1
    assert gr1.items[0].quantity_received == 8

    # Stock verification: warehouse stock should now be 8
    stock = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock is not None
    assert stock.quantity == 8

    # PO should be in PARTIAL status
    updated_po = await service.po_repo.get_by_id(po.id)
    assert updated_po.status == "PARTIAL"
    assert updated_po.items[0].quantity_received == 8

    # 4. Final Goods Receipt (receive remaining 12 units)
    gr_in_2 = GOODS_RECEIPT_CREATE_SCHEMA(
        purchase_order_id=po.id,
        notes="Remaining delivery received",
        items=[
            GOODS_RECEIPT_ITEM_CREATE_SCHEMA(
                purchase_item_id=po_item.id,
                variant_id=infra["variant"].id,
                quantity_received=12,
                unit_cost=Decimal("12.00"),
            )
        ],
    )
    gr2 = await service.create_goods_receipt(received_by=infra["user"].id, data=gr_in_2)
    assert gr2.status == "COMPLETED"

    # Stock verification: warehouse stock should now be 8 + 12 = 20
    stock = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock.quantity == 20

    # PO should now be fully RECEIVED
    final_po = await service.po_repo.get_by_id(po.id)
    assert final_po.status == "RECEIVED"
    assert final_po.items[0].quantity_received == 20
