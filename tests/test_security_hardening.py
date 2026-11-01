"""Regression tests for the P0 security fixes (management routes + storefront payments)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models import Sale
from app.models import Role, User
from app.repositories.inventory_repository import InventoryStockRepository
from test_sales import create_sale_test_infra


# ── Management surfaces require authentication ───────────────────────────────

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/systems"),
        ("get", "/api/v1/telegram/bots"),
        ("get", "/api/v1/telegram/chats"),
        ("get", "/api/v1/logs/system"),
        ("get", "/api/v1/logs/telegram-outbound"),
        ("get", "/api/v1/auth/clients"),
        ("get", "/api/admin/v1/auth/clients"),
        ("get", "/api/cashier/v1/auth/clients"),
    ],
)
@pytest.mark.asyncio
async def test_management_routes_reject_anonymous(client: AsyncClient, method: str, path: str) -> None:
    resp = await getattr(client, method)(path)
    assert resp.status_code == 401, f"{path} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_fake_api_key_header_does_not_grant_access(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/systems", headers={"X-API-KEY": "anything", "X-CLIENT-ID": "x"}
    )
    assert resp.status_code == 401


# ── Storefront payments cannot be forged ─────────────────────────────────────

async def _create_order(client: AsyncClient, variant_id, headers=None) -> dict:
    resp = await client.post(
        "/api/store/v1/orders",
        json={
            "items": [{"variant_id": str(variant_id), "quantity": 2}],
            "payment_method": "CASH",
            "create_draft": False,  # legacy "complete immediately" flag must be ignored
            "customer_phone": "012345678",
        },
        headers=headers or {},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_store_order_is_never_paid_on_creation(client: AsyncClient, db: AsyncSession) -> None:
    infra = await create_sale_test_infra(db)
    order = await _create_order(client, infra["variant"].id)

    assert order["sale_status"] == "DRAFT"
    assert order["payment_status"] != "PAID"
    assert order["payments"] == []

    stock = await InventoryStockRepository(db).get_stock(
        infra["variant"].id, infra["warehouse"].id
    )
    assert stock.quantity == 50  # nothing deducted until the gateway approves


@pytest.mark.asyncio
async def test_store_order_complete_requires_gateway_confirmation(
    client: AsyncClient, db: AsyncSession
) -> None:
    infra = await create_sale_test_infra(db)
    order = await _create_order(client, infra["variant"].id)

    resp = await client.post(
        f"/api/store/v1/orders/{order['id']}/complete",
        json={"payment_method": "ABA_KHQR", "reference_number": "FORGED"},
    )
    assert resp.status_code == 402, resp.text

    sale = (await db.execute(select(Sale).where(Sale.invoice_number == order["invoice_number"]))).scalar_one()
    await db.refresh(sale)
    assert sale.sale_status == "DRAFT"

    stock = await InventoryStockRepository(db).get_stock(
        infra["variant"].id, infra["warehouse"].id
    )
    assert stock.quantity == 50


@pytest.mark.asyncio
async def test_guest_orders_not_attributed_to_active_staff(
    client: AsyncClient, db: AsyncSession
) -> None:
    infra = await create_sale_test_infra(db)
    order = await _create_order(client, infra["variant"].id)

    sale = (await db.execute(select(Sale).where(Sale.invoice_number == order["invoice_number"]))).scalar_one()
    actor = await db.get(User, sale.cashier_id)
    assert actor.username == "online_store_guest"
    assert actor.status != "ACTIVE"  # can never log in


@pytest.mark.asyncio
async def test_khqr_never_returns_fabricated_qr_on_gateway_failure(
    client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    from app.services.payway import payway_client

    async def boom(**kwargs):
        raise RuntimeError("gateway offline")

    monkeypatch.setattr(payway_client, "create_khqr", boom)

    infra = await create_sale_test_infra(db)
    order = await _create_order(client, infra["variant"].id)

    resp = await client.post(f"/api/store/v1/orders/{order['id']}/khqr")
    assert resp.status_code == 502, resp.text
    assert "qr_string" not in resp.json()


@pytest.mark.asyncio
async def test_pos_sales_are_not_reachable_through_store_lane(
    client: AsyncClient, db: AsyncSession
) -> None:
    from app.services.sale_service import SaleService

    infra = await create_sale_test_infra(db)
    pos_sale = await SaleService(db).create_sale(
        branch_id=infra["branch"].id,
        warehouse_id=infra["warehouse"].id,
        cashier_id=infra["user"].id,
        items_data=[
            {
                "variant_id": infra["variant"].id,
                "quantity": 1,
                "unit_price": infra["variant"].selling_price,
                "discount_amount": 0,
            }
        ],
    )
    await db.commit()

    for method, suffix in (("get", ""), ("get", "/payment-status"), ("post", "/khqr"), ("post", "/complete")):
        kwargs = {"json": {}} if suffix == "/complete" else {}
        resp = await getattr(client, method)(f"/api/store/v1/orders/{pos_sale.id}{suffix}", **kwargs)
        assert resp.status_code == 404, f"{method} {suffix} -> {resp.status_code}"


@pytest.mark.asyncio
async def test_customer_order_is_private_to_its_owner(client: AsyncClient, db: AsyncSession) -> None:
    infra = await create_sale_test_infra(db)

    role = Role(name="CUSTOMER", description="Web store customer", is_system=True)
    db.add(role)
    await db.flush()
    owner = User(username="cust_a", email="a@example.com", full_name="A",
                 hashed_password=hash_password("x" * 12), status="ACTIVE")
    other = User(username="cust_b", email="b@example.com", full_name="B",
                 hashed_password=hash_password("x" * 12), status="ACTIVE")
    owner.roles = [role]
    other.roles = [role]
    db.add_all([owner, other])
    await db.commit()

    owner_h = {"Authorization": f"Bearer {create_access_token(str(owner.id))}"}
    other_h = {"Authorization": f"Bearer {create_access_token(str(other.id))}"}

    order = await _create_order(client, infra["variant"].id, headers=owner_h)
    url = f"/api/store/v1/orders/{order['id']}"

    assert (await client.get(url, headers=owner_h)).status_code == 200
    assert (await client.get(url, headers=other_h)).status_code == 404
    assert (await client.get(url)).status_code == 404
