"""Tests for Cashier Shift Sessions and Cash Drawer Reconciliation."""
from __future__ import annotations

from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models import Branch, PERMISSION_MODEL, PosTerminal, ROLE_MODEL, User, Warehouse
from app.models import CATEGORY_MODEL, BRAND_MODEL, Color, Size, Product, ProductVariant
from app.services.inventory_service import INVENTORY_SERVICE


@pytest.fixture(autouse=True)
def mock_sale_bg_tasks(monkeypatch):
    async def noop(*args, **kwargs):
        pass
    monkeypatch.setattr("app.tasks.sale_background.bg_record_sale_audit", noop)
    monkeypatch.setattr("app.tasks.sale_background.bg_award_loyalty_points", noop)
    monkeypatch.setattr("app.tasks.sale_background.bg_increment_inventory_cache", noop)


async def setup_shift_test_env(db: AsyncSession):
    branch = Branch(code="SHIFT-BR", name="Shift Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Shift Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    terminal = PosTerminal(
        branch_id=branch.id,
        warehouse_id=warehouse.id,
        code="POS-SHIFT-01",
        name="Shift Register 1",
        status_code="ACTIVE",
    )
    db.add(terminal)
    await db.flush()

    # Permissions for sales & shifts
    sale_perm = PERMISSION_MODEL(code="sale.create", name="Create Sale", module="sales")
    sale_read_perm = PERMISSION_MODEL(code="sale.read", name="Read Sale", module="sales")
    db.add_all([sale_perm, sale_read_perm])
    await db.flush()

    role = ROLE_MODEL(
        name="CASHIER",
        is_system=True,
        permissions=[sale_perm, sale_read_perm],
    )
    db.add(role)
    await db.flush()

    user = User(
        username="cashier_shift_user",
        email="cashier_shift@example.com",
        full_name="Shift Cashier",
        hashed_password=hash_password("password123"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.flush()

    # Product & stock for test sales
    category = CATEGORY_MODEL(name="Shirts", slug="shirts-shift")
    brand = BRAND_MODEL(name="ShiftBrand", slug="shiftbrand")
    color = Color(name="Black", hex_code="#000000")
    size = Size(name="M", type="LETTER")
    db.add_all([category, brand, color, size])
    await db.flush()

    product = Product(
        code="PROD-SHIFT-01",
        name="Shift Tee",
        slug="shift-tee",
        category_id=category.id,
        brand_id=brand.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="SHIFT-TEE-BLK-M",
        qr_reference="VAR-SHIFT-01",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("10.00"),
        selling_price=Decimal("25.00"),
    )
    db.add(variant)
    await db.flush()

    inv_service = INVENTORY_SERVICE(db)
    await inv_service.adjust_stock(
        variant_id=variant.id,
        warehouse_id=warehouse.id,
        quantity_delta=100,
        movement_type="INITIAL_STOCK",
        note="Shift test initial stock",
        created_by=user.id,
    )
    await db.commit()

    token = create_access_token({"sub": str(user.id), "username": user.username})

    return {
        "branch": branch,
        "warehouse": warehouse,
        "terminal": terminal,
        "cashier": user,
        "variant": variant,
        "token": token,
    }


@pytest.mark.asyncio
async def test_shift_lifecycle_and_reconciliation(client: AsyncClient, db: AsyncSession):
    """Test full shift lifecycle: open -> sales auto-link -> summary breakdown -> close."""
    env = await setup_shift_test_env(db)
    headers = {"Authorization": f"Bearer {env['token']}"}
    terminal_id = str(env["terminal"].id)

    # 1. Initially, no active shift
    res = await client.get(f"/api/v1/shifts/active?terminal_id={terminal_id}", headers=headers)
    assert res.status_code == 404

    # 2. Open shift with $100 USD and 400,000 KHR float
    open_payload = {
        "terminal_id": terminal_id,
        "opening_float_usd": 100.00,
        "opening_float_khr": 400000.00,
        "notes": "Morning opening shift",
    }
    open_res = await client.post("/api/v1/shifts/open", json=open_payload, headers=headers)
    assert open_res.status_code == 201
    shift_data = open_res.json()
    shift_id = shift_data["id"]
    assert shift_data["status_code"] == "OPEN"
    assert float(shift_data["opening_float_usd"]) == 100.00
    assert float(shift_data["opening_float_khr"]) == 400000.00

    # 3. Duplicate open attempt on the same terminal must be rejected (400)
    dup_res = await client.post("/api/v1/shifts/open", json=open_payload, headers=headers)
    assert dup_res.status_code == 400
    assert "already has an active open shift" in dup_res.json()["detail"]

    # 4. GET /active now returns the open shift
    active_res = await client.get(f"/api/v1/shifts/active?terminal_id={terminal_id}", headers=headers)
    assert active_res.status_code == 200
    assert active_res.json()["id"] == shift_id

    # 5. Make sales via API - Sale 1: CASH $25.00
    sale1_res = await client.post(
        "/api/v1/sales/",
        headers=headers,
        json={
            "branch_id": str(env["branch"].id),
            "warehouse_id": str(env["warehouse"].id),
            "terminal_id": terminal_id,
            "items": [{
                "variant_id": str(env["variant"].id),
                "quantity": 1,
                "discount_amount": 0,
            }],
            "discount_amount": 0,
            "tax_amount": 0,
            "payments": [{
                "payment_method": "CASH",
                "amount": 25.00,
            }],
        },
    )
    assert sale1_res.status_code == 201
    sale1_data = sale1_res.json()
    assert sale1_data["shift_id"] == shift_id

    # Sale 2: ABA_KHQR $50.00
    sale2_res = await client.post(
        "/api/v1/sales/",
        headers=headers,
        json={
            "branch_id": str(env["branch"].id),
            "warehouse_id": str(env["warehouse"].id),
            "terminal_id": terminal_id,
            "items": [{
                "variant_id": str(env["variant"].id),
                "quantity": 2,
                "discount_amount": 0,
            }],
            "discount_amount": 0,
            "tax_amount": 0,
            "payments": [{
                "payment_method": "ABA_KHQR",
                "amount": 50.00,
            }],
        },
    )
    assert sale2_res.status_code == 201
    sale2_data = sale2_res.json()
    assert sale2_data["shift_id"] == shift_id

    # 6. Check shift summary
    summary_res = await client.get(f"/api/v1/shifts/{shift_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_sales_count"] == 2
    assert float(summary["total_sales_amount"]) == 75.00
    assert float(summary["cash_sales_amount"]) == 25.00
    assert summary["cash_payments_count"] == 1
    assert float(summary["aba_sales_amount"]) == 50.00
    assert summary["aba_payments_count"] == 1
    # Expected cash: $100 float + $25 cash sale = $125
    assert float(summary["expected_cash_usd"]) == 125.00
    assert float(summary["expected_cash_khr"]) == 400000.00

    # 7. Close shift with counted cash = $125.00 USD and 400,000 KHR (Balanced drawer)
    close_payload = {
        "closing_cash_usd": 125.00,
        "closing_cash_khr": 400000.00,
        "notes": "Drawer counts balanced perfectly",
    }
    close_res = await client.post(f"/api/v1/shifts/{shift_id}/close", json=close_payload, headers=headers)
    assert close_res.status_code == 200
    closed = close_res.json()
    assert closed["status_code"] == "CLOSED"
    assert closed["closed_at"] is not None
    assert float(closed["closing_cash_usd"]) == 125.00
    assert float(closed["discrepancy_usd"]) == 0.00
    assert float(closed["discrepancy_khr"]) == 0.00

    # 8. Attempting to close again returns 400
    reclose_res = await client.post(f"/api/v1/shifts/{shift_id}/close", json=close_payload, headers=headers)
    assert reclose_res.status_code == 400

    # 9. Active shift is now None (404)
    active_after_close = await client.get(f"/api/v1/shifts/active?terminal_id={terminal_id}", headers=headers)
    assert active_after_close.status_code == 404
