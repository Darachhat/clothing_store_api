from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
import uuid

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TEMPLATE_BASE_MODEL

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class SYSTEM_LOG_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "system_log"
    __table_args__              = {"schema": "track"}

    id                          : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_log_id               : Mapped[Optional[str]]      = mapped_column(String(40), nullable=True)

    traffic_type                : Mapped[Optional[str]]      = mapped_column(String(20), nullable=True)
    system_code                 : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    channel                     : Mapped[Optional[str]]      = mapped_column(String(50), nullable=True)

    request_method              : Mapped[str]                = mapped_column(String(10), nullable=False)
    request_endpoint            : Mapped[str]                = mapped_column(Text, nullable=False)
    request_netloc              : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    request_content_type        : Mapped[Optional[str]]      = mapped_column(String(255), nullable=True)
    request_user_agent          : Mapped[Optional[str]]      = mapped_column(Text, nullable=True)
    request_headers             : Mapped[Optional[Any]]      = mapped_column(JSON_TYPE, nullable=True)
    request_body                : Mapped[Optional[Any]]      = mapped_column(JSON_TYPE, nullable=True)
    requested_datetime          : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    client_ip                   : Mapped[Optional[str]]      = mapped_column(String(50), nullable=True)

    response_code               : Mapped[Optional[int]]      = mapped_column(Integer, nullable=True)
    response_headers            : Mapped[Optional[Any]]      = mapped_column(JSON_TYPE, nullable=True)
    response_body               : Mapped[Optional[Any]]      = mapped_column(JSON_TYPE, nullable=True)
    response_duration           : Mapped[Optional[Decimal]]  = mapped_column(Numeric, nullable=True)
    response_datetime           : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status_code                 : Mapped[str]                = mapped_column(String(10), default="active", nullable=False)


class TELEGRAM_OUTBOUND_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "telegram_outbound"
    __table_args__              = {"schema": "track"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_chat_code          : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chat_type                   : Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telegram_bot_code           : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chat_id                     : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thread_id                   : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    request_object              : Mapped[Optional[Any]] = mapped_column(JSON_TYPE, nullable=True)
    response_object             : Mapped[Optional[Any]] = mapped_column(JSON_TYPE, nullable=True)
    is_success                  : Mapped[bool]          = mapped_column(Boolean, default=True, nullable=False)
    telegram_message_id         : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_code                  : Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_detail                : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)

