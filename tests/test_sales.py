"""Tests for sale, complete-sale, cancel, and return/refund flows."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Branch, Warehouse
from app.models import Brand, Category, Color, Product, ProductVariant, Size
from app.models import Permission, Role, User
from app.repositories.inventory_repository import InventoryStockRepository
from app.services.inventory_service import InventoryService
from app.services.sale_service import SaleService


async def create_sale_test_infra(db: AsyncSession):
    branch = Branch(code="SALE-TEST", name="Sales Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Sales Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    category = Category(name="Sale Shirts", slug="sale-shirts")
    db.add(category)
    brand = Brand(name="SaleBrand", slug="salebrand")
    db.add(brand)
    color = Color(name="Red", hex_code="#FF0000")
    db.add(color)
    size = Size(name="L", type="LETTER")
    db.add(size)
    await db.flush()

    product = Product(
        code="SALE-PROD-001",
        name="Sale Test Shirt",
        slug="sale-test-shirt",
        category_id=category.id,
        brand_id=brand.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="SALE-RED-L-001",
        qr_reference="VAR-SALE-001",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("8.00"),
        selling_price=Decimal("20.00"),
    )
    db.add(variant)

    # Create role with permissions - assign in constructor to avoid lazy load in async
    sale_perm = Permission(code="sale.create", name="Create Sale", module="sales")
    sale_read_perm = Permission(code="sale.read", name="Read Sale", module="sales")
    refund_perm = Permission(code="sale.refund", name="Refund Sale", module="sales")
    db.add_all([sale_perm, sale_read_perm, refund_perm])
    await db.flush()

    role = Role(
        name="CASHIER_TEST",
        is_system=True,
        permissions=[sale_perm, sale_read_perm, refund_perm],
    )
    db.add(role)
    await db.flush()

    user = User(
        username="cashier_tester",
        email="cashier@saletest.com",
        full_name="Cashier Tester",
        hashed_password=hash_password("test_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.flush()
    await db.commit()

    # Initialize stock
    inv_service = InventoryService(db)
    await inv_service.adjust_stock(
        variant_id=variant.id,
        warehouse_id=warehouse.id,
        quantity_delta=50,
        movement_type="INITIAL_STOCK",
        note="Initial test stock",
        created_by=user.id,
    )
    await db.commit()

    return {
        "branch": branch,
        "warehouse": warehouse,
        "variant": variant,
        "user": user,
        "role": role,
    }


@pytest.mark.asyncio
async def test_create_and_complete_sale(db: AsyncSession) -> None:
    """Create a sale, complete it with payment, verify stock decreases."""
    infra = await create_sale_test_infra(db)
    stock_repo = InventoryStockRepository(db)

    # Check initial stock = 50
    stock = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock is not None and stock.quantity == 50

    service = SaleService(db)

    # Create a draft sale
    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 3,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
        customer_id=None,
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
    )
    assert sale.sale_status == "DRAFT"
    assert sale.total == Decimal("60.00")
    assert len(sale.items) == 1
    await db.commit()

    # Stock should NOT change yet (stock changes on complete, not create)
    stock = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock.quantity == 50

    # Complete the sale
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()

    completed = await service.complete_sale(
        sale_reloaded,
        [{"payment_method": "CASH", "amount": Decimal("60.00"), "reference_number": None}],
    )
    await db.commit()

    assert completed.sale_status == "COMPLETED"
    assert completed.payment_status == "PAID"

    # Stock should now be 50 - 3 = 47
    stock = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock.quantity == 47


@pytest.mark.asyncio
async def test_cancel_completed_sale_restores_stock(db: AsyncSession) -> None:
    """Cancelling a completed sale must restore stock."""
    infra = await create_sale_test_infra(db)
    stock_repo = InventoryStockRepository(db)
    service = SaleService(db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 5,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    await db.commit()

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()
    await service.complete_sale(sale_reloaded, [{"payment_method": "CASH", "amount": Decimal("100.00")}])
    await db.commit()

    stock_after_sale = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock_after_sale.quantity == 45  # 50 - 5

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items), selectinload(SaleModel.payments))
    )
    completed_sale = res.scalar_one()
    await service.cancel_sale(completed_sale, infra["user"].id)
    await db.commit()

    stock_after_cancel = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock_after_cancel.quantity == 50  # restored


@pytest.mark.asyncio
async def test_partial_payment_sets_partial_status(db: AsyncSession) -> None:
    """Paying less than total should mark payment as PARTIAL."""
    infra = await create_sale_test_infra(db)
    service = SaleService(db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 2,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    await db.commit()

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()

    # Pay only 30 out of 40
    completed = await service.complete_sale(
        sale_reloaded, [{"payment_method": "CASH", "amount": Decimal("30.00")}]
    )
    await db.commit()

    assert completed.payment_status == "PARTIAL"
    assert completed.sale_status == "COMPLETED"


@pytest.mark.asyncio
async def test_return_restores_stock(db: AsyncSession) -> None:
    """Returning 1 item from a 2-item sale should restore stock by 1."""
    infra = await create_sale_test_infra(db)
    stock_repo = InventoryStockRepository(db)
    service = SaleService(db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 2,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    await db.commit()

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()
    await service.complete_sale(sale_reloaded, [{"payment_method": "CASH", "amount": Decimal("40.00")}])
    await db.commit()

    stock_mid = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock_mid.quantity == 48  # 50 - 2

    # Reload sale with items for return
    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    completed_sale = res.scalar_one()
    sale_item = completed_sale.items[0]

    ret = await service.process_return(
        original_sale=completed_sale,
        return_items_data=[{"sale_item_id": sale_item.id, "quantity": 1}],
        refund_payments=[{"payment_method": "CASH", "amount": Decimal("20.00")}],
        return_type="PARTIAL",
        reason="Customer changed mind",
        processed_by=infra["user"].id,
    )
    await db.commit()

    assert ret.status == "COMPLETED"
    assert ret.return_type == "PARTIAL"
    assert ret.total_refund == Decimal("20.00")

    stock_final = await stock_repo.get_stock(infra["variant"].id, infra["warehouse"].id)
    assert stock_final.quantity == 49  # 48 + 1 returned


@pytest.mark.asyncio
async def test_cannot_double_complete_sale(db: AsyncSession) -> None:
    """Completing an already completed sale must raise HTTPException."""
    from fastapi import HTTPException

    infra = await create_sale_test_infra(db)
    service = SaleService(db)

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 1,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    await db.commit()

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()
    await service.complete_sale(sale_reloaded, [{"payment_method": "CASH", "amount": Decimal("20.00")}])
    await db.commit()

    # Try to complete again — must raise
    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_again = res.scalar_one()
    with pytest.raises(HTTPException) as exc_info:
        await service.complete_sale(sale_again, [{"payment_method": "CASH", "amount": Decimal("20.00")}])
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_sale_api_via_http(client: AsyncClient, db: AsyncSession) -> None:
    """End-to-end test: login → create sale → GET /sales via HTTP."""
    infra = await create_sale_test_infra(db)

    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "cashier_tester", "password": "test_pass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create sale via API
    sale_resp = await client.post(
        "/api/v1/sales/",
        headers=headers,
        json={
            "branch_id": str(infra["branch"].id),
            "warehouse_id": str(infra["warehouse"].id),
            "items": [
                {
                    "variant_id": str(infra["variant"].id),
                    "quantity": 2,
                    "discount_amount": 0,
                }
            ],
            "discount_amount": 0,
            "tax_amount": 0,
        },
    )
    assert sale_resp.status_code == 201
    sale_data = sale_resp.json()
    assert sale_data["sale_status"] == "DRAFT"
    assert float(sale_data["total"]) == 40.00

    # List sales
    list_resp = await client.get("/api/v1/sales/", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


# ── Server-side pricing / discount validation ────────────────────────────────


@pytest.mark.asyncio
async def test_create_sale_ignores_client_unit_price(db: AsyncSession) -> None:
    """A client-supplied unit_price must not override the catalog selling price."""
    infra = await create_sale_test_infra(db)
    sale = await SaleService(db).create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 2,
                "unit_price": Decimal("0.01"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    assert sale.items[0].unit_price == Decimal("20.00")
    assert sale.total == Decimal("40.00")


@pytest.mark.asyncio
async def test_line_discount_is_not_double_counted(db: AsyncSession) -> None:
    """Line discount reduces the total once; order discount is separate."""
    infra = await create_sale_test_infra(db)
    sale = await SaleService(db).create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 2,
                "discount_amount": Decimal("5.00"),
            }
        ],
        discount_amount=Decimal("3.00"),
    )
    # 2 * 20 - 5 (line) - 3 (order) = 32
    assert sale.subtotal == Decimal("35.00")
    assert sale.total == Decimal("32.00")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "line_discount,order_discount,tax,qty",
    [
        (Decimal("-1"), Decimal("0"), Decimal("0"), 1),
        (Decimal("21"), Decimal("0"), Decimal("0"), 1),
        (Decimal("0"), Decimal("21"), Decimal("0"), 1),
        (Decimal("0"), Decimal("0"), Decimal("-1"), 1),
        (Decimal("0"), Decimal("0"), Decimal("0"), 0),
    ],
)
async def test_create_sale_rejects_invalid_amounts(
    db: AsyncSession, line_discount, order_discount, tax, qty
) -> None:
    from fastapi import HTTPException

    infra = await create_sale_test_infra(db)
    with pytest.raises(HTTPException) as exc:
        await SaleService(db).create_sale(
            branch_id=infra["branch"].id,
            warehouse_id=infra["warehouse"].id,
            cashier_id=infra["user"].id,
            items_data=[
                {
                    "variant_id": infra["variant"].id,
                    "quantity": qty,
                    "discount_amount": line_discount,
                }
            ],
            discount_amount=order_discount,
            tax_amount=tax,
        )
    assert exc.value.status_code == 400


# ── Return validation ────────────────────────────────────────────────────────


async def _completed_sale(db: AsyncSession, infra, qty: int):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    service = SaleService(db)
    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[{"variant_id": infra["variant"].id, "quantity": qty}],
    )
    await db.commit()
    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    loaded = res.scalar_one()
    await service.complete_sale(
        loaded, [{"payment_method": "CASH", "amount": Decimal(20) * qty}]
    )
    await db.commit()
    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    return service, res.scalar_one()


@pytest.mark.asyncio
async def test_partial_return_keeps_sale_partially_refunded(db: AsyncSession) -> None:
    infra = await create_sale_test_infra(db)
    service, sale = await _completed_sale(db, infra, 2)
    item = sale.items[0]

    await service.process_return(
        original_sale=sale,
        return_items_data=[{"sale_item_id": item.id, "quantity": 1}],
        refund_payments=[{"payment_method": "CASH", "amount": Decimal("20.00")}],
        return_type="PARTIAL",
        reason=None,
        processed_by=infra["user"].id,
    )
    await db.commit()
    assert sale.payment_status == "PARTIALLY_REFUNDED"
    assert sale.sale_status == "COMPLETED"

    # Returning the remaining unit completes the refund
    await service.process_return(
        original_sale=sale,
        return_items_data=[{"sale_item_id": item.id, "quantity": 1}],
        refund_payments=[{"payment_method": "CASH", "amount": Decimal("20.00")}],
        return_type="PARTIAL",
        reason=None,
        processed_by=infra["user"].id,
    )
    await db.commit()
    assert sale.payment_status == "REFUNDED"
    assert sale.sale_status == "RETURNED"


@pytest.mark.asyncio
async def test_return_cannot_exceed_quantity_sold(db: AsyncSession) -> None:
    from fastapi import HTTPException

    infra = await create_sale_test_infra(db)
    service, sale = await _completed_sale(db, infra, 2)
    item = sale.items[0]

    with pytest.raises(HTTPException) as exc:
        await service.process_return(
            original_sale=sale,
            return_items_data=[{"sale_item_id": item.id, "quantity": 3}],
            refund_payments=[],
            return_type="PARTIAL",
            reason=None,
            processed_by=infra["user"].id,
        )
    assert exc.value.status_code == 400

    # Stock must be unchanged by the rejected return (50 - 2 sold)
    stock = await InventoryStockRepository(db).get_stock(
        infra["variant"].id, infra["warehouse"].id
    )
    assert stock.quantity == 48


@pytest.mark.asyncio
async def test_loyalty_points_earned_and_clawed_back(db: AsyncSession) -> None:
    from app.models import Customer
    from app.models import Sale as SaleModel
    from app.services.customer_service import CustomerService
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    infra = await create_sale_test_infra(db)
    cust = Customer(
        customer_code="CUST-LOYAL-1",
        name="Loyalty Tester",
        phone="099887766",
        status="ACTIVE",
    )
    db.add(cust)
    await db.flush()

    service = SaleService(db)
    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        customer_id=cust.id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 2,
                "unit_price": Decimal("20.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    # Total is 40.00 (selling_price=20.00 * 2)
    sale = await service.complete_sale(
        sale, [{"payment_method": "CASH", "amount": Decimal("40.00")}]
    )
    await db.commit()

    cust_svc = CustomerService(db)
    cust_loaded = await cust_svc.get_customer(cust.id)
    assert cust_loaded.loyalty_account is not None
    assert cust_loaded.loyalty_account.points_balance == 40
    assert cust_loaded.loyalty_account.total_points_earned == 40

    # Process partial return of 1 unit ($20 refund)
    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_to_return = res.scalar_one()
    item = sale_to_return.items[0]

    await service.process_return(
        original_sale=sale_to_return,
        return_items_data=[{"sale_item_id": item.id, "quantity": 1}],
        refund_payments=[{"payment_method": "CASH", "amount": Decimal("20.00")}],
        return_type="PARTIAL",
        reason="Partial return",
        processed_by=infra["user"].id,
    )
    await db.commit()

    cust_loaded = await cust_svc.get_customer(cust.id)
    assert cust_loaded.loyalty_account.points_balance == 20
    assert cust_loaded.loyalty_account.total_points_earned == 20
