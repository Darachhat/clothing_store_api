from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel


class SYSTEM_LOG_RESPONSE_SCHEMA(BaseModel):
    id                   : uuid.UUID
    client_log_id        : Optional[str]      = None
    traffic_type         : Optional[str]      = None
    system_code          : Optional[str]      = None
    channel              : Optional[str]      = None
    request_method       : str
    request_endpoint     : str
    request_netloc       : Optional[str]      = None
    request_content_type : Optional[str]      = None
    request_user_agent   : Optional[str]      = None
    request_headers      : Optional[Any]      = None
    request_body         : Optional[Any]      = None
    requested_datetime   : Optional[datetime] = None
    client_ip            : Optional[str]      = None
    response_code        : Optional[int]      = None
    response_headers     : Optional[Any]      = None
    response_body        : Optional[Any]      = None
    response_duration    : Optional[Decimal]  = None
    response_datetime    : Optional[datetime] = None
    status_code          : str
    created_datetime     : Optional[datetime] = None

    model_config = {"from_attributes": True}


class SYSTEM_LOG_LIST_OUT_SCHEMA(BaseModel):
    items : List[SYSTEM_LOG_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int


class TELEGRAM_OUTBOUND_RESPONSE_SCHEMA(BaseModel):
    id                  : uuid.UUID
    telegram_chat_code  : Optional[str]      = None
    chat_type           : Optional[str]      = None
    telegram_bot_code   : Optional[str]      = None
    chat_id             : Optional[str]      = None
    thread_id           : Optional[str]      = None
    request_object      : Optional[Any]      = None
    response_object     : Optional[Any]      = None
    is_success          : bool
    telegram_message_id : Optional[str]      = None
    error_code          : Optional[int]      = None
    error_detail        : Optional[str]      = None
    status_code         : str
    created_datetime    : Optional[datetime] = None

    model_config = {"from_attributes": True}

