from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.schemas.system_log_schema import (
    SYSTEM_LOG_LIST_OUT_SCHEMA
    , TELEGRAM_OUTBOUND_RESPONSE_SCHEMA
)
from app.services.log_service import LOG_SERVICE

router = APIRouter(prefix="/logs", tags=["Traffic Audit & System Logs"])


@router.get(
    "/system"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_LOG_LIST_OUT_SCHEMA]
)
def list_system_logs(
    traffic_type  : Optional[str] = Query(default=None, description="inbound | outbound")
    , system_code : Optional[str] = Query(default=None)
    , page        : int           = Query(default=1, ge=1)
    , size        : int           = Query(default=50, ge=1, le=200)
    , db          : Session       = Depends(get_db)
):
    data = LOG_SERVICE.list_system_logs(
        db             = db
        , traffic_type = traffic_type
        , system_code  = system_code
        , page         = page
        , size         = size
    )
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System logs retrieved successfully."
    )


@router.get(
    "/telegram-outbound"
    , response_model = RESPONSE_ENVELOPE[List[TELEGRAM_OUTBOUND_RESPONSE_SCHEMA]]
)
def list_telegram_outbound_logs(
    telegram_chat_code : Optional[str] = Query(default=None)
    , limit            : int           = Query(default=50, ge=1, le=200)
    , db               : Session       = Depends(get_db)
):
    data = LOG_SERVICE.list_telegram_outbound(
        db                   = db
        , telegram_chat_code = telegram_chat_code
        , limit              = limit
    )
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Telegram outbound logs retrieved successfully."
    )

