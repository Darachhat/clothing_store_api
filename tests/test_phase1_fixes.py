"""Comprehensive Phase 1 verification tests for security, schema alignment, and API contract fixes."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Branch, Warehouse
from app.models import Customer
from app.models import ExpenseCategory
from app.models import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.models import Permission, Role, User
from app.schemas.expense_schema import EXPENSE_CREATE_SCHEMA
from app.schemas.inventory_schema import STOCK_ADJUSTMENT_CREATE_SCHEMA
from app.schemas.promotion_schema import PROMOTION_CREATE_SCHEMA
from app.schemas.telegram_schema import TELEGRAM_BOT_RESPONSE_SCHEMA
from app.services.inventory_service import InventoryService


async def setup_admin_env(db: AsyncSession):
    branch = Branch(code="PH1-BR", name="Phase1 Main Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Phase1 Main Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    category = Category(name="Phase1 Shirts", slug="phase1-shirts")
    brand = Brand(name="Phase1Brand", slug="phase1brand")
    color = Color(name="Navy", hex_code="#000080")
    size = Size(name="XL", type="LETTER")
    supplier = Supplier(code="SUP-PH1", name="Phase1 Supplier", phone="012345678")
    db.add_all([category, brand, color, size, supplier])
    await db.flush()

    product = Product(
        code="PH1-PROD-001",
        name="Phase1 Oxford Shirt",
        slug="phase1-oxford-shirt",
        category_id=category.id,
        brand_id=brand.id,
        supplier_id=supplier.id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="PH1-NVY-XL-001",
        qr_reference="VAR-PH1-001",
        barcode="885000000001",
        color_id=color.id,
        size_id=size.id,
        cost_price=Decimal("10.00"),
        selling_price=Decimal("25.00"),
    )
    db.add(variant)
    await db.flush()

    perm_codes = [
        "product.read",
        "product.create",
        "product.update",
        "product.delete",
        "branch.read",
        "branch.create",
        "branch.update",
        "branch.delete",
        "inventory.read",
        "inventory.adjust",
        "inventory.transfer",
        "purchase.read",
        "purchase.create",
        "purchase.receive",
        "customer.read",
        "customer.create",
        "customer.update",
        "customer.delete",
        "report.read",
        "settings.manage",
    ]
    perms = [
        Permission(code=code, name=code, module=code.split(".")[0])
        for code in perm_codes
    ]
    db.add_all(perms)
    await db.flush()

    admin_role = Role(name="ADMIN", is_system=True, permissions=perms)
    customer_role = Role(name="CUSTOMER", is_system=True)
    db.add_all([admin_role, customer_role])
    await db.flush()

    admin_user = User(
        username="phase1_admin",
        email="phase1_admin@example.com",
        full_name="Phase1 Admin",
        hashed_password=hash_password("admin_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[admin_role],
    )
    db.add(admin_user)
    await db.flush()

    inv_service = InventoryService(db)
    await inv_service.adjust_stock(
        variant_id=variant.id,
        warehouse_id=warehouse.id,
        quantity_delta=25,
        movement_type="INITIAL_STOCK",
        note="Initial Phase 1 stock",
        created_by=admin_user.id,
    )
    await db.commit()

    return {
        "branch": branch,
        "warehouse": warehouse,
        "category": category,
        "brand": brand,
        "color": color,
        "size": size,
        "supplier": supplier,
        "product": product,
        "variant": variant,
        "admin_user": admin_user,
        "admin_role": admin_role,
        "customer_role": customer_role,
    }


def test_schema_normalizers_and_security_redaction() -> None:
    """Verify synchronous schema normalizers and Telegram token masking."""
    # 1. STOCK_ADJUSTMENT_CREATE_SCHEMA alias normalization (ADD / REMOVE / SET)
    adj_add = STOCK_ADJUSTMENT_CREATE_SCHEMA.model_validate(
        {
            "variant_id": "00000000-0000-0000-0000-000000000001",
            "warehouse_id": "00000000-0000-0000-0000-000000000002",
            "adjustment_type": "ADD",
            "quantity": 10,
            "reason": "Count surplus",
        }
    )
    assert adj_add.quantity_delta == 10
    assert adj_add.note == "Count surplus"

    adj_remove = STOCK_ADJUSTMENT_CREATE_SCHEMA.model_validate(
        {
            "variant_id": "00000000-0000-0000-0000-000000000001",
            "warehouse_id": "00000000-0000-0000-0000-000000000002",
            "adjustment_type": "REMOVE",
            "quantity": 4,
            "reason": "Damaged item",
        }
    )
    assert adj_remove.quantity_delta == -4
    assert adj_remove.movement_type == "ADJUSTMENT"

    # 2. PROMOTION_CREATE_SCHEMA frontend field normalization
    promo = PROMOTION_CREATE_SCHEMA.model_validate(
        {
            "name": "Summer Flash",
            "code": "SUMMER20",
            "discount_type": "PERCENTAGE",
            "discount_value": "20.00",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
            "is_active": True,
        }
    )
    assert promo.type == "PERCENTAGE"
    assert promo.value == Decimal("20.00")
    assert promo.status == "ACTIVE"

    # 3. EXPENSE_CREATE_SCHEMA nil UUID branch resolution
    exp = EXPENSE_CREATE_SCHEMA.model_validate(
        {
            "category_id": "00000000-0000-0000-0000-000000000001",
            "branch_id": "00000000-0000-0000-0000-000000000000",
            "amount": "50.00",
            "expense_date": "2026-06-01",
        }
    )
    assert exp.branch_id is None

    # 4. Telegram bot token masking
    bot_resp = TELEGRAM_BOT_RESPONSE_SCHEMA(
        id="00000000-0000-0000-0000-000000000099",
        code="BOT-1",
        name="StoreBot",
        token="123456789:ABCDEF_secret_bot_token_9876",
        status_code="active",
    )
    assert "secret_bot_token" not in (bot_resp.token or "")
    assert "***" in (bot_resp.token or "")

    # 5. Verify all new Phase 1 routes are registered in FastAPI app
    from app.main import app

    route_paths = {getattr(r, "path", "") for r in app.routes}
    expected_paths = {
        "/api/v1/warehouses",
        "/api/v1/warehouses/{id}",
        "/api/v1/branches/{id}",
        "/api/v1/products/{id}/variants",
        "/api/v1/product-variants/qr/{reference}",
        "/api/v1/product-variants/barcode/{barcode}",
        "/api/v1/product-variants/sku/{sku}",
        "/api/v1/product-variants/{id}/regenerate-codes",
        "/api/v1/inventory",
        "/api/v1/inventory/low-stock",
        "/api/v1/inventory/transfers/{id}/complete",
        "/api/v1/purchases/{order_id}/receive",
        "/api/v1/sales/returns",
        "/api/v1/sales/{id}/receipt",
        "/api/v1/sales/{id}/return",
        "/api/v1/customers/{customer_id}",
        "/api/v1/customers/{customer_id}/loyalty",
        "/api/v1/customers/{customer_id}/loyalty/adjust",
        "/api/v1/expenses/{expense_id}",
        "/api/v1/expenses/categories/{cat_id}",
        "/api/v1/reports/sales/export-csv",
        "/api/v1/reports/profit-loss",
        "/api/v1/reports/expenses",
        "/api/v1/labels/presets",
        "/api/v1/roles/{role_id}",
        "/api/v1/uploads/images",
        "/api/v1/audit-logs",
        "/api/admin/v1/audit-logs",
        "/api/store/v1/orders",
        "/api/store/v1/orders/{order_id}",
        "/api/store/v1/orders/{order_id}/khqr",
        "/api/store/v1/orders/{order_id}/payment-status",
        "/api/store/v1/orders/{order_id}/complete",
        "/api/store/v1/orders/validate-coupon",
    }
    missing = expected_paths - route_paths
    assert not missing, f"Missing expected routes: {missing}"


@pytest.mark.asyncio
async def test_storefront_product_detail_and_duplicate_email(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify GET /api/store/v1/catalog/products/{id} returns 200 with variants & stock, and duplicate registration returns 400."""
    from app.services.payway import payway_client

    async def mock_create_khqr(**kwargs):
        return {
            "status": {"code": "00"},
            "qrString": "00020101021200000000",
            "qrImage": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
            "abapay_deeplink": "https://link.payway.com.kh/mock",
        }

    async def mock_check_transaction(tran_id: str):
        return {"status": {"code": "00"}, "data": {"payment_status": "APPROVED", "apv": "MOCK-APV-123"}}

    async def mock_get_transaction_detail(tran_id: str):
        return {"status": {"code": "00"}, "data": {"payment_type": "KHQR", "payer_account": "012345"}}

    from app.tasks import notification_tasks
    monkeypatch.setattr(notification_tasks.send_telegram, "delay", lambda *a, **k: None)

    monkeypatch.setattr(payway_client, "create_khqr", mock_create_khqr)
    monkeypatch.setattr(payway_client, "check_transaction", mock_check_transaction)
    monkeypatch.setattr(payway_client, "get_transaction_detail", mock_get_transaction_detail)

    env = await setup_admin_env(db)
    product = env["product"]

    # 1. Public product detail must not raise MissingGreenlet and must include stock
    resp = await client.get(f"/api/store/v1/catalog/products/{product.id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == str(product.id)
    assert len(data["variants"]) == 1
    assert data["variants"][0]["color"] == "Navy"
    assert data["variants"][0]["size"] == "XL"
    assert data["variants"][0]["stock"] == 25

    # 2. Customer registration & duplicate email check (400 instead of 500)
    reg_payload = {
        "full_name": "Jane Customer",
        "email": "jane.customer@example.com",
        "phone": "099887766",
        "password": "customer_pass123",
    }
    r1 = await client.post("/api/store/v1/auth/register", json=reg_payload)
    assert r1.status_code == 201, r1.text

    r2 = await client.post("/api/store/v1/auth/register", json=reg_payload)
    assert r2.status_code == 400, r2.text

    # 3. Storefront customer login, order placement, stock deduction & order history
    login_r = await client.post(
        "/api/store/v1/auth/login",
        json={"username": "jane.customer@example.com", "password": "customer_pass123"},
    )
    assert login_r.status_code == 200, login_r.text
    cust_token = login_r.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    variant = env["variant"]
    order_r = await client.post(
        "/api/store/v1/orders",
        headers=cust_headers,
        json={
            "items": [{"variant_id": str(variant.id), "quantity": 2}],
            "payment_method": "ABA_KHQR",
            "customer_name": "Jane Customer",
            "customer_phone": "099887766",
            "shipping_address": "123 Norodom Blvd, Phnom Penh",
        },
    )
    assert order_r.status_code == 201, order_r.text
    order_data = order_r.json()
    assert order_data["sale_status"] == "DRAFT"
    assert order_data["payment_status"] == "PENDING"
    assert order_data["total"] == 50.0

    # Generate KHQR transaction for the order
    khqr_step3 = await client.post(
        f"/api/store/v1/orders/{order_data['id']}/khqr",
        headers=cust_headers,
    )
    assert khqr_step3.status_code == 201, khqr_step3.text

    # Complete order after payment gateway confirmation
    comp_step3 = await client.post(
        f"/api/store/v1/orders/{order_data['id']}/complete",
        headers=cust_headers,
        json={"payment_method": "ABA_KHQR"},
    )
    assert comp_step3.status_code == 200, comp_step3.text
    assert comp_step3.json()["sale_status"] == "COMPLETED"
    assert comp_step3.json()["payment_status"] == "PAID"

    # Verify stock decreased from 25 to 23 on public product detail
    resp_after = await client.get(f"/api/store/v1/catalog/products/{product.id}")
    assert resp_after.status_code == 200
    assert resp_after.json()["variants"][0]["stock"] == 23

    # Verify customer order history endpoint
    hist_r = await client.get("/api/store/v1/orders", headers=cust_headers)
    assert hist_r.status_code == 200
    assert len(hist_r.json()) == 1
    assert hist_r.json()[0]["id"] == order_data["id"]

    # 4. Storefront DRAFT order + KHQR generation + payment status polling + order completion
    draft_r = await client.post(
        "/api/store/v1/orders",
        headers=cust_headers,
        json={
            "items": [{"variant_id": str(variant.id), "quantity": 1}],
            "payment_method": "ABA_KHQR",
            "customer_name": "Jane Customer",
            "customer_phone": "099887766",
            "create_draft": True,
        },
    )
    assert draft_r.status_code == 201, draft_r.text
    draft_order = draft_r.json()
    assert draft_order["sale_status"] == "DRAFT"

    khqr_r = await client.post(
        f"/api/store/v1/orders/{draft_order['id']}/khqr",
        headers=cust_headers,
    )
    assert khqr_r.status_code == 201, khqr_r.text
    khqr_data = khqr_r.json()
    assert khqr_data["qr_image"] is not None
    assert khqr_data["qr_image"].startswith("data:image/png;base64,")

    poll_r = await client.get(
        f"/api/store/v1/orders/{draft_order['id']}/payment-status",
        headers=cust_headers,
    )
    assert poll_r.status_code == 200, poll_r.text
    assert poll_r.json()["sale_status"] == "COMPLETED"

    comp_r = await client.post(
        f"/api/store/v1/orders/{draft_order['id']}/complete",
        headers=cust_headers,
        json={"payment_method": "ABA_KHQR"},
    )
    assert comp_r.status_code == 200, comp_r.text
    assert comp_r.json()["sale_status"] == "COMPLETED"
    assert comp_r.json()["payment_status"] == "PAID"


@pytest.mark.asyncio
async def test_phase1_admin_and_pos_endpoints(client: AsyncClient, db: AsyncSession) -> None:
    """Verify new and fixed endpoints across products, variants, branches, warehouses, inventory, purchases, sales, customers, reports, and labels."""
    env = await setup_admin_env(db)

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "phase1_admin", "password": "admin_pass123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Product variant lookup aliases (/qr/, /barcode/, /sku/) and regenerate-codes
    variant = env["variant"]
    r_qr = await client.get(f"/api/v1/product-variants/qr/{variant.qr_reference}", headers=headers)
    assert r_qr.status_code == 200
    r_bc = await client.get(f"/api/v1/product-variants/barcode/{variant.barcode}", headers=headers)
    assert r_bc.status_code == 200
    r_sku = await client.get(f"/api/v1/product-variants/sku/{variant.sku}", headers=headers)
    assert r_sku.status_code == 200
    r_regen = await client.post(
        f"/api/v1/product-variants/{variant.id}/regenerate-codes", headers=headers
    )
    assert r_regen.status_code == 200

    # 2. Warehouses & Branches CRUD
    r_wh = await client.get("/api/v1/warehouses", headers=headers)
    assert r_wh.status_code == 200
    assert len(r_wh.json()) >= 1

    # 3. Inventory root alias & low-stock
    r_inv = await client.get("/api/v1/inventory", headers=headers)
    assert r_inv.status_code == 200
    inv_items = r_inv.json()
    assert len(inv_items) >= 1
    assert inv_items[0]["sku"] == variant.sku

    r_low = await client.get("/api/v1/inventory/low-stock", headers=headers)
    assert r_low.status_code == 200

    # 4. Simplified PO creation (without branch_id/warehouse_id) & /purchases/{id}/receive
    r_po = await client.post(
        "/api/v1/purchases",
        headers=headers,
        json={
            "supplier_id": str(env["supplier"].id),
            "items": [
                {
                    "variant_id": str(variant.id),
                    "quantity_ordered": 5,
                    "unit_cost": "10.00",
                }
            ],
        },
    )
    assert r_po.status_code == 201, r_po.text
    po_id = r_po.json()["id"]

    r_rec = await client.post(
        f"/api/v1/purchases/{po_id}/receive",
        headers=headers,
        json={
            "note": "Quick receive from stock_manager_front",
            "items": [{"variant_id": str(variant.id), "quantity_received": 5}],
        },
    )
    assert r_rec.status_code == 201, r_rec.text

    # 5. Customer loyalty endpoints
    cust = Customer(
        customer_code="CUST-PH1",
        name="Loyal Shopper",
        phone="011223344",
    )
    db.add(cust)
    await db.commit()
    await db.refresh(cust)

    r_loy_adj = await client.post(
        f"/api/v1/customers/{cust.id}/loyalty/adjust",
        headers=headers,
        json={"points_delta": 50, "reason": "Welcome bonus"},
    )
    assert r_loy_adj.status_code == 200, r_loy_adj.text
    assert r_loy_adj.json()["points_balance"] == 50
    assert len(r_loy_adj.json()["transactions"]) == 1

    # 6. Reports & Labels presets
    r_pl = await client.get("/api/v1/reports/profit-loss", headers=headers)
    assert r_pl.status_code == 200
    r_exp_rep = await client.get("/api/v1/reports/expenses", headers=headers)
    assert r_exp_rep.status_code == 200
    r_csv = await client.get("/api/v1/reports/sales/export-csv", headers=headers)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers.get("content-type", "")
    r_presets = await client.get("/api/v1/labels/presets", headers=headers)
    assert r_presets.status_code == 200
    assert len(r_presets.json()) >= 1

    # 7. Phase 3: Domain audit logs (public.audit_logs) recorded and queryable via GET /api/v1/audit-logs
    r_audit = await client.get("/api/v1/audit-logs", headers=headers)
    assert r_audit.status_code == 200, r_audit.text
    audit_entries = r_audit.json()
    assert len(audit_entries) >= 2
    actions = {entry["action"] for entry in audit_entries}
    assert "INVENTORY_INITIAL_STOCK" in actions
    assert "GOODS_RECEIPT_CREATED" in actions

    # 8. Phase 3: Unauthenticated variant lookup (/by-qr, /by-sku, /by-barcode) must require auth (401/403)
    unauth_qr = await client.get(f"/api/v1/product-variants/by-qr/{variant.qr_reference}")
    assert unauth_qr.status_code in (401, 403)
    unauth_upload_list = await client.get("/api/v1/attachments")
    assert unauth_upload_list.status_code in (401, 403)
