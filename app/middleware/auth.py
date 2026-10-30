from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.enum.common_enum import AUTH_TYPE_ENUM, CHANNEL_ENUM
from app.core.utils.crypto_utils import parse_basic_auth
from app.middleware.types import AUTH_CONTEXT


class SYSTEM_AUTH_MIDDLEWARE(BaseHTTPMiddleware):
    """
    Middleware establishing request AUTH_CONTEXT based on API Key, Basic Auth, or Bearer headers.
    """
    async def dispatch(
        self
        , request   : Request
        , call_next : Callable
    ) -> Response:
        api_key     = request.headers.get(settings.API_KEY_HEADER_NAME)
        client_id   = request.headers.get("X-CLIENT-ID")
        auth_header = request.headers.get("Authorization", "")

        if api_key:
            auth_context = AUTH_CONTEXT(
                system_code        = client_id or "authenticated_client"
                , client_id        = client_id
                , auth_type        = AUTH_TYPE_ENUM.API_KEY.value
                , channel          = CHANNEL_ENUM.SYSTEM.value
                , is_authenticated = True
                , permissions      = ["*"]
            )
        elif auth_header.lower().startswith("basic "):
            parsed       = parse_basic_auth(auth_header)
            username     = parsed[0] if parsed else None
            auth_context = AUTH_CONTEXT(
                system_code        = client_id or username or "basic_client"
                , client_id        = client_id or username
                , auth_type        = AUTH_TYPE_ENUM.BASIC.value
                , channel          = CHANNEL_ENUM.SYSTEM.value
                , is_authenticated = bool(parsed)
                , permissions      = ["*"] if parsed else []
            )
        elif auth_header.lower().startswith("bearer "):
            token        = auth_header.split(" ", 1)[1].strip() if " " in auth_header else ""
            auth_context = AUTH_CONTEXT(
                system_code        = client_id or "bearer_client"
                , client_id        = client_id
                , auth_type        = AUTH_TYPE_ENUM.BEARER.value
                , channel          = CHANNEL_ENUM.SYSTEM.value
                , is_authenticated = bool(token)
                , permissions      = ["*"] if token else []
            )
        else:
            auth_context = AUTH_CONTEXT(
                system_code        = "anonymous"
                , auth_type        = None
                , channel          = None
                , is_authenticated = False
                , permissions      = []
            )

        request.state.auth        = auth_context
        request.state.system_code = auth_context.system_code if auth_context.is_authenticated else None
        request.state.channel     = auth_context.channel
        return await call_next(request)

