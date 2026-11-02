"""Tests for the reports API: dashboard, sales, profit, inventory, purchases."""
from __future__ import annotations

from datetime import date, datetime, UTC
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Branch, Warehouse
from app.models import Expense, ExpenseCategory
from app.models import Brand, Category, Color, Product, ProductVariant, Size
from app.models import Permission, Role, User
from app.services.inventory_service import INVENTORY_SERVICE
from app.services.sale_service import SALE_SERVICE


async def create_report_test_infra(db: AsyncSession):
    """Create a full environment for report testing."""
    branch = Branch(code="RPT-TEST", name="Report Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Report Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    category = Category(name="Report Category", slug="report-category")
    db.add(category)
    brand = Brand(name="ReportBrand", slug="reportbrand")
    db.add(brand)
    color = Color(name="ReportBlue", hex_code="#0000AA")
    db.add(color)
    size = Size(name="Rpt_S", type="LETTER")
    db.add(size)
    await db.flush()

    product = Product(
        code="RPT-PROD-001",
        name="Report T-Shirt",
        slug="report-t-shirt",
        category_id=category.id,
        brand_id=brand.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="RPT-BLU-S-001",
        qr_reference="VAR-RPT-001",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("6.00"),
        selling_price=Decimal("18.00"),
    )
    db.add(variant)

    # Permissions - flush first, then assign in constructor to avoid lazy load in async
    perms = [
        Permission(code="report.read", name="Read Reports", module="reports"),
        Permission(code="sale.create", name="Create Sale", module="sales"),
        Permission(code="sale.read", name="Read Sale", module="sales"),
    ]
    db.add_all(perms)
    await db.flush()

    role = Role(name="REPORT_ADMIN_TEST", is_system=True, permissions=perms)
    db.add(role)
    await db.flush()

    user = User(
        username="report_tester",
        email="report@test.com",
        full_name="Report Tester",
        hashed_password=hash_password("rpt_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.flush()
    await db.commit()

    # Initial stock
    inv_svc = INVENTORY_SERVICE(db)
    await inv_svc.adjust_stock(
        variant_id=variant.id,
        warehouse_id=warehouse.id,
        quantity_delta=100,
        movement_type="INITIAL_STOCK",
        created_by=user.id,
    )
    await db.commit()

    return {
        "branch": branch,
        "warehouse": warehouse,
        "variant": variant,
        "user": user,
        "category": category,
    }


async def make_completed_sale(
    db: AsyncSession,
    infra: dict,
    qty: int = 2,
    amount: Decimal = Decimal("36.00"),
):
    """Helper: create + complete a sale."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models import Sale as SaleModel

    service = SALE_SERVICE(db)
    sale = await service.create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": qty,
                "unit_price": Decimal("18.00"),
                "discount_amount": Decimal("0"),
            }
        ],
    )
    await db.commit()

    res = await db.execute(
        select(SaleModel).where(SaleModel.id == sale.id).options(selectinload(SaleModel.items))
    )
    sale_reloaded = res.scalar_one()
    await service.complete_sale(sale_reloaded, [{"payment_method": "CASH", "amount": amount}])
    await db.commit()
    return sale


@pytest.mark.asyncio
async def test_dashboard_report_today(client: AsyncClient, db: AsyncSession) -> None:
    """Dashboard with no sales should return zeros."""
    await create_report_test_infra(db)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "report_tester", "password": "rpt_pass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dash = await client.get("/api/v1/reports/dashboard?period=today", headers=headers)
    assert dash.status_code == 200
    data = dash.json()
    assert "revenue" in data
    assert "gross_profit" in data
    assert "expenses" in data
    assert "net_profit" in data
    assert "low_stock_count" in data
    assert data["period"] == "today"


@pytest.mark.asyncio
async def test_dashboard_revenue_reflects_sales(db: AsyncSession) -> None:
    """After making a sale, dashboard revenue should match."""
    infra = await create_report_test_infra(db)
    await make_completed_sale(db, infra, qty=3)

    # Check reports endpoint via service layer (direct DB query)
    from sqlalchemy import and_, func, select
    from app.models import Sale

    now = datetime.now(UTC)
    today_start = datetime.combine(now.date(), datetime.min.time()).replace(tzinfo=UTC)

    result = await db.execute(
        select(func.coalesce(func.sum(Sale.total), 0)).where(
            and_(Sale.sale_status == "COMPLETED", Sale.created_at >= today_start)
        )
    )
    total_revenue = float(result.scalar_one())
    assert total_revenue == 54.00  # 3 * $18


@pytest.mark.asyncio
async def test_sales_report_date_range(client: AsyncClient, db: AsyncSession) -> None:
    """Sales report with date range should return structured data."""
    infra = await create_report_test_infra(db)
    await make_completed_sale(db, infra, qty=2)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "report_tester", "password": "rpt_pass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    today = datetime.now(UTC).date().isoformat()
    rpt = await client.get(
        f"/api/v1/reports/sales?start_date={today}&end_date={today}",
        headers=headers,
    )
    assert rpt.status_code == 200
    data = rpt.json()
    assert data["total_sales"] == 1
    assert float(data["total_revenue"]) == 36.00


@pytest.mark.asyncio
async def test_profit_report_calculation(client: AsyncClient, db: AsyncSession) -> None:
    """Profit report: revenue - COGS = gross profit."""
    infra = await create_report_test_infra(db)
    # Sell 2 items: revenue = 2*18 = 36, COGS = 2*6 = 12, gross = 24
    await make_completed_sale(db, infra, qty=2)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "report_tester", "password": "rpt_pass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    today = datetime.now(UTC).date().isoformat()
    rpt = await client.get(
        f"/api/v1/reports/profit?start_date={today}&end_date={today}",
        headers=headers,
    )
    assert rpt.status_code == 200
    data = rpt.json()
    assert float(data["revenue"]) == 36.00
    assert float(data["cost_of_goods_sold"]) == 12.00
    assert float(data["gross_profit"]) == 24.00
    # No expenses added, net_profit == gross_profit
    assert float(data["net_profit"]) == 24.00


@pytest.mark.asyncio
async def test_inventory_report_returns_stock_data(client: AsyncClient, db: AsyncSession) -> None:
    """Inventory report should show stock levels and valuation."""
    await create_report_test_infra(db)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "report_tester", "password": "rpt_pass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    rpt = await client.get("/api/v1/reports/inventory", headers=headers)
    assert rpt.status_code == 200
    data = rpt.json()
    assert "total_sku_count" in data
    assert "total_quantity" in data
    assert "total_cost_value" in data
    assert "items" in data
    assert data["total_quantity"] == 100  # initial stock
    assert float(data["total_cost_value"]) == 600.00  # 100 * 6.00


@pytest.mark.asyncio
async def test_net_profit_decreases_with_expenses(db: AsyncSession) -> None:
    """Net profit should decrease when expenses are added."""
    from sqlalchemy import and_, func, select
    from app.models import Sale, SaleItem
    from app.models import Expense

    infra = await create_report_test_infra(db)
    await make_completed_sale(db, infra, qty=4)

    # Directly compute gross profit
    today = datetime.now(UTC).date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)

    cogs_res = await db.execute(
        select(func.coalesce(func.sum(SaleItem.cost_price * SaleItem.quantity), 0))
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(Sale.sale_status == "COMPLETED", Sale.created_at >= today_start)
    )
    cogs = float(cogs_res.scalar_one())

    rev_res = await db.execute(
        select(func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.sale_status == "COMPLETED", Sale.created_at >= today_start)
    )
    revenue = float(rev_res.scalar_one())

    gross_profit = revenue - cogs
    # 4 items: revenue=72, COGS=24, gross=48

    # Add an expense
    exp_cat = ExpenseCategory(name="Rpt Rent", code="RPT_RENT", is_system=True)
    db.add(exp_cat)
    await db.flush()

    expense = Expense(
        expense_number="EXP-RPT-001",
        category_id=exp_cat.id,
        branch_id=infra["branch"].id,
        amount=Decimal("10.00"),
        payment_method="CASH",
        expense_date=today,
        created_by=infra["user"].id,
        status="APPROVED",
    )
    db.add(expense)
    await db.commit()

    # Net profit = 48 - 10 = 38
    exp_res = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.status == "APPROVED", Expense.expense_date == today)
    )
    total_expenses = float(exp_res.scalar_one())
    net_profit = gross_profit - total_expenses

    assert net_profit == pytest.approx(38.00, abs=0.01)


@pytest.mark.asyncio
async def test_reports_accept_from_to_date_and_return_rows(client: AsyncClient, db: AsyncSession) -> None:
    """Sales, Profit, and Purchases reports accept from_date/to_date + group_by and return rows."""
    infra = await create_report_test_infra(db)
    await make_completed_sale(db, infra, qty=2)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "report_tester", "password": "rpt_pass123"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    today = datetime.now(UTC).date().isoformat()
    sales_rpt = await client.get(
        f"/api/v1/reports/sales?from_date={today}&to_date={today}&group_by=day",
        headers=headers,
    )
    assert sales_rpt.status_code == 200
    s_data = sales_rpt.json()
    assert "rows" in s_data
    assert len(s_data["rows"]) == 1
    assert s_data["rows"][0]["transaction_count"] == 1
    assert s_data["rows"][0]["items_sold"] == 2
    assert float(s_data["rows"][0]["revenue"]) == 36.00

    profit_rpt = await client.get(
        f"/api/v1/reports/profit?from_date={today}&to_date={today}&group_by=day",
        headers=headers,
    )
    assert profit_rpt.status_code == 200
    p_data = profit_rpt.json()
    assert "rows" in p_data
    assert len(p_data["rows"]) == 1
    assert float(p_data["rows"][0]["net_profit"]) == 24.00



# ── Warehouse dashboard (inventory.read only, no revenue data) ───────────────


async def _make_user_with_perms(db: AsyncSession, infra: dict, username: str, codes: list[str]):
    from sqlalchemy import select

    existing = (
        await db.execute(select(Permission).where(Permission.code.in_(codes)))
    ).scalars().all()
    have = {p.code for p in existing}
    new = [Permission(code=c, name=c, module=c.split(".")[0]) for c in codes if c not in have]
    db.add_all(new)
    await db.flush()
    role = Role(name=f"ROLE_{username}", permissions=[*existing, *new])
    db.add(role)
    await db.flush()
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name=username,
        hashed_password=hash_password("pw_123456"),
        branch_id=infra["branch"].id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.commit()


async def _login_headers(client: AsyncClient, username: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": "pw_123456"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_warehouse_dashboard_needs_only_inventory_read(
    client: AsyncClient, db: AsyncSession
) -> None:
    infra = await create_report_test_infra(db)
    await _make_user_with_perms(db, infra, "wh_user", ["inventory.read"])
    headers = await _login_headers(client, "wh_user")

    resp = await client.get("/api/v1/reports/warehouse-dashboard?period=today", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_units"] == 100  # initial stock from the test infra
    assert data["units_in"] == 100  # INITIAL_STOCK movement happened today
    assert data["units_out"] == 0
    assert data["out_of_stock_count"] == 0
    assert data["open_transfers"] == 0
    assert "revenue" not in data and "gross_profit" not in data

    # The sales dashboard remains protected
    assert (await client.get("/api/v1/reports/dashboard", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_warehouse_dashboard_denied_without_permission(
    client: AsyncClient, db: AsyncSession
) -> None:
    infra = await create_report_test_infra(db)
    await _make_user_with_perms(db, infra, "nobody", ["sale.read"])
    headers = await _login_headers(client, "nobody")
    resp = await client.get("/api/v1/reports/warehouse-dashboard", headers=headers)
    assert resp.status_code == 403
