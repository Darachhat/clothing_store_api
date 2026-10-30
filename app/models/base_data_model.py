from typing import Optional
import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TEMPLATE_BASE_MODEL


class TRANSLATE_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "translate"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ref_id                      : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), nullable=False)
    schema_name                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    table_name                  : Mapped[str]           = mapped_column(String(100), nullable=False)
    column_name                 : Mapped[str]           = mapped_column(String(100), nullable=False)
    en                          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    km                          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cn                          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jp                          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kr                          : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note                        : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class STATUS_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "status"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                 = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]                 = mapped_column(String(255), nullable=False)
    translate_id                : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    description                 : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)


class AUTH_TYPE_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "auth_type"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class LANGUAGE_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "language"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    native_name                 : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order                  : Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


class CURRENCY_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "currency"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    symbol                      : Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    decimal_places              : Mapped[int]           = mapped_column(Integer, default=2, nullable=False)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)

