import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import get_static_session
from app.core.enum.response_enum import RESPONSE_CODE_ENUM
from app.core.exceptions import APP_EXCEPTION
from app.core.logger import logger
from app.core.utils.crypto_utils import redact_headers


class BASE_MIDDLEWARE(BaseHTTPMiddleware):
    """
    Middleware managing:
    - Request ID injection & timing
    - Inbound system_log capture (request + response body & redacted headers) as fire-and-forget background task
    - Fallback exception envelope wrapping
    """

    @staticmethod
    def _safe_parse_json(raw: bytes) -> Optional[Any]:
        """Safely parse raw bytes into JSON. Returns None if not valid JSON."""
        try:
            return json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            return None

    @staticmethod
    def _safe_headers(headers) -> Dict[str, Any]:
        return redact_headers(dict(headers)) if headers else {}

    async def dispatch(
        self
        , request   : Request
        , call_next : Callable
    ) -> Response:
        start_time               = time.time()
        req_datetime             = datetime.now(timezone.utc)
        request_id               = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
        request.state.request_id = request_id

        raw_body      = await request.body()
        req_body_json = BASE_MIDDLEWARE._safe_parse_json(raw_body)

        async def receive():
            return {"type": "http.request", "body": raw_body}

        request = Request(request.scope, receive, request._send)

        client_ip   = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
        req_headers = BASE_MIDDLEWARE._safe_headers(request.headers)

        logger.info(f"[{request_id}] Inbound {request.method} {request.url.path} client_ip={client_ip}")

        resp_code      : Optional[int]      = None
        resp_headers   : Dict[str, Any]     = {}
        resp_body_json : Optional[Any]      = None
        resp_duration  : Optional[Decimal]  = None
        resp_datetime  : Optional[datetime] = None

        try:
            response   = await call_next(request)
            resp_bytes = b""
            if hasattr(response, "body_iterator"):
                chunks = [chunk async for chunk in response.body_iterator]
                resp_bytes = b"".join(
                    c if isinstance(c, bytes) else str(c).encode("utf-8")
                    for c in chunks
                )
                response = Response(
                    content       = resp_bytes
                    , status_code = response.status_code
                    , headers     = dict(response.headers)
                    , media_type  = response.media_type
                    , background  = response.background
                )
            elif hasattr(response, "body"):
                resp_bytes = response.body or b""

            duration_ms                            = round((time.time() - start_time) * 1000, 2)
            resp_datetime                          = datetime.now(timezone.utc)
            resp_duration                          = Decimal(str(duration_ms))
            resp_code                              = response.status_code
            response.headers["X-Request-ID"]       = request_id
            response.headers["X-Response-Time-MS"] = str(duration_ms)
            resp_headers                           = BASE_MIDDLEWARE._safe_headers(response.headers)
            resp_body_json                         = BASE_MIDDLEWARE._safe_parse_json(resp_bytes)

            logger.info(f"[{request_id}] Outbound status={resp_code} in {duration_ms}ms")
            return response

        except APP_EXCEPTION as exc:
            duration_ms   = round((time.time() - start_time) * 1000, 2)
            resp_duration = Decimal(str(duration_ms))
            resp_datetime = datetime.now(timezone.utc)
            resp_code     = exc.status_code
            logger.warning(f"[{request_id}] Domain Exception: code={exc.code} msg='{exc.message}' ({duration_ms}ms)")
            content = {
                "code"         : exc.code
                , "message"    : exc.message
                , "data"       : None
                , "errors"     : exc.errors
                , "request_id" : request_id
                , "detail"     : exc.message
            }
            json_resp = JSONResponse(
                status_code = exc.status_code
                , content   = content
                , headers   = {"X-Request-ID": request_id, "X-Response-Time-MS": str(duration_ms)}
            )
            resp_headers   = BASE_MIDDLEWARE._safe_headers(json_resp.headers)
            resp_body_json = content
            return json_resp

        except Exception as exc:
            duration_ms   = round((time.time() - start_time) * 1000, 2)
            resp_duration = Decimal(str(duration_ms))
            resp_datetime = datetime.now(timezone.utc)
            resp_code     = 500
            logger.error(f"[{request_id}] Unhandled Exception: {str(exc)} ({duration_ms}ms)", exc_info=True)
            content = {
                "code"         : RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR
                , "message"    : "An unexpected server error occurred."
                , "data"       : None
                , "errors"     : [str(exc)]
                , "request_id" : request_id
                , "detail"     : "Internal server error"
            }
            json_resp = JSONResponse(
                status_code = 500
                , content   = content
                , headers   = {"X-Request-ID": request_id, "X-Response-Time-MS": str(duration_ms)}
            )
            resp_headers   = BASE_MIDDLEWARE._safe_headers(json_resp.headers)
            resp_body_json = content
            return json_resp

        finally:
            if settings.ENABLE_ACCESS_AUDIT_LOG:
                system_code = (
                    getattr(request.state, "system_code", None)
                    or getattr(getattr(request.state, "auth", None), "system_code", None)
                )
                channel = (
                    getattr(request.state, "channel", None)
                    or getattr(getattr(request.state, "auth", None), "channel", None)
                )
                try:
                    asyncio.create_task(
                        BASE_MIDDLEWARE._persist_inbound_log(
                            request_id      = request_id
                            , system_code   = system_code
                            , channel       = channel
                            , method        = request.method
                            , endpoint      = str(request.url.path)
                            , netloc        = request.url.netloc
                            , content_type  = request.headers.get("content-type")
                            , user_agent    = request.headers.get("user-agent")
                            , req_headers   = req_headers
                            , req_body      = req_body_json
                            , req_datetime  = req_datetime
                            , client_ip     = client_ip
                            , resp_code     = resp_code
                            , resp_headers  = resp_headers
                            , resp_body     = resp_body_json
                            , resp_duration = resp_duration
                            , resp_datetime = resp_datetime
                        )
                    )
                except RuntimeError:
                    pass

    @staticmethod
    async def _persist_inbound_log(
        request_id      : str
        , system_code   : Optional[str]
        , method        : str
        , endpoint      : str
        , netloc        : Optional[str]      = None
        , content_type  : Optional[str]      = None
        , user_agent    : Optional[str]      = None
        , req_headers   : Optional[Dict]     = None
        , req_body      : Optional[Any]      = None
        , req_datetime  : Optional[datetime] = None
        , client_ip     : Optional[str]      = None
        , resp_code     : Optional[int]      = None
        , resp_headers  : Optional[Dict]     = None
        , resp_body     : Optional[Any]      = None
        , resp_duration : Optional[Decimal]  = None
        , resp_datetime : Optional[datetime] = None
        , channel       : Optional[str]      = None
    ) -> None:
        from app.services.log_service import LOG_SERVICE

        def _sync_write() -> None:
            db = get_static_session()
            LOG_SERVICE.write_inbound(
                db              = db
                , request_id    = request_id
                , system_code   = system_code
                , method        = method
                , endpoint      = endpoint
                , netloc        = netloc
                , content_type  = content_type
                , user_agent    = user_agent
                , req_headers   = req_headers
                , req_body      = req_body
                , req_datetime  = req_datetime
                , client_ip     = client_ip
                , resp_code     = resp_code
                , resp_headers  = resp_headers
                , resp_body     = resp_body
                , resp_duration = resp_duration
                , resp_datetime = resp_datetime
                , channel       = channel
            )

        await asyncio.to_thread(_sync_write)

