from typing import Any, Optional
import uuid

from sqlalchemy import Boolean, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BASE_MODEL

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class SYSTEM_MODEL(BASE_MODEL):
    __tablename__               = "system"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_url                    : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    scope                       : Mapped[str]           = mapped_column(String(50), nullable=False, default="external")
    is_encrypted_body           : Mapped[bool]          = mapped_column(Boolean, default=False, nullable=False)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class SYSTEM_CLIENT_MODEL(BASE_MODEL):
    __tablename__               = "system_client"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, index=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    api_key_hash                : Mapped[str]           = mapped_column(String(255), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class SYSTEM_CREDENTIAL_MODEL(BASE_MODEL):
    __tablename__               = "system_credential"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False)
    auth_type_code              : Mapped[str]           = mapped_column(String(50), nullable=False)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class CREDENTIAL_BASIC_MODEL(BASE_MODEL):
    __tablename__               = "credential_basic"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False)
    username                    : Mapped[str]           = mapped_column(String(255), nullable=False)
    password                    : Mapped[str]           = mapped_column(Text, nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class CREDENTIAL_BEARER_MODEL(BASE_MODEL):
    __tablename__               = "credential_bearer"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False)
    header_name                 : Mapped[str]           = mapped_column(String(100), nullable=False, default="Authorization")
    token_prefix                : Mapped[str]           = mapped_column(String(50), nullable=False, default="Bearer")
    token_value                 : Mapped[str]           = mapped_column(Text, nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class CREDENTIAL_API_KEY_MODEL(BASE_MODEL):
    __tablename__               = "credential_api_key"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False)
    key_location                : Mapped[str]           = mapped_column(String(20), nullable=False, default="header")
    key_name                    : Mapped[str]           = mapped_column(String(100), nullable=False)
    key_value                   : Mapped[str]           = mapped_column(Text, nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class CREDENTIAL_OAUTH2_MODEL(BASE_MODEL):
    __tablename__               = "credential_oauth2"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False)
    token_url                   : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    grant_type                  : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    client_id                   : Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_secret               : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    username                    : Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password                    : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class TELEGRAM_BOT_MODEL(BASE_MODEL):
    __tablename__               = "telegram_bot"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    user_id                     : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    username                    : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    token                       : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class TELEGRAM_CHAT_MODEL(BASE_MODEL):
    __tablename__               = "telegram_chat"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    telegram_bot_code           : Mapped[str]           = mapped_column(String(100), nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    chat_type                   : Mapped[Optional[str]] = mapped_column("type", String(50), nullable=True)
    link                        : Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    chat_id                     : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    thread_id                   : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class SYSTEM_ENDPOINT_MODEL(BASE_MODEL):
    __tablename__               = "system_endpoint"
    __table_args__              = {"schema": "auth"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_code                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    code                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    operation_type              : Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    endpoint                    : Mapped[str]           = mapped_column(String(500), nullable=False)
    http_method                 : Mapped[str]           = mapped_column(String(10), nullable=False, default="POST")
    traffic_type                : Mapped[str]           = mapped_column(String(20), nullable=False, default="outbound")
    request_timeout             : Mapped[int]           = mapped_column(Integer, nullable=False, default=30)
    headers_config              : Mapped[Optional[Any]] = mapped_column(JSON_TYPE, nullable=True)
    query_config                : Mapped[Optional[Any]] = mapped_column(JSON_TYPE, nullable=True)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)

