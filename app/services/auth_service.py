"""Authentication service: user JWT auth (login, logout, refresh, change password) & system client API key auth."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enum.common_enum import (
    COMMON_STATUS_ENUM
    , STATUS_CODE_ENUM
)
from app.core.exceptions import (
    BAD_REQUEST_EXCEPTION
    , FORBIDDEN_EXCEPTION
    , NOT_FOUND_EXCEPTION
    , UNAUTHORIZED_EXCEPTION
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token
    , create_refresh_token
    , hash_password
    , verify_password
)
from app.core.utils.crypto_utils import generate_api_key, hash_api_key
from app.models import RefreshToken, User
from app.models import SYSTEM_CLIENT_MODEL
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.auth_schema import (
    CHANGE_PASSWORD_REQUEST_SCHEMA
    , LOGIN_REQUEST_SCHEMA
    , LOGOUT_REQUEST_SCHEMA
    , REFRESH_REQUEST_SCHEMA
    , SYSTEM_CLIENT_CREATE_SCHEMA
    , SYSTEM_CLIENT_RESPONSE_SCHEMA
)

logger = get_logger(__name__)


class AUTH_SERVICE:
    """Service orchestrating User RBAC JWT credential issuance and System Client API keys."""

    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self.user_repo  = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    # ── User JWT Authentication (Clothing Store RBAC) ─────────────────────────

    async def login(
        self
        , username : str
        , password : str
        , request  : Optional[Request] = None
    ) -> Dict[str, Any]:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise UNAUTHORIZED_EXCEPTION("Invalid username or password")

        if user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise FORBIDDEN_EXCEPTION("Account is not active")

        user.last_login_at = datetime.now(UTC)

        access_token  = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))
        token_hash    = hashlib.sha256(refresh_token.encode()).hexdigest()

        rt = RefreshToken(
            user_id      = user.id
            , token_hash = token_hash
            , expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            , ip_address = request.client.host if request and request.client else None
            , user_agent = request.headers.get("user-agent") if request else None
        )
        self.db.add(rt)
        await self.db.commit()
        await self.db.refresh(user)

        return {
            "access_token"    : access_token
            , "refresh_token" : refresh_token
            , "token_type"    : "bearer"
            , "user"          : user
        }

    async def refresh(self, refresh_token: str) -> Dict[str, Any]:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stored     = await self.token_repo.get_by_hash(token_hash)

        if not stored or stored.revoked:
            raise UNAUTHORIZED_EXCEPTION("Invalid or revoked refresh token")
        if stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise UNAUTHORIZED_EXCEPTION("Refresh token expired")

        stored.revoked = True

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or user.status != COMMON_STATUS_ENUM.ACTIVE.value:
            raise UNAUTHORIZED_EXCEPTION("User not found")

        new_access  = create_access_token(str(user.id))
        new_refresh = create_refresh_token(str(user.id))
        new_hash    = hashlib.sha256(new_refresh.encode()).hexdigest()

        new_rt = RefreshToken(
            user_id      = user.id
            , token_hash = new_hash
            , expires_at = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(new_rt)
        await self.db.commit()

        return {
            "access_token"    : new_access
            , "refresh_token" : new_refresh
            , "token_type"    : "bearer"
        }

    async def logout(self, refresh_token: str) -> None:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stored     = await self.token_repo.get_by_hash(token_hash)
        if stored:
            stored.revoked = True
            await self.db.commit()

    async def change_password(
        self
        , user             : User
        , current_password : str
        , new_password     : str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise BAD_REQUEST_EXCEPTION("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        await self.db.commit()

    async def login_payload(
        self
        , payload : LOGIN_REQUEST_SCHEMA
        , request : Optional[Request] = None
    ) -> Dict[str, Any]:
        """Authenticate user using structured LOGIN_REQUEST_SCHEMA."""
        return await self.login(
            username = payload.username
            , password = payload.password
            , request  = request
        )

    async def refresh_payload(
        self
        , payload : REFRESH_REQUEST_SCHEMA
    ) -> Dict[str, Any]:
        """Refresh JWT tokens using structured REFRESH_REQUEST_SCHEMA."""
        return await self.refresh(refresh_token=payload.refresh_token)

    async def logout_payload(
        self
        , payload : LOGOUT_REQUEST_SCHEMA
    ) -> None:
        """Revoke refresh token using structured LOGOUT_REQUEST_SCHEMA."""
        await self.logout(refresh_token=payload.refresh_token)

    async def change_password_payload(
        self
        , user    : User
        , payload : CHANGE_PASSWORD_REQUEST_SCHEMA
    ) -> None:
        """Update user password using structured CHANGE_PASSWORD_REQUEST_SCHEMA."""
        await self.change_password(
            user             = user
            , current_password = payload.current_password
            , new_password     = payload.new_password
        )


    # ── System Client API Key Authentication (Enterprise Template) ────────────

    @staticmethod
    def create_system_client(
        db     : Session
        , data : SYSTEM_CLIENT_CREATE_SCHEMA
    ) -> Tuple[SYSTEM_CLIENT_MODEL, str]:
        existing = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == data.code
                , SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if existing:
            raise BAD_REQUEST_EXCEPTION(f"System client code '{data.code}' is already registered.")

        raw_api_key  = generate_api_key()
        api_key_hash = hash_api_key(raw_api_key)

        client = SYSTEM_CLIENT_MODEL(
            code           = data.code
            , name         = data.name
            , api_key_hash = api_key_hash
            , description  = data.description
            , status_code  = STATUS_CODE_ENUM.ACTIVE.value
            , created_by   = "admin"
        )
        db.add(client)
        db.commit()
        db.refresh(client)

        return client, raw_api_key

    @staticmethod
    def list_system_clients(db: Session) -> List[SYSTEM_CLIENT_RESPONSE_SCHEMA]:
        rows = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None))
            .order_by(SYSTEM_CLIENT_MODEL.created_datetime.desc())
            .all()
        )
        return [SYSTEM_CLIENT_RESPONSE_SCHEMA.model_validate(r) for r in rows]

    @staticmethod
    def revoke_system_client(
        db     : Session
        , code : str
    ) -> SYSTEM_CLIENT_RESPONSE_SCHEMA:
        client = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == code
                , SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not client:
            raise NOT_FOUND_EXCEPTION(f"System client '{code}' was not found.")

        client.status_code      = STATUS_CODE_ENUM.INACTIVE.value
        client.updated_datetime = datetime.now(timezone.utc)
        client.updated_by       = "admin"
        db.commit()
        db.refresh(client)
        return SYSTEM_CLIENT_RESPONSE_SCHEMA.model_validate(client)

    @staticmethod
    def verify_api_key(
        db            : Session
        , client_code : str
        , raw_api_key : str
    ) -> bool:
        client = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == client_code
                , SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None)
                , SYSTEM_CLIENT_MODEL.status_code.in_([STATUS_CODE_ENUM.ACTIVE.value, COMMON_STATUS_ENUM.ACTIVE.value])
            )
            .first()
        )

        if not client:
            return False

        return client.api_key_hash == hash_api_key(raw_api_key)
