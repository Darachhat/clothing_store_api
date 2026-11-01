import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.models import SYSTEM_LOG_MODEL, TELEGRAM_OUTBOUND_MODEL
from app.schemas.system_log_schema import (
    SYSTEM_LOG_LIST_OUT_SCHEMA
    , SYSTEM_LOG_RESPONSE_SCHEMA
    , TELEGRAM_OUTBOUND_RESPONSE_SCHEMA
)


class LOG_SERVICE:
    """
    Service for persisting and querying SYSTEM_LOG_MODEL and TELEGRAM_OUTBOUND_MODEL records.
    Both inbound (requests to our API) and outbound (requests to external APIs)
    are written as fire-and-forget background tasks to avoid blocking the main request path.
    """

    @staticmethod
    def _write(
        db              : Session
        , traffic_type  : str
        , system_code   : Optional[str]
        , request_id    : Optional[str]
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
        try:
            log = SYSTEM_LOG_MODEL(
                client_log_id          = request_id
                , traffic_type         = traffic_type
                , system_code          = system_code
                , channel              = channel
                , request_method       = method
                , request_endpoint     = endpoint
                , request_netloc       = netloc
                , request_content_type = content_type
                , request_user_agent   = user_agent
                , request_headers      = req_headers
                , request_body         = req_body
                , requested_datetime   = req_datetime or datetime.now(timezone.utc)
                , client_ip            = client_ip
                , response_code        = resp_code
                , response_headers     = resp_headers
                , response_body        = resp_body
                , response_duration    = resp_duration
                , response_datetime    = resp_datetime or datetime.now(timezone.utc)
                , status_code          = "active"
            )
            db.add(log)
            db.commit()
        except Exception as exc:
            logger.error(f"[LOG_SERVICE] Failed to persist system_log record: {str(exc)}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def write_inbound(
        db              : Session
        , request_id    : str
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
        LOG_SERVICE._write(
            db              = db
            , traffic_type  = "inbound"
            , system_code   = system_code
            , request_id    = request_id
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

    @staticmethod
    def write_outbound(
        db              : Session
        , request_id    : Optional[str]
        , system_code   : Optional[str]
        , method        : str
        , endpoint      : str
        , netloc        : Optional[str]      = None
        , content_type  : Optional[str]      = None
        , req_headers   : Optional[Dict]     = None
        , req_body      : Optional[Any]      = None
        , req_datetime  : Optional[datetime] = None
        , resp_code     : Optional[int]      = None
        , resp_headers  : Optional[Dict]     = None
        , resp_body     : Optional[Any]      = None
        , resp_duration : Optional[Decimal]  = None
        , resp_datetime : Optional[datetime] = None
        , channel       : Optional[str]      = "SYSTEM"
    ) -> None:
        LOG_SERVICE._write(
            db              = db
            , traffic_type  = "outbound"
            , system_code   = system_code
            , request_id    = request_id or f"out_{uuid.uuid4().hex[:12]}"
            , method        = method
            , endpoint      = endpoint
            , netloc        = netloc
            , content_type  = content_type
            , user_agent    = None
            , req_headers   = req_headers
            , req_body      = req_body
            , req_datetime  = req_datetime
            , client_ip     = None
            , resp_code     = resp_code
            , resp_headers  = resp_headers
            , resp_body     = resp_body
            , resp_duration = resp_duration
            , resp_datetime = resp_datetime
            , channel       = channel
        )

    @staticmethod
    def list_system_logs(
        db             : Session
        , traffic_type : Optional[str] = None
        , system_code  : Optional[str] = None
        , page         : int           = 1
        , size         : int           = 50
    ) -> SYSTEM_LOG_LIST_OUT_SCHEMA:
        query = db.query(SYSTEM_LOG_MODEL).filter(
            SYSTEM_LOG_MODEL.deleted_datetime.is_(None)
        )
        if traffic_type:
            query = query.filter(SYSTEM_LOG_MODEL.traffic_type == traffic_type)
        if system_code:
            query = query.filter(SYSTEM_LOG_MODEL.system_code == system_code)

        total = query.count()
        rows  = (
            query.order_by(SYSTEM_LOG_MODEL.created_datetime.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return SYSTEM_LOG_LIST_OUT_SCHEMA(
            items   = [SYSTEM_LOG_RESPONSE_SCHEMA.model_validate(r) for r in rows]
            , total = total
            , page  = page
            , size  = size
        )

    @staticmethod
    def list_telegram_outbound(
        db                   : Session
        , telegram_chat_code : Optional[str] = None
        , limit              : int           = 50
    ) -> List[TELEGRAM_OUTBOUND_RESPONSE_SCHEMA]:
        query = db.query(TELEGRAM_OUTBOUND_MODEL).filter(
            TELEGRAM_OUTBOUND_MODEL.deleted_datetime.is_(None)
        )
        if telegram_chat_code:
            query = query.filter(TELEGRAM_OUTBOUND_MODEL.telegram_chat_code == telegram_chat_code)

        rows = query.order_by(TELEGRAM_OUTBOUND_MODEL.created_datetime.desc()).limit(limit).all()
        return [TELEGRAM_OUTBOUND_RESPONSE_SCHEMA.model_validate(r) for r in rows]

