from typing import Annotated, List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.deps.database import get_db as get_sync_db
from app.core.database import get_db as get_async_db
from app.core.deps import get_current_active_user, require_system_admin
from app.models import User
from app.schemas.auth_schema import (
    CHANGE_PASSWORD_REQUEST_SCHEMA
    , LOGIN_REQUEST_SCHEMA
    , LOGIN_RESPONSE_SCHEMA
    , LOGOUT_REQUEST_SCHEMA
    , REFRESH_REQUEST_SCHEMA
    , TOKEN_RESPONSE_SCHEMA
    , USER_RESPONSE_SCHEMA
)
from app.schemas.auth_schema import (
    API_KEY_CREATED_SCHEMA
    , SYSTEM_CLIENT_CREATE_SCHEMA
    , SYSTEM_CLIENT_RESPONSE_SCHEMA
)
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.services.auth_service import AUTH_SERVICE

router = APIRouter(prefix="/auth", tags=["Authentication & System Client Auth"])


# ── System Client API Key Authentication (Template) ──────────────────────────

@router.post(
    "/clients"
    , response_model = RESPONSE_ENVELOPE[API_KEY_CREATED_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
    , dependencies   = [Depends(require_system_admin)]
)
def register_system_client(
    body : SYSTEM_CLIENT_CREATE_SCHEMA
    , db : Session = Depends(get_sync_db)
):
    client, raw_key = AUTH_SERVICE.create_system_client(db=db, data=body)
    return RESPONSE_ENVELOPE.created(
        data      = API_KEY_CREATED_SCHEMA(code=client.code, raw_api_key=raw_key)
        , message = "System client registered successfully."
    )


@router.get(
    "/clients"
    , response_model = RESPONSE_ENVELOPE[List[SYSTEM_CLIENT_RESPONSE_SCHEMA]]
    , dependencies   = [Depends(require_system_admin)]
)
def list_system_clients(db: Session = Depends(get_sync_db)):
    clients = AUTH_SERVICE.list_system_clients(db=db)
    return RESPONSE_ENVELOPE.success(
        data      = clients
        , message = "System clients retrieved successfully."
    )


@router.put(
    "/clients/{code}/revoke"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_CLIENT_RESPONSE_SCHEMA]
    , dependencies   = [Depends(require_system_admin)]
)
def revoke_system_client(
    code : str
    , db : Session = Depends(get_sync_db)
):
    client = AUTH_SERVICE.revoke_system_client(db=db, code=code)
    return RESPONSE_ENVELOPE.success(
        data      = client
        , message = "System client revoked successfully."
    )


# ── User JWT Authentication (Store / Admin / Cashier) ────────────────────────

@router.post("/login", response_model=LOGIN_RESPONSE_SCHEMA)
async def login(
    body      : LOGIN_REQUEST_SCHEMA
    , request : Request
    , db      : Annotated[AsyncSession, Depends(get_async_db)]
) -> LOGIN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result  = await service.login(body.username, body.password, request)
    return LOGIN_RESPONSE_SCHEMA(**result)


@router.post("/refresh", response_model=TOKEN_RESPONSE_SCHEMA)
async def refresh(
    body : REFRESH_REQUEST_SCHEMA
    , db : Annotated[AsyncSession, Depends(get_async_db)]
) -> TOKEN_RESPONSE_SCHEMA:
    service = AUTH_SERVICE(db)
    result  = await service.refresh(body.refresh_token)
    return TOKEN_RESPONSE_SCHEMA(**result)


@router.post("/logout")
async def logout(
    body : LOGOUT_REQUEST_SCHEMA
    , db : Annotated[AsyncSession, Depends(get_async_db)]
) -> dict:
    service = AUTH_SERVICE(db)
    await service.logout(body.refresh_token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=USER_RESPONSE_SCHEMA)
async def get_me(
    current_user : Annotated[User, Depends(get_current_active_user)]
) -> User:
    return current_user


@router.post("/change-password")
async def change_password(
    body           : CHANGE_PASSWORD_REQUEST_SCHEMA
    , current_user : Annotated[User, Depends(get_current_active_user)]
    , db           : Annotated[AsyncSession, Depends(get_async_db)]
) -> dict:
    service = AUTH_SERVICE(db)
    await service.change_password(current_user, body.current_password, body.new_password)
    return {"message": "Password changed successfully"}

