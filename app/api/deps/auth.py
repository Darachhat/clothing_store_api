from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
from app.core.config import settings
from app.core.deps import (
    get_current_active_user
    , get_current_user
    , require_permission
)
from app.core.enum.common_enum import AUTH_TYPE_ENUM, CHANNEL_ENUM, TRAFFIC_TYPE_ENUM
from app.core.exceptions import UNAUTHORIZED_EXCEPTION
from app.core.logger import logger
from app.core.utils.crypto_utils import hash_api_key, parse_basic_auth
from app.middleware.types import AUTH_CONTEXT
from app.models.auth_model import (
    CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , SYSTEM_CLIENT_MODEL
)


class AUTH_DEPS:
    """
    FastAPI dependency class providing layered authentication checks.
    Modeled after templete_api's AUTH_DEPS and AUTH_CONTEXT architecture.
    """

    @staticmethod
    def get_context(request: Request) -> AUTH_CONTEXT:
        auth : AUTH_CONTEXT = getattr(request.state, "auth", None)
        if not auth:
            raise UNAUTHORIZED_EXCEPTION("Authentication context missing from request state.")
        return auth

    @staticmethod
    def require_authenticated(
        auth : AUTH_CONTEXT = Depends(get_context)
    ) -> AUTH_CONTEXT:
        if not auth.is_authenticated:
            raise UNAUTHORIZED_EXCEPTION("Valid credentials are required to access this resource.")
        return auth

    @staticmethod
    def require_verified_client(
        request : Request
        , db    : Session      = Depends(get_db)
        , auth  : AUTH_CONTEXT = Depends(get_context)
    ) -> AUTH_CONTEXT:
        raw_api_key = request.headers.get(settings.API_KEY_HEADER_NAME)
        client_code = request.headers.get("X-CLIENT-ID")

        if not raw_api_key:
            raise UNAUTHORIZED_EXCEPTION(f"Missing required header: {settings.API_KEY_HEADER_NAME}")

        if not client_code:
            raise UNAUTHORIZED_EXCEPTION("Missing required header: X-CLIENT-ID")

        client : Optional[SYSTEM_CLIENT_MODEL] = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == client_code
                , SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None)
                , SYSTEM_CLIENT_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )

        if not client:
            logger.warning(f"[AUTH_DEPS] Unknown or inactive system client: code={client_code}")
            raise UNAUTHORIZED_EXCEPTION(f"System client '{client_code}' is not registered or is inactive.")

        if client.api_key_hash != hash_api_key(raw_api_key):
            logger.warning(f"[AUTH_DEPS] Invalid API key for client: code={client_code}")
            raise UNAUTHORIZED_EXCEPTION("Invalid API key provided.")

        auth.client_id            = str(client.id)
        auth.client_name          = client.name
        auth.system_code          = client.code
        auth.auth_type            = AUTH_TYPE_ENUM.API_KEY.value
        auth.channel              = CHANNEL_ENUM.SYSTEM.value
        auth.is_authenticated     = True
        request.state.system_code = client.code
        request.state.channel     = CHANNEL_ENUM.SYSTEM.value

        return auth

    @staticmethod
    def require_basic_credential(
        request : Request
        , db    : Session      = Depends(get_db)
        , auth  : AUTH_CONTEXT = Depends(get_context)
    ) -> AUTH_CONTEXT:
        auth_header = request.headers.get("Authorization")
        parsed      = parse_basic_auth(auth_header)
        if not parsed:
            raise UNAUTHORIZED_EXCEPTION("Missing or malformed Basic Authorization header.")

        username, password = parsed
        cred : Optional[CREDENTIAL_BASIC_MODEL] = (
            db.query(CREDENTIAL_BASIC_MODEL)
            .filter(
                CREDENTIAL_BASIC_MODEL.username == username
                , CREDENTIAL_BASIC_MODEL.password == password
                , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value
                , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
                , CREDENTIAL_BASIC_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )

        if not cred:
            logger.warning(f"[AUTH_DEPS] Invalid Basic Auth credentials for username={username}")
            raise UNAUTHORIZED_EXCEPTION("Invalid Basic Auth credentials.")

        auth.client_id            = str(cred.id)
        auth.client_name          = cred.username
        auth.system_code          = cred.system_code
        auth.auth_type            = AUTH_TYPE_ENUM.BASIC.value
        auth.channel              = CHANNEL_ENUM.SYSTEM.value
        auth.is_authenticated     = True
        request.state.system_code = cred.system_code
        request.state.channel     = CHANNEL_ENUM.SYSTEM.value

        return auth

    @staticmethod
    def require_bearer_credential(
        request : Request
        , db    : Session      = Depends(get_db)
        , auth  : AUTH_CONTEXT = Depends(get_context)
    ) -> AUTH_CONTEXT:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            raise UNAUTHORIZED_EXCEPTION("Missing or malformed Bearer Authorization header.")

        token = auth_header.split(" ", 1)[1].strip()
        cred : Optional[CREDENTIAL_BEARER_MODEL] = (
            db.query(CREDENTIAL_BEARER_MODEL)
            .filter(
                CREDENTIAL_BEARER_MODEL.token_value == token
                , CREDENTIAL_BEARER_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value
                , CREDENTIAL_BEARER_MODEL.deleted_datetime.is_(None)
                , CREDENTIAL_BEARER_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )

        if not cred:
            logger.warning("[AUTH_DEPS] Invalid Bearer token credential.")
            raise UNAUTHORIZED_EXCEPTION("Invalid Bearer token credential.")

        auth.client_id            = str(cred.id)
        auth.client_name          = cred.system_code
        auth.system_code          = cred.system_code
        auth.auth_type            = AUTH_TYPE_ENUM.BEARER.value
        auth.channel              = CHANNEL_ENUM.SYSTEM.value
        auth.is_authenticated     = True
        request.state.system_code = cred.system_code
        request.state.channel     = CHANNEL_ENUM.SYSTEM.value

        return auth


__all__ = [
    "AUTH_DEPS"
    , "get_current_user"
    , "get_current_active_user"
    , "require_permission"
]

