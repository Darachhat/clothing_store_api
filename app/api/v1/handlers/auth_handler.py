from typing import Annotated, List
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.deps.database import get_db as get_sync_db
from app.core.config import settings
from app.core.database import get_db as get_async_db
from app.core.deps import get_current_active_user, require_system_admin
from app.models import User
from app.schemas.auth_schema import (
    API_KEY_CREATED_SCHEMA,
    CHANGE_PASSWORD_REQUEST_SCHEMA,
    LOGIN_REQUEST_SCHEMA,
    LOGIN_RESPONSE_SCHEMA,
    LOGOUT_REQUEST_SCHEMA,
    PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA,
    PHONE_VERIFICATION_REQUEST_SCHEMA,
    PHONE_VERIFY_CONFIRM_SCHEMA,
    REFRESH_REQUEST_SCHEMA,
    SYSTEM_CLIENT_CREATE_SCHEMA,
    SYSTEM_CLIENT_RESPONSE_SCHEMA,
    TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA,
    TELEGRAM_APP_STATUS_RESPONSE_SCHEMA,
    TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    TELEGRAM_CONFIG_RESPONSE_SCHEMA,
    TELEGRAM_STATUS_RESPONSE_SCHEMA,
    TOKEN_RESPONSE_SCHEMA,
    USER_RESPONSE_SCHEMA,
)
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.services.auth_service import AUTH_SERVICE

router = APIRouter(prefix="/auth", tags=["Authentication & System Client Auth"])


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    is_secure = settings.ENV.lower() == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


# ── System Client API Key Authentication (Template) ──────────────────────────

@router.post(
    "/clients",
    response_model=RESPONSE_ENVELOPE[API_KEY_CREATED_SCHEMA],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_system_admin)],
)
def register_system_client(
    body: SYSTEM_CLIENT_CREATE_SCHEMA,
    db: Session = Depends(get_sync_db),
):
    client, raw_key = AUTH_SERVICE.create_system_client(db=db, data=body)
    return RESPONSE_ENVELOPE.created(
        data=API_KEY_CREATED_SCHEMA(code=client.code, raw_api_key=raw_key),
        message="System client registered successfully.",
    )


@router.get(
    "/clients",
    response_model=RESPONSE_ENVELOPE[List[SYSTEM_CLIENT_RESPONSE_SCHEMA]],
    dependencies=[Depends(require_system_admin)],
)
def list_system_clients(db: Session = Depends(get_sync_db)):
    clients = AUTH_SERVICE.list_system_clients(db=db)
    return RESPONSE_ENVELOPE.success(
        data=clients,
        message="System clients retrieved successfully.",
    )


@router.put(
    "/clients/{code}/revoke",
    response_model=RESPONSE_ENVELOPE[SYSTEM_CLIENT_RESPONSE_SCHEMA],
    dependencies=[Depends(require_system_admin)],
)
def revoke_system_client(
    code: str,
    db: Session = Depends(get_sync_db),
):
    client = AUTH_SERVICE.revoke_system_client(db=db, code=code)
    return RESPONSE_ENVELOPE.success(
        data=client,
        message="System client revoked successfully.",
    )


# ── User JWT Authentication (Store / Admin / Cashier) ────────────────────────

@router.post("/login", response_model=LOGIN_RESPONSE_SCHEMA)
async def login(
    body: LOGIN_REQUEST_SCHEMA,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> LOGIN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.login(body.username, body.password, request)
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.get("/telegram/config", response_model=TELEGRAM_CONFIG_RESPONSE_SCHEMA)
async def get_telegram_auth_config(
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TELEGRAM_CONFIG_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    cfg = await service.get_telegram_config()
    return TELEGRAM_CONFIG_RESPONSE_SCHEMA(**cfg)


@router.get("/telegram/status", response_model=TELEGRAM_STATUS_RESPONSE_SCHEMA)
async def get_telegram_auth_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TELEGRAM_STATUS_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    st = await service.get_telegram_status(current_user)
    return TELEGRAM_STATUS_RESPONSE_SCHEMA(**st)


@router.post("/telegram", response_model=LOGIN_RESPONSE_SCHEMA)
@router.post("/telegram/login", response_model=LOGIN_RESPONSE_SCHEMA)
async def login_with_telegram(
    body: TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> LOGIN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.login_with_telegram(body.model_dump(exclude_none=True), request=request)
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.post("/telegram/app-challenge", response_model=TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA)
async def create_telegram_app_challenge(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    res = await service.create_telegram_app_challenge(mode="login", request=request)
    return TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA(**res)


@router.post("/telegram/app-link-challenge", response_model=TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA)
async def create_telegram_app_link_challenge(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    res = await service.create_telegram_app_challenge(mode="link", current_user=current_user, request=request)
    return TELEGRAM_APP_CHALLENGE_RESPONSE_SCHEMA(**res)


@router.get("/telegram/app-status/{challenge_token}", response_model=TELEGRAM_APP_STATUS_RESPONSE_SCHEMA)
async def get_telegram_app_challenge_status(
    challenge_token: str,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TELEGRAM_APP_STATUS_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    res = await service.check_telegram_app_challenge(challenge_token, request=request)
    if res.get("status") == "APPROVED" and res.get("access_token") and res.get("refresh_token"):
        set_session_cookies(response, res["access_token"], res["refresh_token"])
    return TELEGRAM_APP_STATUS_RESPONSE_SCHEMA(**res)


@router.post("/telegram/link", response_model=USER_RESPONSE_SCHEMA)
async def link_telegram_account(
    body: TELEGRAM_AUTH_PAYLOAD_SCHEMA,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.link_telegram_identity(current_user, body.model_dump(exclude_none=True), request=request)


@router.delete("/telegram/unlink", response_model=USER_RESPONSE_SCHEMA)
@router.delete("/telegram/link", response_model=USER_RESPONSE_SCHEMA)
async def unlink_telegram_account(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.unlink_telegram_identity(current_user, request=request)


@router.post(
    "/phone/request-verification",
    response_model=PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA,
)
async def request_phone_verification(
    body: PHONE_VERIFICATION_REQUEST_SCHEMA,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.request_phone_verification(current_user, body.phone_number, request=request)
    return PHONE_VERIFICATION_CHALLENGE_RESPONSE_SCHEMA(**result)


@router.post("/phone/verify", response_model=USER_RESPONSE_SCHEMA)
async def verify_and_link_phone(
    body: PHONE_VERIFY_CONFIRM_SCHEMA,
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> User:
    service = AUTH_SERVICE(db)
    return await service.verify_and_link_phone(
        current_user,
        body.phone_number,
        body.otp_code,
        request=request,
    )


@router.post("/refresh", response_model=TOKEN_RESPONSE_SCHEMA)
async def refresh(
    body: REFRESH_REQUEST_SCHEMA,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> TOKEN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result = await service.refresh(body.refresh_token)
    set_session_cookies(response, result["access_token"], result["refresh_token"])
    return TOKEN_RESPONSE_SCHEMA(**result)


@router.post("/logout")
async def logout(
    body: LOGOUT_REQUEST_SCHEMA,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict:
    service = AUTH_SERVICE(db)
    await service.logout(body.refresh_token)
    clear_session_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=USER_RESPONSE_SCHEMA)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user


@router.post("/change-password")
async def change_password(
    body: CHANGE_PASSWORD_REQUEST_SCHEMA,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> dict:
    service = AUTH_SERVICE(db)
    await service.change_password(current_user, body.current_password, body.new_password)
    return {"message": "Password changed successfully"}
