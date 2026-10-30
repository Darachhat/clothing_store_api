"""User and Role Administration unit tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.user import Permission, Role, User


async def create_admin_user(db: AsyncSession) -> User:
    perm = Permission(code="user.manage", name="Manage Users", module="users")
    db.add(perm)
    await db.flush()

    role = Role(name="ADMIN", is_system=True, permissions=[perm])
    db.add(role)
    await db.flush()

    admin = User(
        username="superadmin",
        email="admin@test.com",
        full_name="Super Administrator",
        hashed_password=hash_password("admin_pass_123"),
        status="ACTIVE",
        roles=[role],
    )
    db.add(admin)
    await db.flush()
    return admin


@pytest.mark.asyncio
async def test_user_and_role_management(client: AsyncClient, db: AsyncSession):
    admin = await create_admin_user(db)
    token = create_access_token(admin.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List roles
    res = await client.get("/api/v1/roles", headers=headers)
    assert res.status_code == 200
    roles = res.json()
    assert any(r["name"] == "ADMIN" for r in roles)

    # 2. List permissions
    res_perms = await client.get("/api/v1/roles/permissions", headers=headers)
    assert res_perms.status_code == 200
    perms = res_perms.json()
    assert any(p["code"] == "user.manage" for p in perms)

    # 3. Create a new user
    user_payload = {
        "username": "cashier_jill",
        "email": "jill@test.com",
        "full_name": "Jill Cashier",
        "password": "Password123!",
        "role_ids": [roles[0]["id"]],
    }
    create_res = await client.post("/api/v1/users", json=user_payload, headers=headers)
    assert create_res.status_code == 201
    created_user = create_res.json()
    assert created_user["username"] == "cashier_jill"
    assert created_user["status"] == "ACTIVE"

    # 4. List users
    list_res = await client.get("/api/v1/users", headers=headers)
    assert list_res.status_code == 200
    users = list_res.json()
    assert len(users) >= 2

    # 5. Update user
    update_res = await client.patch(
        f"/api/v1/users/{created_user['id']}",
        json={"full_name": "Jill Updated"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == "Jill Updated"

    # 6. Deactivate user
    deact_res = await client.delete(f"/api/v1/users/{created_user['id']}", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["status"] == "INACTIVE"
