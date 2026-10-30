"""Tests for authentication endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.branch import Branch, Warehouse
from app.models.user import Role, User


async def create_test_user(db: AsyncSession) -> User:
    branch = Branch(code="TEST", name="Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Test Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    role = Role(name="ADMIN", is_system=True)
    db.add(role)
    await db.flush()

    user = User(
        username="testadmin",
        email="test@example.com",
        full_name="Test Admin",
        hashed_password=hash_password("test_password123"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "test_password123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testadmin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "wrong_password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient, db: AsyncSession) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "ghost", "password": "password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "test_password123"},
    )
    token = login_res.json()["access_token"]

    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "testadmin"


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient, db: AsyncSession) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "test_password123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, db: AsyncSession) -> None:
    await create_test_user(db)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "testadmin", "password": "test_password123"},
    )
    refresh_token = login_res.json()["refresh_token"]

    logout_res = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # After logout, refresh should fail
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401
