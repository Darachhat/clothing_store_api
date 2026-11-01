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
from app.models import User
from app.schemas.auth_schema import LOGIN_REQUEST_SCHEMA, LOGIN_RESPONSE_SCHEMA, REFRESH_REQUEST_SCHEMA, TOKEN_RESPONSE_SCHEMA
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Store Auth"])


class CustomerRegisterRequest(BaseModel):
    username: str | None = None
    email: EmailStr
    full_name: str
    password: str
    phone: str | None = None


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_customer(
    body: CustomerRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Register a new customer account."""
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository
    from sqlalchemy import select
    from app.models import User, Role

    repo = UserRepository(db)

    normalized_email = body.email.lower().strip()
    resolved_username = (body.username or normalized_email).strip()

    # Check username/email uniqueness
    existing = await repo.get_by_username(resolved_username)
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already taken.")

    if await repo.email_exists(normalized_email):
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Get or create CUSTOMER role
    result = await db.execute(select(Role).where(Role.name == "CUSTOMER"))
    customer_role = result.scalar_one_or_none()
    if not customer_role:
        customer_role = Role(name="CUSTOMER", description="Web store customer", is_system=True)
        db.add(customer_role)
        await db.flush()

    new_user = User(
        username=resolved_username,
        email=normalized_email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        status="ACTIVE",
    )
    new_user.roles = [customer_role]
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {"message": "Account created successfully.", "user_id": str(new_user.id)}


@router.post("/login", response_model=LOGIN_RESPONSE_SCHEMA)
async def customer_login(
    body: LOGIN_REQUEST_SCHEMA,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LOGIN_RESPONSE_SCHEMA:
    """Customer login — returns JWT access + refresh tokens."""
    from app.repositories.user_repository import UserRepository

    repo = UserRepository(db)
    pre_user = await repo.get_by_username(body.username)
    if pre_user:
        role_names = {r.name for r in pre_user.roles}
        if "CUSTOMER" not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is for customer accounts only.",
            )

    service = AuthService(db)
    result = await service.login(body.username, body.password, request)
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.post("/refresh", response_model=TOKEN_RESPONSE_SCHEMA)
async def customer_refresh(
    body: REFRESH_REQUEST_SCHEMA,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TOKEN_RESPONSE_SCHEMA:
    service = AuthService(db)
    result = await service.refresh(body.refresh_token)
    return TOKEN_RESPONSE_SCHEMA(**result)


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
