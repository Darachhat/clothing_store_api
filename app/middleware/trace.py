import json
import time
from typing import Any, Dict, List, Optional

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.constants import DEFAULT_TIMEZONE
from app.core.logger import trace_logger
from app.core.utils.crypto_utils import generate_ulid, redact_headers
from app.core.utils.date_utils import get_current_time

MAX_TRACE_BODY_BYTES = 16384


class TRACE_MIDDLEWARE:
    """
    Pure ASGI outermost trace middleware writing structured JSON-lines records
    to logs/trace.log for every HTTP request/response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _decode_body(raw: bytes) -> Optional[Any]:
        if not raw:
            return None
        clipped = raw[:MAX_TRACE_BODY_BYTES]
        try:
            return json.loads(clipped.decode("utf-8"))
        except Exception:
            try:
                return clipped.decode("utf-8", errors="replace")
            except Exception:
                return "<binary>"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        start_time   = time.perf_counter()
        timestamp    = get_current_time(DEFAULT_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
        method       = scope.get("method", "")
        path         = scope.get("path", "")
        query_string = (scope.get("query_string") or b"").decode("utf-8", errors="replace")
        client_tuple = scope.get("client")
        client_ip    = client_tuple[0] if client_tuple else None

        raw_req_headers : Dict[str, str] = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in (scope.get("headers") or [])
        }
        trace_id = raw_req_headers.get("x-request-id") or generate_ulid()

        req_chunks   : List[bytes]    = []
        resp_chunks  : List[bytes]    = []
        status_code  : int            = 500
        resp_headers : Dict[str, str] = {}

        async def wrapped_receive() -> Message:
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                if body:
                    req_chunks.append(body)
            return message

        async def wrapped_send(message: Message) -> None:
            nonlocal status_code, resp_headers
            msg_type = message.get("type")
            if msg_type == "http.response.start":
                status_code  = int(message.get("status", 200))
                resp_headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in (message.get("headers") or [])
                }
            elif msg_type == "http.response.body":
                body = message.get("body", b"")
                if body:
                    resp_chunks.append(body)
            await send(message)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            req_raw     = b"".join(req_chunks)
            resp_raw    = b"".join(resp_chunks)

            trace_record = {
                "timestamp"         : timestamp
                , "trace_id"        : resp_headers.get("x-request-id", trace_id)
                , "method"          : method
                , "path"            : path
                , "query"           : query_string or None
                , "client_ip"       : raw_req_headers.get("x-forwarded-for", client_ip)
                , "status_code"     : status_code
                , "duration_ms"     : duration_ms
                , "request_headers" : redact_headers(raw_req_headers)
                , "request_body"    : TRACE_MIDDLEWARE._decode_body(req_raw)
                , "response_body"   : TRACE_MIDDLEWARE._decode_body(resp_raw)
            }
            trace_logger.write(trace_record)

