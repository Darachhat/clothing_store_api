"""Inbound system/client credential verification against auth.system* tables.

Accepted credentials (first match wins):
  1. ``<SYSTEM_AUTH_HEADER_NAME>: Basic <b64(client:secret)>``  -> auth.credential_basic
  2. ``<SYSTEM_AUTH_HEADER_NAME>: Bearer <token>``              -> auth.credential_bearer
  3. ``X-API-KEY`` + ``X-CLIENT-ID``                            -> auth.system_client

Inbound secrets are stored as ``sha256:<hex>`` (server-generated, high entropy). A stored value
without that prefix is never accepted, so legacy plaintext rows cannot authenticate inbound traffic.
"""
from __future__ import annotations

import hmac
import secrets
from typing import Mapping, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enum.common_enum import AUTH_TYPE_ENUM, CHANNEL_ENUM, TRAFFIC_TYPE_ENUM
from app.core.utils.crypto_utils import hash_api_key, parse_basic_auth
from app.middleware.types import AUTH_CONTEXT
from app.models import (
    CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , SYSTEM_CLIENT_MODEL
    , SYSTEM_MODEL
)

SECRET_PREFIX   = "sha256:"
_ACTIVE         = ("active", "ACTIVE")
AuthResult      = Tuple[Optional[AUTH_CONTEXT], Optional[str]]


def generate_secret(nbytes: int = 32) -> str:
    """URL-safe random secret for inbound credentials (shown to the operator exactly once)."""
    return secrets.token_urlsafe(nbytes)


def hash_inbound_secret(secret: str) -> str:
    return f"{SECRET_PREFIX}{hash_api_key(secret)}"


def _secret_matches(stored: Optional[str], presented: str) -> bool:
    if not stored or not stored.startswith(SECRET_PREFIX):
        return False
    return hmac.compare_digest(stored, hash_inbound_secret(presented))


class SYSTEM_AUTH_SERVICE:

    @staticmethod
    def _system_is_active(db: Session, system_code: str) -> bool:
        return (
            db.query(SYSTEM_MODEL.id)
            .filter(
                SYSTEM_MODEL.code == system_code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
                , SYSTEM_MODEL.status_code.in_(_ACTIVE)
            )
            .first()
        ) is not None

    @staticmethod
    def _context(system_code: str, client_id: str, client_name: str, auth_type: str) -> AUTH_CONTEXT:
        return AUTH_CONTEXT(
            system_code        = system_code
            , client_id        = client_id
            , client_name      = client_name
            , auth_type        = auth_type
            , channel          = CHANNEL_ENUM.SYSTEM.value
            , is_authenticated = True
            , permissions      = []
        )

    @staticmethod
    def _verify_basic(db: Session, header_value: str) -> AuthResult:
        parsed = parse_basic_auth(header_value)
        if not parsed:
            return None, "malformed Basic credential"
        username, password = parsed
        rows = (
            db.query(CREDENTIAL_BASIC_MODEL)
            .filter(
                CREDENTIAL_BASIC_MODEL.username == username
                , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value
                , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
                , CREDENTIAL_BASIC_MODEL.status_code.in_(_ACTIVE)
            )
            .all()
        )
        for cred in rows:
            if _secret_matches(cred.password, password) and SYSTEM_AUTH_SERVICE._system_is_active(db, cred.system_code):
                return SYSTEM_AUTH_SERVICE._context(
                    cred.system_code, str(cred.id), cred.username, AUTH_TYPE_ENUM.BASIC.value
                ), None
        return None, f"invalid Basic credential for '{username}'"

    @staticmethod
    def _verify_bearer(db: Session, token: str) -> AuthResult:
        if not token:
            return None, "empty Bearer token"
        cred = (
            db.query(CREDENTIAL_BEARER_MODEL)
            .filter(
                CREDENTIAL_BEARER_MODEL.token_value == hash_inbound_secret(token)
                , CREDENTIAL_BEARER_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.INBOUND.value
                , CREDENTIAL_BEARER_MODEL.deleted_datetime.is_(None)
                , CREDENTIAL_BEARER_MODEL.status_code.in_(_ACTIVE)
            )
            .first()
        )
        if cred and _secret_matches(cred.token_value, token) and SYSTEM_AUTH_SERVICE._system_is_active(db, cred.system_code):
            return SYSTEM_AUTH_SERVICE._context(
                cred.system_code, str(cred.id), cred.system_code, AUTH_TYPE_ENUM.BEARER.value
            ), None
        return None, "invalid Bearer token"

    @staticmethod
    def _verify_api_key(db: Session, client_code: str, api_key: str) -> AuthResult:
        client = (
            db.query(SYSTEM_CLIENT_MODEL)
            .filter(
                SYSTEM_CLIENT_MODEL.code == client_code
                , SYSTEM_CLIENT_MODEL.deleted_datetime.is_(None)
                , SYSTEM_CLIENT_MODEL.status_code.in_(_ACTIVE)
            )
            .first()
        )
        if client and hmac.compare_digest(client.api_key_hash, hash_api_key(api_key)):
            return SYSTEM_AUTH_SERVICE._context(
                client.code, str(client.id), client.name, AUTH_TYPE_ENUM.API_KEY.value
            ), None
        return None, f"invalid API key for client '{client_code}'"

    @staticmethod
    def authenticate(db: Session, headers: Mapping[str, str]) -> AuthResult:
        """
        Returns (context, None) when a credential is valid, (None, reason) when one was
        presented but is invalid, and (None, None) when no credential was presented at all.
        """
        value = headers.get(settings.SYSTEM_AUTH_HEADER_NAME)
        if value:
            scheme, _, rest = value.strip().partition(" ")
            scheme = scheme.lower()
            if scheme == "basic":
                return SYSTEM_AUTH_SERVICE._verify_basic(db, value.strip())
            if scheme == "bearer":
                return SYSTEM_AUTH_SERVICE._verify_bearer(db, rest.strip())
            return None, f"unsupported scheme '{scheme}' in {settings.SYSTEM_AUTH_HEADER_NAME}"

        api_key = headers.get(settings.API_KEY_HEADER_NAME)
        if api_key:
            client_code = headers.get("X-CLIENT-ID")
            if not client_code:
                return None, "X-CLIENT-ID is required with X-API-KEY"
            return SYSTEM_AUTH_SERVICE._verify_api_key(db, client_code, api_key)

        return None, None

