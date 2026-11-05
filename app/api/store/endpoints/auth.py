"""Store lane customer auth endpoints — /api/store/v1/auth/

Handles customer registration, login, Telegram authentication, phone verification,
token refresh, and logout. Customers are stored in the shared users table with the CUSTOMER role.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.store.auth import require_customer
from app.api.v1.handlers.auth_handler import clear_session_cookies, set_session_cookies
from app.core.database import get_db
from app.core.security import hash_password
from app.models import Role, User
from app.repositories.user_repository import UserRepository
from app.schemas.auth_schema import (
    LOGIN_REQUEST_SCHEMA,
    LOGIN_RESPONSE_SCHEMA,
    LOGOUT_REQUEST_SCHEMA,
    PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA,
    PHONE_VERIFICATION_REQUEST_SCHEMA,
    PHONE_VERIFY_CONFIRM_SCHEMA,
    REFRESH_REQUEST_SCHEMA,
    TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    TELEGRAM_CONFIG_RESPONSE_SCHEMA,
    TELEGRAM_STATUS_RESPONSE_SCHEMA,
    TOKEN_RESPONSE_SCHEMA,
    USER_RESPONSE_SCHEMA,
)
from app.services.auth_service import AUTH_SERVICE

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
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LOGIN_RESPONSE_SCHEMA:
    """Customer login — returns JWT access + refresh tokens."""
    repo = UserRepository(db)
    pre_user = await repo.get_by_username(body.username.strip())
    if not pre_user and "@" in body.username:
        pre_user = await repo.get_by_email(body.username.strip().lower())
    if pre_user:
        role_names = {r.name for r in pre_user.roles}
        if "CUSTOMER" not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is for customer accounts only.",
            )

    service = AUTH_SERVICE(db)
    result = await service.login(body.username, body.password, request)
    user_roles = {r.name for r in (result["user"].roles or [])}
    if "CUSTOMER" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for customer accounts only.",
        )
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.get("/telegram/config", response_model=TELEGRAM_CONFIG_RESPONSE_SCHEMA)
async def customer_telegram_config(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TELEGRAM_CONFIG_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    cfg = await service.get_telegram_config()
    return TELEGRAM_CONFIG_RESPONSE_SCHEMA(**cfg)


@router.get("/telegram/status", response_model=TELEGRAM_STATUS_RESPONSE_SCHEMA)
async def customer_telegram_status(
    current_customer: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TELEGRAM_STATUS_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    st = await service.get_telegram_status(current_customer)
    return TELEGRAM_STATUS_RESPONSE_SCHEMA(**st)


@router.post("/telegram", response_model=LOGIN_RESPONSE_SCHEMA)
@router.post("/telegram/login", response_model=LOGIN_RESPONSE_SCHEMA)
async def customer_telegram_login(
    body: TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LOGIN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.login_with_telegram(
        body.model_dump(exclude_none=True),
        request=request,
        required_role="CUSTOMER",
        auto_create_customer=True,
    )
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.post("/telegram/link", response_model=USER_RESPONSE_SCHEMA)
async def customer_link_telegram(
    body: TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    request: Request,
    current_customer: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.link_telegram_identity(current_customer, body.model_dump(exclude_none=True), request=request)


@router.delete("/telegram/unlink", response_model=USER_RESPONSE_SCHEMA)
@router.delete("/telegram/link", response_model=USER_RESPONSE_SCHEMA)
async def customer_unlink_telegram(
    request: Request,
    current_customer: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.unlink_telegram_identity(current_customer, request=request)


@router.post(
    "/phone/request-verification",
    response_model=PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA,
)
async def customer_request_phone_verification(
    body: PHONE_VERIFICATION_REQUEST_SCHEMA,
    request: Request,
    current_customer: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.request_phone_verification(current_customer, body.phone_number, request=request)
    return PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA(**result)


@router.post("/phone/verify", response_model=USER_RESPONSE_SCHEMA)
async def customer_verify_phone(
    body: PHONE_VERIFY_CONFIRM_SCHEMA,
    request: Request,
    current_customer: Annotated[User, Depends(require_customer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.verify_and_link_phone(
        current_customer,
        body.phone_number,
        body.otp_code,
        request=request,
    )


@router.post("/refresh", response_model=TOKEN_RESPONSE_SCHEMA)
async def customer_refresh(
    body: REFRESH_REQUEST_SCHEMA,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TOKEN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.refresh(body.refresh_token)
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return TOKEN_RESPONSE_SCHEMA(**result)


@router.post("/logout")
async def customer_logout(
    body: LOGOUT_REQUEST_SCHEMA,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    service = AUTH_SERVICE(db)
    await service.logout(body.refresh_token)
    clear_session_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=USER_RESPONSE_SCHEMA)
async def customer_me(
    current_customer: Annotated[User, Depends(require_customer)],
) -> User:
    return current_customer
