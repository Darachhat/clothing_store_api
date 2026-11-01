from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.types import AUTH_CONTEXT


class SYSTEM_AUTH_MIDDLEWARE(BaseHTTPMiddleware):
    """
    Seeds an *anonymous* AUTH_CONTEXT on every request.

    It deliberately trusts nothing from request headers. Credentials are validated against the
    auth.* tables by the `system_gate` dependency (app/api/deps/system_gate.py), which upgrades
    request.state.auth only for a verified system/client credential.
    """
    async def dispatch(
        self
        , request   : Request
        , call_next : Callable
    ) -> Response:
        request.state.auth = AUTH_CONTEXT(
            system_code        = "anonymous"
            , auth_type        = None
            , channel          = None
            , is_authenticated = False
            , permissions      = []
        )
        request.state.system_code = None
        request.state.channel     = None
        return await call_next(request)
