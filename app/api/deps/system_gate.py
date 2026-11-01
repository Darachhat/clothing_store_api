"""Global inbound gate: validates the system/client credential on every API call.

Mode comes from ``settings.system_auth_mode``:
  off     -> skipped
  audit   -> validate when present; log what *would* be rejected; never block
  enforce -> missing/invalid credential => 401 (except allow-listed paths)
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from app.api.deps.database import get_db
from app.core.config import settings
from app.core.enum.common_enum import CHANNEL_ENUM
from app.core.exceptions import UNAUTHORIZED_EXCEPTION
from app.core.logger import logger
from app.services.system_auth_service import SYSTEM_AUTH_SERVICE

# Callers that cannot attach the front-end credential (docs, probes, bank callback,
# phone scanner pairing/WebSocket, static uploads). They keep their own protections.
BUILTIN_PUBLIC_PREFIXES = (
    "/health"
    , "/api/v1/health"
    , "/api/docs"
    , "/api/redoc"
    , "/api/v1/openapi.json"
    , "/uploads"
    , "/api/payments/aba/pushback"
    , "/api/v1/scanner/"
)


def is_public_path(path: str) -> bool:
    prefixes = BUILTIN_PUBLIC_PREFIXES + tuple(settings.SYSTEM_AUTH_PUBLIC_PATHS)
    return any(path == p.rstrip("/") or path.startswith(p) for p in prefixes)


def system_gate(
    conn : HTTPConnection
    , db : Session = Depends(get_db)
) -> None:
    mode = settings.system_auth_mode
    if mode == "off" or is_public_path(conn.url.path):
        return

    context, error = SYSTEM_AUTH_SERVICE.authenticate(db, conn.headers)

    if context:
        conn.state.auth        = context
        conn.state.system_code = context.system_code
        conn.state.channel     = CHANNEL_ENUM.SYSTEM.value
        return

    reason = error or f"missing {settings.SYSTEM_AUTH_HEADER_NAME} credential"
    if mode == "enforce":
        logger.warning(f"[SYSTEM_GATE] rejected {conn.url.path}: {reason}")
        raise UNAUTHORIZED_EXCEPTION("A valid system credential is required to access this API.")
    logger.warning(f"[SYSTEM_GATE][audit] would reject {conn.url.path}: {reason}")

