"""Authentication service: user JWT auth (login, logout, refresh, change password) & system client API key auth."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta, timezone
from typing import List, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BAD_REQUEST_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.security import (
    create_access_token
    , create_refresh_token
    , hash_password
    , verify_password
)
from app.core.utils.crypto_utils import generate_api_key, hash_api_key
from app.models.auth_model import SYSTEM_CLIENT_MODEL
from app.models.user import RefreshToken, User
from app.repositories.user_repository import RefreshTokenRepository, UserRepository
from app.schemas.auth_schema import (
    SYSTEM_CLIENT_CREATE_SCHEMA
    , SYSTEM_CLIENT_RESPONSE_SCHEMA
)


class AUTH_SERVICE:
    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self.user_repo  = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    # ── User JWT Authentication (Clothing Store RBAC) ─────────────────────────

    async def login(
        self
        , username : str
        , password : str
        , request  : Request | None = None
    ) -> dict:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid username or password"
            )
        if user.status != "ACTIVE":
            raise HTTPException(
                status_code = status.HTTP_403_FORBIDDEN
                , detail    = "Account is not active"
            )

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

    async def refresh(self, refresh_token: str) -> dict:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        stored     = await self.token_repo.get_by_hash(token_hash)

        if not stored or stored.revoked:
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Invalid or revoked refresh token"
            )
        if stored.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise HTTPException(
                status_code = status.HTTP_401_UNAUTHORIZED
                , detail    = "Refresh token expired"
            )

        stored.revoked = True

        user = await self.user_repo.get_by_id(stored.user_id)
        if not user or user.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

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
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = "Current password is incorrect"
            )
        user.hashed_password = hash_password(new_password)
        await self.db.commit()

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
            , status_code  = "active"
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

        client.status_code      = "inactive"
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
                , SYSTEM_CLIENT_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )

        if not client:
            return False

        return client.api_key_hash == hash_api_key(raw_api_key)


AuthService = AUTH_SERVICE
