"""Comprehensive tests for Telegram Login Authentication, Phone Number Linking/Normalization, Admin Role Management, and Lane Authorization."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.core.utils.phone_utils import get_equivalent_phone_formats, normalize_phone_number
from app.core.utils.telegram_auth import compute_telegram_login_hash
from app.models import Branch, Permission, Role, User, Warehouse
from app.services.auth_service import AUTH_SERVICE

TEST_BOT_TOKEN = "123456789:AAH_test_bot_secret_token_for_hmac_verification"


def build_signed_telegram_payload(
    *,
    telegram_id: int | str = 99887766,
    first_name: str = "System",
    last_name: str = "Admin",
    username: str = "sys_admin_tg",
    auth_date: int | None = None,
    bot_token: str = TEST_BOT_TOKEN,
    tamper_hash: str | None = None,
) -> dict[str, Any]:
    if auth_date is None:
        auth_date = int(datetime.now(UTC).timestamp())
    payload: dict[str, Any] = {
        "id": telegram_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "auth_date": auth_date,
    }
    payload["hash"] = tamper_hash or compute_telegram_login_hash(payload, bot_token)
    return payload


async def seed_roles_and_users(db: AsyncSession) -> dict[str, Any]:
    AUTH_SERVICE.reset_rate_limits()
    settings.TELEGRAM_BOT_TOKEN = TEST_BOT_TOKEN
    settings.TELEGRAM_BOT_USERNAME = "clothing_store_test_bot"

    branch = Branch(code="HQ", name="HQ Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Main Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    perm_defs = [
        ("product.read", "Read Products", "product"),
        ("inventory.read", "Read Inventory", "inventory"),
        ("inventory.adjust", "Adjust Inventory", "inventory"),
        ("sale.read", "Read Sales", "sale"),
        ("sale.create", "Create Sales", "sale"),
        ("user.manage", "Manage Users", "user"),
        ("settings.manage", "Manage Settings", "settings"),
        ("report.view", "View Reports", "report"),
    ]
    perms: dict[str, Permission] = {}
    for code, name, module in perm_defs:
        p = Permission(code=code, name=name, module=module)
        db.add(p)
        perms[code] = p
    await db.flush()

    admin_role = Role(
        name="ADMIN",
        description="System Administrator",
        is_system=True,
        permissions=list(perms.values()),
    )
    manager_role = Role(
        name="MANAGER",
        description="Store Manager",
        is_system=True,
        permissions=[perms["product.read"], perms["inventory.read"], perms["sale.read"], perms["report.view"]],
    )
    warehouse_role = Role(
        name="WAREHOUSE",
        description="Stock Manager",
        is_system=True,
        permissions=[perms["product.read"], perms["inventory.read"], perms["inventory.adjust"]],
    )
    cashier_role = Role(
        name="CASHIER",
        description="POS Cashier",
        is_system=True,
        permissions=[perms["product.read"], perms["inventory.read"], perms["sale.read"], perms["sale.create"]],
    )
    customer_role = Role(
        name="CUSTOMER",
        description="Storefront Customer",
        is_system=True,
        permissions=[],
    )
    db.add_all([admin_role, manager_role, warehouse_role, cashier_role, customer_role])
    await db.flush()

    admin_user = User(
        employee_code="EMP-001",
        username="admin",
        email="admin@example.com",
        full_name="System Administrator",
        hashed_password=hash_password("admin_pass_123"),
        branch_id=branch.id,
        phone_number="+85569382165",
        phone_verified_at=datetime.now(UTC),
        status="ACTIVE",
        roles=[admin_role],
    )
    manager_user = User(
        employee_code="EMP-002",
        username="manager",
        email="manager@example.com",
        full_name="Store Manager",
        hashed_password=hash_password("manager_pass_123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[manager_role],
    )
    warehouse_user = User(
        employee_code="EMP-003",
        username="warehouse",
        email="warehouse@example.com",
        full_name="Warehouse Staff",
        hashed_password=hash_password("warehouse_pass_123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[warehouse_role],
    )
    cashier_user = User(
        employee_code="EMP-004",
        username="cashier",
        email="cashier@example.com",
        full_name="Front Cashier",
        hashed_password=hash_password("cashier_pass_123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[cashier_role],
    )
    customer_user = User(
        username="customer1",
        email="customer1@example.com",
        full_name="Online Shopper",
        hashed_password=hash_password("customer_pass_123"),
        status="ACTIVE",
        roles=[customer_role],
    )
    db.add_all([admin_user, manager_user, warehouse_user, cashier_user, customer_user])
    await db.commit()

    return {
        "roles": {
            "ADMIN": admin_role,
            "MANAGER": manager_role,
            "WAREHOUSE": warehouse_role,
            "CASHIER": cashier_role,
            "CUSTOMER": customer_role,
        },
        "users": {
            "admin": admin_user,
            "manager": manager_user,
            "warehouse": warehouse_user,
            "cashier": cashier_user,
            "customer": customer_user,
        },
    }


async def login_and_get_tokens(client: AsyncClient, username: str, password: str) -> dict[str, Any]:
    res = await client.post("/api/admin/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


# ── 1. Phone Normalization Unit & Login Tests ─────────────────────────────────

def test_phone_normalization_rules() -> None:
    assert normalize_phone_number("+855069382165") == "+85569382165"
    assert normalize_phone_number("+85569382165") == "+85569382165"
    assert normalize_phone_number("069382165") == "+85569382165"
    assert normalize_phone_number("855069382165") == "+85569382165"
    assert normalize_phone_number("85569382165") == "+85569382165"
    assert normalize_phone_number("+855 069 382-165") == "+85569382165"

    variants = get_equivalent_phone_formats("+855069382165")
    assert "+85569382165" in variants
    assert "+855069382165" in variants
    assert "069382165" in variants

    with pytest.raises(ValueError):
        normalize_phone_number("@telegram_handle")
    with pytest.raises(ValueError):
        normalize_phone_number("not_a_phone")
    with pytest.raises(ValueError):
        normalize_phone_number("123")


@pytest.mark.asyncio
async def test_login_with_migrated_phone_number_formats(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)

    # Login using raw unnormalized phone +855069382165, canonical E.164 +85569382165, and local 069382165
    for phone_input in ("+855069382165", "+85569382165", "069382165"):
        res = await client.post(
            "/api/admin/v1/auth/login",
            json={"username": phone_input, "password": "admin_pass_123"},
        )
        assert res.status_code == 200, f"Failed for {phone_input}: {res.text}"
        body = res.json()
        assert body["user"]["username"] == "admin"
        assert body["user"]["phone_number"] == "+85569382165"
        assert body["user"]["phone_verified"] is True
        assert [r["name"] for r in body["user"]["roles"]] == ["ADMIN"]


# ── 2. Telegram Authentication Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_telegram_link_and_successful_login(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # Check public Telegram config endpoint (must never expose bot token)
    cfg_res = await client.get("/api/admin/v1/auth/telegram/config")
    assert cfg_res.status_code == 200
    cfg_data = cfg_res.json()
    assert cfg_data["enabled"] is True
    assert cfg_data["bot_username"] == "clothing_store_test_bot"
    assert "token" not in cfg_data

    # Link Telegram identity to existing admin account
    link_payload = build_signed_telegram_payload(telegram_id=777888999, username="admin_tg")
    link_res = await client.post("/api/admin/v1/auth/telegram/link", json=link_payload, headers=headers)
    assert link_res.status_code == 200, link_res.text
    linked_user = link_res.json()
    assert linked_user["telegram_id"] == "777888999"
    assert linked_user["telegram_username"] == "admin_tg"
    assert linked_user["phone_number"] == "+85569382165"
    assert [r["name"] for r in linked_user["roles"]] == ["ADMIN"]

    # Now sign in via Telegram with a fresh signed payload
    login_payload = build_signed_telegram_payload(
        telegram_id=777888999,
        username="admin_tg",
        auth_date=int(datetime.now(UTC).timestamp()) + 1,
    )
    tg_login_res = await client.post("/api/admin/v1/auth/telegram/login", json=login_payload)
    assert tg_login_res.status_code == 200, tg_login_res.text
    tg_data = tg_login_res.json()
    assert "access_token" in tg_data
    assert "refresh_token" in tg_data
    assert tg_data["user"]["id"] == linked_user["id"]
    assert tg_data["user"]["telegram_id"] == "777888999"


@pytest.mark.asyncio
async def test_telegram_invalid_signature_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    bad_payload = build_signed_telegram_payload(
        telegram_id=777888999,
        tamper_hash="0" * 64,
    )
    res = await client.post("/api/admin/v1/auth/telegram/login", json=bad_payload)
    assert res.status_code == 401
    assert "signature" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_telegram_expired_auth_date_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    expired_ts = int(datetime.now(UTC).timestamp()) - (settings.TELEGRAM_AUTH_MAX_AGE_SECONDS + 120)
    expired_payload = build_signed_telegram_payload(telegram_id=777888999, auth_date=expired_ts)
    res = await client.post("/api/admin/v1/auth/telegram/login", json=expired_payload)
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_telegram_replay_attack_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # Link Telegram identity
    link_payload = build_signed_telegram_payload(telegram_id=555666777, username="admin_replay")
    link_res = await client.post("/api/admin/v1/auth/telegram/link", json=link_payload, headers=headers)
    assert link_res.status_code == 200

    # Reusing the exact same signed payload for login must be rejected as a replay
    replay_res = await client.post("/api/admin/v1/auth/telegram/login", json=link_payload)
    assert replay_res.status_code == 401
    assert "replay" in replay_res.json()["detail"].lower() or "already been used" in replay_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_telegram_identity_conflict(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    manager_tokens = await login_and_get_tokens(client, "manager", "manager_pass_123")

    payload1 = build_signed_telegram_payload(telegram_id=111222333, username="shared_tg", auth_date=int(datetime.now(UTC).timestamp()))
    res1 = await client.post(
        "/api/admin/v1/auth/telegram/link",
        json=payload1,
        headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
    )
    assert res1.status_code == 200

    # Manager attempts to link the same Telegram ID with a fresh valid signature
    payload2 = build_signed_telegram_payload(telegram_id=111222333, username="shared_tg", auth_date=int(datetime.now(UTC).timestamp()) + 2)
    res2 = await client.post(
        "/api/admin/v1/auth/telegram/link",
        json=payload2,
        headers={"Authorization": f"Bearer {manager_tokens['access_token']}"},
    )
    assert res2.status_code == 409
    assert "already linked" in res2.json()["detail"].lower()

    # Verify USER_TELEGRAM_LINK_CONFLICT audit record was logged
    from sqlalchemy import select
    from app.models import AUDIT_LOG_MODEL
    conflict_logs = (
        await db.execute(
            select(AUDIT_LOG_MODEL).where(AUDIT_LOG_MODEL.action == "USER_TELEGRAM_LINK_CONFLICT")
        )
    ).scalars().all()
    assert len(conflict_logs) == 1
    assert conflict_logs[0].new_data["attempted_telegram_id"] == "111222333"


@pytest.mark.asyncio
async def test_telegram_primary_endpoint_status_and_unlink(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # Initially not linked
    status_before = await client.get("/api/v1/auth/telegram/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.json()["is_linked"] is False

    # Link Telegram identity
    link_payload = build_signed_telegram_payload(telegram_id=444555666, username="primary_tg")
    link_res = await client.post("/api/v1/auth/telegram/link", json=link_payload, headers=headers)
    assert link_res.status_code == 200

    # Status now reports linked with metadata
    status_after = await client.get("/api/v1/auth/telegram/status", headers=headers)
    assert status_after.status_code == 200
    st = status_after.json()
    assert st["is_linked"] is True
    assert st["telegram_id"] == "444555666"
    assert st["telegram_username"] == "primary_tg"
    assert st["telegram_linked_at"] is not None

    # Authenticate via primary endpoint POST /api/v1/auth/telegram
    auth_payload = build_signed_telegram_payload(
        telegram_id=444555666,
        username="primary_tg",
        auth_date=int(datetime.now(UTC).timestamp()) + 2,
    )
    auth_res = await client.post("/api/v1/auth/telegram", json=auth_payload)
    assert auth_res.status_code == 200
    assert auth_res.json()["user"]["telegram_id"] == "444555666"

    # Unlink via DELETE /api/v1/auth/telegram/unlink (allowed because user has password)
    unlink_res = await client.delete("/api/v1/auth/telegram/unlink", headers=headers)
    assert unlink_res.status_code == 200
    assert unlink_res.json()["telegram_id"] is None

    # Subsequent Telegram login with unlinked ID fails with 401
    unlinked_login_payload = build_signed_telegram_payload(
        telegram_id=444555666,
        username="primary_tg",
        auth_date=int(datetime.now(UTC).timestamp()) + 3,
    )
    unlinked_res = await client.post("/api/v1/auth/telegram", json=unlinked_login_payload)
    assert unlinked_res.status_code == 401
    assert "no user account" in unlinked_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_telegram_security_edge_cases_and_rate_limiting(client: AsyncClient, db: AsyncSession) -> None:
    seeded = await seed_roles_and_users(db)
    cashier_user = seeded["users"]["cashier"]

    # 1. Modified id after signing -> rejected with 401
    tampered_id_payload = build_signed_telegram_payload(telegram_id=12345)
    tampered_id_payload["id"] = 99999
    res_tampered = await client.post("/api/v1/auth/telegram", json=tampered_id_payload)
    assert res_tampered.status_code == 401

    # 2. Missing hash -> rejected (422 validation error)
    missing_hash = {"id": 12345, "first_name": "Test", "auth_date": int(datetime.now(UTC).timestamp())}
    res_missing = await client.post("/api/v1/auth/telegram", json=missing_hash)
    assert res_missing.status_code == 422

    # 3. Future auth_date -> rejected with 401
    future_ts = int(datetime.now(UTC).timestamp()) + 600
    future_payload = build_signed_telegram_payload(telegram_id=12345, auth_date=future_ts)
    res_future = await client.post("/api/v1/auth/telegram", json=future_payload)
    assert res_future.status_code == 401
    assert "future" in res_future.json()["detail"].lower()

    # 4. Missing bot token configuration -> rejected with 400
    settings.TELEGRAM_BOT_TOKEN = None
    no_cfg_payload = build_signed_telegram_payload(telegram_id=12345)
    res_no_cfg = await client.post("/api/v1/auth/telegram", json=no_cfg_payload)
    assert res_no_cfg.status_code == 400
    settings.TELEGRAM_BOT_TOKEN = TEST_BOT_TOKEN

    # 5. Disabled account cannot link or login via Telegram
    cashier_tokens = await login_and_get_tokens(client, "cashier", "cashier_pass_123")
    cashier_link_payload = build_signed_telegram_payload(telegram_id=888111222, username="cashier_tg")
    link_ok = await client.post(
        "/api/v1/auth/telegram/link",
        json=cashier_link_payload,
        headers={"Authorization": f"Bearer {cashier_tokens['access_token']}"},
    )
    assert link_ok.status_code == 200

    cashier_user.status = "INACTIVE"
    await db.commit()

    disabled_login_payload = build_signed_telegram_payload(
        telegram_id=888111222,
        username="cashier_tg",
        auth_date=int(datetime.now(UTC).timestamp()) + 2,
    )
    res_disabled = await client.post("/api/v1/auth/telegram", json=disabled_login_payload)
    assert res_disabled.status_code == 403

    # 6. Rate limiting triggers 429 on excessive Telegram auth requests
    AUTH_SERVICE.reset_rate_limits()
    got_429 = False
    for i in range(25):
        p = build_signed_telegram_payload(telegram_id=900000 + i, auth_date=int(datetime.now(UTC).timestamp()))
        r = await client.post("/api/v1/auth/telegram", json=p)
        if r.status_code == 429:
            got_429 = True
            break
    assert got_429 is True
    AUTH_SERVICE.reset_rate_limits()


# ── 3. Verified Phone Linking Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_phone_verification_flow_and_conflicts(client: AsyncClient, db: AsyncSession) -> None:
    seeded = await seed_roles_and_users(db)
    manager_user = seeded["users"]["manager"]
    manager_tokens = await login_and_get_tokens(client, "manager", "manager_pass_123")
    headers = {"Authorization": f"Bearer {manager_tokens['access_token']}"}

    # 1. Attempting to claim admin's existing phone (+855069382165 / +85569382165) must fail with 409
    conflict_res = await client.post(
        "/api/admin/v1/auth/phone/request-verification",
        json={"phone_number": "069382165"},
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # 2. Request verification for a new phone number in local format
    req_res = await client.post(
        "/api/admin/v1/auth/phone/request-verification",
        json={"phone_number": "+855012999888"},
        headers=headers,
    )
    assert req_res.status_code == 200, req_res.text
    challenge_info = req_res.json()
    assert challenge_info["normalized_phone"] == "+85512999888"

    # 3. Invalid OTP code is rejected with 400
    bad_verify = await client.post(
        "/api/admin/v1/auth/phone/verify",
        json={"phone_number": "+85512999888", "otp_code": "000000"},
        headers=headers,
    )
    assert bad_verify.status_code == 400

    # 4. Valid OTP verification succeeds and preserves MANAGER role
    # Set a known OTP hash on the pending challenge for deterministic verification in test
    from sqlalchemy import select
    from app.models import PHONE_VERIFICATION_MODEL
    stmt = (
        select(PHONE_VERIFICATION_MODEL)
        .where(PHONE_VERIFICATION_MODEL.user_id == manager_user.id, PHONE_VERIFICATION_MODEL.status_code == "PENDING")
    )
    challenge_row = (await db.execute(stmt)).scalar_one()
    challenge_row.otp_hash = AUTH_SERVICE._hash_phone_otp(manager_user.id, "+85512999888", "654321")
    await db.commit()

    ok_verify = await client.post(
        "/api/admin/v1/auth/phone/verify",
        json={"phone_number": "012999888", "otp_code": "654321"},
        headers=headers,
    )
    assert ok_verify.status_code == 200, ok_verify.text
    verified_user = ok_verify.json()
    assert verified_user["phone_number"] == "+85512999888"
    assert verified_user["phone_verified"] is True
    assert [r["name"] for r in verified_user["roles"]] == ["MANAGER"]


# ── 4. Admin Role Management & Security Tests ─────────────────────────────────

@pytest.mark.asyncio
async def test_role_assignment_multi_role_revocation_and_history(client: AsyncClient, db: AsyncSession) -> None:
    seeded = await seed_roles_and_users(db)
    roles = seeded["roles"]
    cashier_user = seeded["users"]["cashier"]

    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # 1. Assign multiple roles (CASHIER + WAREHOUSE + MANAGER) to cashier user
    multi_role_ids = [str(roles["CASHIER"].id), str(roles["WAREHOUSE"].id), str(roles["MANAGER"].id)]
    patch_res = await client.patch(
        f"/api/admin/v1/users/{cashier_user.id}",
        json={"role_ids": multi_role_ids},
        headers=admin_headers,
    )
    assert patch_res.status_code == 200, patch_res.text
    updated_roles = {r["name"] for r in patch_res.json()["roles"]}
    assert updated_roles == {"CASHIER", "WAREHOUSE", "MANAGER"}

    # 2. Revoke MANAGER role (leaving CASHIER + WAREHOUSE)
    revoke_res = await client.patch(
        f"/api/admin/v1/users/{cashier_user.id}",
        json={"role_ids": [str(roles["CASHIER"].id), str(roles["WAREHOUSE"].id)]},
        headers=admin_headers,
    )
    assert revoke_res.status_code == 200
    assert {r["name"] for r in revoke_res.json()["roles"]} == {"CASHIER", "WAREHOUSE"}

    # 3. Verify role-change history endpoint records USER_ROLES_UPDATED
    hist_res = await client.get(
        f"/api/admin/v1/users/{cashier_user.id}/role-history",
        headers=admin_headers,
    )
    assert hist_res.status_code == 200
    history = hist_res.json()
    role_events = [h for h in history if h["action"] == "USER_ROLES_UPDATED"]
    assert len(role_events) >= 2
    assert "MANAGER" in role_events[0]["new_data"]["revoked_roles"]


@pytest.mark.asyncio
async def test_self_role_modification_and_unauthorized_admin_requests_blocked(client: AsyncClient, db: AsyncSession) -> None:
    seeded = await seed_roles_and_users(db)
    roles = seeded["roles"]
    admin_user = seeded["users"]["admin"]

    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # 1. Admin cannot modify their own role assignments (neither revoking ADMIN nor adding extra roles)
    self_role_res = await client.patch(
        f"/api/admin/v1/users/{admin_user.id}",
        json={"role_ids": [str(roles["MANAGER"].id)]},
        headers=admin_headers,
    )
    assert self_role_res.status_code == 400
    assert "cannot modify their own role" in self_role_res.json()["detail"].lower()

    # 2. Admin cannot deactivate their own account
    self_deact_res = await client.delete(
        f"/api/admin/v1/users/{admin_user.id}",
        headers=admin_headers,
    )
    assert self_deact_res.status_code == 400

    # 3. Manager (without user.manage) cannot list or modify users
    manager_tokens = await login_and_get_tokens(client, "manager", "manager_pass_123")
    manager_headers = {"Authorization": f"Bearer {manager_tokens['access_token']}"}
    unauth_res = await client.get("/api/admin/v1/users", headers=manager_headers)
    assert unauth_res.status_code == 403


@pytest.mark.asyncio
async def test_session_refresh_invalidated_after_role_change_or_deactivation(client: AsyncClient, db: AsyncSession) -> None:
    seeded = await seed_roles_and_users(db)
    roles = seeded["roles"]
    manager_user = seeded["users"]["manager"]

    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    manager_tokens = await login_and_get_tokens(client, "manager", "manager_pass_123")
    manager_refresh = manager_tokens["refresh_token"]

    # Admin changes manager's roles -> manager's existing refresh token must be revoked
    patch_res = await client.patch(
        f"/api/admin/v1/users/{manager_user.id}",
        json={"role_ids": [str(roles["MANAGER"].id), str(roles["CASHIER"].id)]},
        headers=admin_headers,
    )
    assert patch_res.status_code == 200

    refresh_res = await client.post(
        "/api/admin/v1/auth/refresh",
        json={"refresh_token": manager_refresh},
    )
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_user_search_by_phone_name_and_lane_authorization(client: AsyncClient, db: AsyncSession) -> None:
    await seed_roles_and_users(db)
    admin_tokens = await login_and_get_tokens(client, "admin", "admin_pass_123")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}

    # Search by unnormalized phone +855069382165 finds the admin user with normalized +85569382165
    search_res = await client.get(
        "/api/admin/v1/users",
        params={"search": "+855069382165"},
        headers=admin_headers,
    )
    assert search_res.status_code == 200
    matched = search_res.json()
    assert len(matched) == 1
    assert matched[0]["username"] == "admin"
    assert matched[0]["phone_number"] == "+85569382165"

    # Lane authorization checks:
    # Cashier can access cashier lane (/api/cashier/v1/auth/me) but is blocked from admin lane (/api/admin/v1/products)
    cashier_login = await client.post(
        "/api/cashier/v1/auth/login",
        json={"username": "cashier", "password": "cashier_pass_123"},
    )
    assert cashier_login.status_code == 200
    cashier_headers = {"Authorization": f"Bearer {cashier_login.json()['access_token']}"}

    cashier_me = await client.get("/api/cashier/v1/auth/me", headers=cashier_headers)
    assert cashier_me.status_code == 200

    cashier_admin_lane = await client.get("/api/admin/v1/products", headers=cashier_headers)
    assert cashier_admin_lane.status_code == 403

    # Warehouse can access admin lane inventory (/api/admin/v1/inventory/stocks) but not cashier lane (/api/cashier/v1/sales)
    warehouse_login = await client.post(
        "/api/admin/v1/auth/login",
        json={"username": "warehouse", "password": "warehouse_pass_123"},
    )
    assert warehouse_login.status_code == 200
    warehouse_headers = {"Authorization": f"Bearer {warehouse_login.json()['access_token']}"}

    warehouse_inv = await client.get("/api/admin/v1/inventory/stocks", headers=warehouse_headers)
    assert warehouse_inv.status_code == 200

    warehouse_cashier_lane = await client.get("/api/cashier/v1/sales", headers=warehouse_headers)
    assert warehouse_cashier_lane.status_code == 403

