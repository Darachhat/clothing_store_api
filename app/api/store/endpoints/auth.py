"""Store lane customer auth endpoints — /api/store/v1/auth/

Handles customer registration, login, token refresh, and logout.
Customers are stored in the shared users table with the CUSTOMER role.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.store.auth import require_customer
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Store Auth"])


class CustomerRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_customer(
    body: CustomerRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Register a new customer account."""
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository
    from sqlalchemy import select
    from app.models.user import User, Role

    repo = UserRepository(db)

    # Check username/email uniqueness
    existing = await repo.get_by_username(body.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken.")

    # Get or create CUSTOMER role
    result = await db.execute(select(Role).where(Role.name == "CUSTOMER"))
    customer_role = result.scalar_one_or_none()
    if not customer_role:
        customer_role = Role(name="CUSTOMER", description="Web store customer", is_system=True)
        db.add(customer_role)
        await db.flush()

    new_user = User(
        username=body.username,
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        status="ACTIVE",
    )
    new_user.roles = [customer_role]
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"message": "Account created successfully.", "user_id": str(new_user.id)}


@router.post("/login", response_model=LoginResponse)
async def customer_login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Customer login — returns JWT access + refresh tokens."""
    service = AuthService(db)
    result = await service.login(body.username, body.password, request)
    # Verify the logged-in user is actually a customer
    from app.repositories.user_repository import UserRepository
    from uuid import UUID
    from app.core.security import verify_access_token
    payload = verify_access_token(result["access_token"])
    if payload:
        repo = UserRepository(db)
        user = await repo.get_by_id(UUID(payload["sub"]))
        if user:
            role_names = {r.name for r in user.roles}
            if "CUSTOMER" not in role_names:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This endpoint is for customer accounts only.",
                )
    return LoginResponse(**result)


@router.post("/refresh", response_model=TokenResponse)
async def customer_refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    service = AuthService(db)
    result = await service.refresh(body.refresh_token)
    return TokenResponse(**result)


@router.get("/me")
async def customer_me(
    current_customer: Annotated[User, Depends(require_customer)],
) -> dict:
    return {
        "id": str(current_customer.id),
        "username": current_customer.username,
        "email": current_customer.email,
        "full_name": current_customer.full_name,
        "status": current_customer.status,
    }
