from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
from app.core.config import settings
from app.core.deps import (
    get_current_active_user
    , get_current_user
    , require_permission
)
from app.core.exceptions import UNAUTHORIZED_EXCEPTION
from app.core.logger import logger
from app.middleware.types import AUTH_CONTEXT
from app.services.system_auth_service import SYSTEM_AUTH_SERVICE


class AUTH_DEPS:
    """
    Per-route dependencies for endpoints that must be called by an authenticated *system client*.
    All verification is delegated to SYSTEM_AUTH_SERVICE (the same code the global gate uses),
    so secrets are only ever compared against their stored hashes.
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
    def require_system_credential(
        request : Request
        , db    : Session = Depends(get_db)
    ) -> AUTH_CONTEXT:
        context, error = SYSTEM_AUTH_SERVICE.authenticate(db, request.headers)
        if not context:
            logger.warning(f"[AUTH_DEPS] system credential rejected: {error or 'not provided'}")
            raise UNAUTHORIZED_EXCEPTION(
                f"A valid credential is required in {settings.SYSTEM_AUTH_HEADER_NAME} "
                f"or {settings.API_KEY_HEADER_NAME} + X-CLIENT-ID."
            )
        request.state.auth        = context
        request.state.system_code = context.system_code
        request.state.channel     = context.channel
        return context

    # Backwards-compatible names used by earlier template code; all share one verifier.
    require_verified_client    = require_system_credential
    require_basic_credential   = require_system_credential
    require_bearer_credential  = require_system_credential


__all__ = [
    "AUTH_DEPS"
    , "get_current_user"
    , "get_current_active_user"
    , "require_permission"
]
