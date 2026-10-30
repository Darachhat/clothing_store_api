import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.core.constants import HTTP_TIMEOUT_SECONDS
from app.core.logger import logger
from app.core.utils.crypto_utils import redact_headers

_global_httpx_client : Optional[httpx.AsyncClient] = None


def create_httpx_client() -> httpx.AsyncClient:
    """
    Create a pooled httpx.AsyncClient instance configured with application limits and timeouts.
    """
    timeout = httpx.Timeout(
        timeout   = float(settings.HTTP_TIMEOUT_SECONDS)
        , connect = float(settings.HTTP_CONNECT_TIMEOUT_SECONDS)
    )
    limits = httpx.Limits(
        max_connections             = settings.HTTP_MAX_CONNECTIONS
        , max_keepalive_connections = settings.HTTP_MAX_KEEPALIVE_CONNECTIONS
    )
    return httpx.AsyncClient(timeout=timeout, limits=limits)


def set_global_httpx_client(client: Optional[httpx.AsyncClient]) -> None:
    global _global_httpx_client
    _global_httpx_client = client


def get_httpx_client() -> Optional[httpx.AsyncClient]:
    return _global_httpx_client


async def close_global_httpx_client() -> None:
    global _global_httpx_client
    if _global_httpx_client is not None:
        try:
            await _global_httpx_client.aclose()
        except Exception:
            pass
        finally:
            _global_httpx_client = None


class HTTP_CLIENT:
    """
    Asynchronous HTTP Client wrapper using httpx.
    Reuses the global pooled httpx.AsyncClient when available (lifespan / Celery worker)
    or falls back to an ephemeral client context.
    Automatically captures outbound request/response as track.system_log records
    with sensitive headers redacted.
    """

    @staticmethod
    @asynccontextmanager
    async def _client_scope(timeout: int = HTTP_TIMEOUT_SECONDS) -> AsyncIterator[httpx.AsyncClient]:
        if _global_httpx_client is not None and not _global_httpx_client.is_closed:
            yield _global_httpx_client
        else:
            async with httpx.AsyncClient(timeout=timeout) as ephemeral_client:
                yield ephemeral_client

    @staticmethod
    async def request(
        method             : str
        , url              : str
        , params           : Optional[Dict[str, Any]] = None
        , json_data        : Optional[Any]            = None
        , data             : Optional[Any]            = None
        , files            : Optional[Any]            = None
        , headers          : Optional[Dict[str, str]] = None
        , timeout          : int                      = HTTP_TIMEOUT_SECONDS
        , system_code      : Optional[str]            = None
        , request_id       : Optional[str]            = None
        , raise_for_status : bool                     = True
    ) -> Dict[str, Any]:
        req_datetime = datetime.now(timezone.utc)
        req_id       = request_id or f"out_{uuid.uuid4().hex[:12]}"
        parsed_url   = urlparse(url)
        netloc       = parsed_url.netloc
        start_time   = time.time()
        upper_method = method.upper()
        logged_req   = json_data if json_data is not None else data

        async with HTTP_CLIENT._client_scope(timeout=timeout) as client:
            try:
                response = await client.request(
                    method    = upper_method
                    , url     = url
                    , params  = params
                    , json    = json_data
                    , data    = data
                    , files   = files
                    , headers = headers
                    , timeout = timeout
                )
                duration_ms   = round((time.time() - start_time) * 1000, 2)
                resp_datetime = datetime.now(timezone.utc)
                resp_body     = HTTP_CLIENT._safe_json(response)
                content_type  = response.headers.get("content-type")

                logger.info(
                    f"[{req_id}] Outbound {upper_method} {url} -> status={response.status_code} in {duration_ms}ms"
                )

                HTTP_CLIENT._schedule_outbound_log(
                    request_id      = req_id
                    , system_code   = system_code
                    , method        = upper_method
                    , endpoint      = url
                    , netloc        = netloc
                    , content_type  = content_type
                    , req_headers   = redact_headers(headers)
                    , req_body      = logged_req
                    , req_datetime  = req_datetime
                    , resp_code     = response.status_code
                    , resp_headers  = redact_headers(dict(response.headers))
                    , resp_body     = resp_body
                    , resp_duration = Decimal(str(duration_ms))
                    , resp_datetime = resp_datetime
                )

                if raise_for_status:
                    response.raise_for_status()
                return resp_body if isinstance(resp_body, dict) else {"data": resp_body} if resp_body is not None else {}

            except httpx.HTTPStatusError as exc:
                duration_ms   = round((time.time() - start_time) * 1000, 2)
                resp_datetime = datetime.now(timezone.utc)
                logger.error(
                    f"[{req_id}] Outbound {upper_method} error from {url}: status={exc.response.status_code}"
                )

                HTTP_CLIENT._schedule_outbound_log(
                    request_id      = req_id
                    , system_code   = system_code
                    , method        = upper_method
                    , endpoint      = url
                    , netloc        = netloc
                    , content_type  = exc.response.headers.get("content-type")
                    , req_headers   = redact_headers(headers)
                    , req_body      = logged_req
                    , req_datetime  = req_datetime
                    , resp_code     = exc.response.status_code
                    , resp_headers  = redact_headers(dict(exc.response.headers))
                    , resp_body     = HTTP_CLIENT._safe_json(exc.response)
                    , resp_duration = Decimal(str(duration_ms))
                    , resp_datetime = resp_datetime
                )
                raise

            except httpx.TimeoutException as exc:
                duration_ms   = round((time.time() - start_time) * 1000, 2)
                resp_datetime = datetime.now(timezone.utc)
                logger.error(
                    f"[{req_id}] Outbound {upper_method} timeout to {url} after {duration_ms}ms: {str(exc)}"
                )

                HTTP_CLIENT._schedule_outbound_log(
                    request_id      = req_id
                    , system_code   = system_code
                    , method        = upper_method
                    , endpoint      = url
                    , netloc        = netloc
                    , content_type  = None
                    , req_headers   = redact_headers(headers)
                    , req_body      = logged_req
                    , req_datetime  = req_datetime
                    , resp_code     = 504
                    , resp_headers  = {}
                    , resp_body     = {"error": "Gateway Timeout", "detail": str(exc)}
                    , resp_duration = Decimal(str(duration_ms))
                    , resp_datetime = resp_datetime
                )
                raise

            except Exception as exc:
                duration_ms   = round((time.time() - start_time) * 1000, 2)
                resp_datetime = datetime.now(timezone.utc)
                logger.error(
                    f"[{req_id}] Outbound {upper_method} request failure to {url}: {str(exc)}"
                )

                HTTP_CLIENT._schedule_outbound_log(
                    request_id      = req_id
                    , system_code   = system_code
                    , method        = upper_method
                    , endpoint      = url
                    , netloc        = netloc
                    , content_type  = None
                    , req_headers   = redact_headers(headers)
                    , req_body      = logged_req
                    , req_datetime  = req_datetime
                    , resp_code     = 503
                    , resp_headers  = {}
                    , resp_body     = {"error": "Service Unavailable", "detail": str(exc)}
                    , resp_duration = Decimal(str(duration_ms))
                    , resp_datetime = resp_datetime
                )
                raise

    @staticmethod
    async def get(
        url             : str
        , params        : Optional[Dict[str, Any]] = None
        , headers       : Optional[Dict[str, str]] = None
        , timeout       : int                      = HTTP_TIMEOUT_SECONDS
        , system_code   : Optional[str]            = None
        , request_id    : Optional[str]            = None
    ) -> Dict[str, Any]:
        return await HTTP_CLIENT.request(
            method        = "GET"
            , url         = url
            , params      = params
            , headers     = headers
            , timeout     = timeout
            , system_code = system_code
            , request_id  = request_id
        )

    @staticmethod
    async def post(
        url             : str
        , json_data     : Optional[Dict[str, Any]] = None
        , data          : Optional[Any]            = None
        , files         : Optional[Any]            = None
        , headers       : Optional[Dict[str, str]] = None
        , timeout       : int                      = HTTP_TIMEOUT_SECONDS
        , system_code   : Optional[str]            = None
        , request_id    : Optional[str]            = None
    ) -> Dict[str, Any]:
        return await HTTP_CLIENT.request(
            method        = "POST"
            , url         = url
            , json_data   = json_data
            , data        = data
            , files       = files
            , headers     = headers
            , timeout     = timeout
            , system_code = system_code
            , request_id  = request_id
        )

    @staticmethod
    async def put(
        url             : str
        , json_data     : Optional[Dict[str, Any]] = None
        , headers       : Optional[Dict[str, str]] = None
        , timeout       : int                      = HTTP_TIMEOUT_SECONDS
        , system_code   : Optional[str]            = None
        , request_id    : Optional[str]            = None
    ) -> Dict[str, Any]:
        return await HTTP_CLIENT.request(
            method        = "PUT"
            , url         = url
            , json_data   = json_data
            , headers     = headers
            , timeout     = timeout
            , system_code = system_code
            , request_id  = request_id
        )

    @staticmethod
    async def delete(
        url             : str
        , params        : Optional[Dict[str, Any]] = None
        , headers       : Optional[Dict[str, str]] = None
        , timeout       : int                      = HTTP_TIMEOUT_SECONDS
        , system_code   : Optional[str]            = None
        , request_id    : Optional[str]            = None
    ) -> Dict[str, Any]:
        return await HTTP_CLIENT.request(
            method        = "DELETE"
            , url         = url
            , params      = params
            , headers     = headers
            , timeout     = timeout
            , system_code = system_code
            , request_id  = request_id
        )

    @staticmethod
    def _safe_json(response: httpx.Response) -> Optional[Any]:
        """Safely extract JSON from an httpx response. Returns None if body is not JSON."""
        try:
            return response.json()
        except Exception:
            return None

    @staticmethod
    def _schedule_outbound_log(
        request_id      : str
        , system_code   : Optional[str]
        , method        : str
        , endpoint      : str
        , netloc        : Optional[str]
        , content_type  : Optional[str]
        , req_headers   : Optional[Dict]
        , req_body      : Optional[Any]
        , req_datetime  : Optional[datetime]
        , resp_code     : Optional[int]
        , resp_headers  : Optional[Dict]
        , resp_body     : Optional[Any]
        , resp_duration : Optional[Decimal]
        , resp_datetime : Optional[datetime]
    ) -> None:
        try:
            asyncio.create_task(
                HTTP_CLIENT._persist_outbound_log(
                    request_id      = request_id
                    , system_code   = system_code
                    , method        = method
                    , endpoint      = endpoint
                    , netloc        = netloc
                    , content_type  = content_type
                    , req_headers   = req_headers
                    , req_body      = req_body
                    , req_datetime  = req_datetime
                    , resp_code     = resp_code
                    , resp_headers  = resp_headers
                    , resp_body     = resp_body
                    , resp_duration = resp_duration
                    , resp_datetime = resp_datetime
                )
            )
        except RuntimeError:
            pass

    @staticmethod
    async def _persist_outbound_log(
        request_id      : str
        , system_code   : Optional[str]
        , method        : str
        , endpoint      : str
        , netloc        : Optional[str]
        , content_type  : Optional[str]      = None
        , req_headers   : Optional[Dict]     = None
        , req_body      : Optional[Any]      = None
        , req_datetime  : Optional[datetime] = None
        , resp_code     : Optional[int]      = None
        , resp_headers  : Optional[Dict]     = None
        , resp_body     : Optional[Any]      = None
        , resp_duration : Optional[Decimal]  = None
        , resp_datetime : Optional[datetime] = None
    ) -> None:
        from app.core.database import get_static_session
        from app.services.log_service import LOG_SERVICE

        def _sync_write() -> None:
            db = get_static_session()
            LOG_SERVICE.write_outbound(
                db
                , request_id
                , system_code
                , method
                , endpoint
                , netloc
                , content_type
                , req_headers
                , req_body
                , req_datetime
                , resp_code
                , resp_headers
                , resp_body
                , resp_duration
                , resp_datetime
            )

        await asyncio.to_thread(_sync_write)

