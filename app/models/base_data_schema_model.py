"""
Base Data Schema Models: lookup, reference, and catalog base models.
Schema: base_data
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.database import BASE_MODEL, UUID_BASE_MODEL

if TYPE_CHECKING:
    from app.models.data_schema_model import (
        PRODUCT_MODEL,
        PRODUCT_VARIANT_MODEL,
        Product,
        ProductVariant,
        USER_MODEL,
        User,
    )


# ── Association Table: role_permissions ───────────────────────────────────────
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("base_data.roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("base_data.permissions.id", ondelete="CASCADE"), primary_key=True),
    schema="base_data",
)


# ── TRANSLATE_MODEL ───────────────────────────────────────────────────────────
class TRANSLATE_MODEL(BASE_MODEL):
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
    status_code                 : Mapped[str]           = mapped_column(String(10), default="ACTIVE", nullable=False)


# ── STATUS_MODEL ──────────────────────────────────────────────────────────────
class STATUS_MODEL(BASE_MODEL):
    __tablename__               = "status"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                 = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]                 = mapped_column(String(255), nullable=False)
    translate_id                : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    description                 : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                 = mapped_column(String(50), default="ACTIVE", nullable=False)


# ── AUTH_TYPE_MODEL ───────────────────────────────────────────────────────────
class AUTH_TYPE_MODEL(BASE_MODEL):
    __tablename__               = "auth_type"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="ACTIVE", nullable=False)


# ── LANGUAGE_MODEL ────────────────────────────────────────────────────────────
class LANGUAGE_MODEL(BASE_MODEL):
    __tablename__               = "language"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    native_name                 : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order                  : Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="ACTIVE", nullable=False)


# ── CURRENCY_MODEL ────────────────────────────────────────────────────────────
class CURRENCY_MODEL(BASE_MODEL):
    __tablename__               = "currency"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    symbol                      : Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    decimal_places              : Mapped[int]           = mapped_column(Integer, default=2, nullable=False)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="ACTIVE", nullable=False)


# ── PERMISSION_MODEL ──────────────────────────────────────────────────────────
class PERMISSION_MODEL(BASE_MODEL):
    __tablename__               = "permissions"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False, index=True)
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    module                      : Mapped[str]                       = mapped_column(String(100), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    roles                       : Mapped[list[ROLE_MODEL]]          = relationship(
        "ROLE_MODEL", secondary="base_data.role_permissions", back_populates="permissions"
    )


# ── ROLE_MODEL ────────────────────────────────────────────────────────────────
class ROLE_MODEL(BASE_MODEL):
    __tablename__               = "roles"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False)
    description                 : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    is_system                   : Mapped[bool]                      = mapped_column(Boolean, default=False, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    permissions                 : Mapped[list[PERMISSION_MODEL]]    = relationship(
        "PERMISSION_MODEL", secondary="base_data.role_permissions", back_populates="roles", lazy="selectin"
    )
    users                       : Mapped[list[USER_MODEL]]          = relationship(
        "USER_MODEL", secondary="data.user_roles", back_populates="roles"
    )


# ── CATEGORY_MODEL ────────────────────────────────────────────────────────────
class CATEGORY_MODEL(BASE_MODEL):
    __tablename__               = "categories"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(200), unique=True, nullable=False)
    slug                        : Mapped[str]                       = mapped_column(String(200), unique=True, nullable=False, index=True)
    parent_id                   : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL"), nullable=True
    )
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    sort_order                  : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    children                    : Mapped[list[CATEGORY_MODEL]]      = relationship("CATEGORY_MODEL", back_populates="parent")
    parent                      : Mapped[Optional[CATEGORY_MODEL]]  = relationship("CATEGORY_MODEL", remote_side="CATEGORY_MODEL.id", back_populates="children")
    products                    : Mapped[list[PRODUCT_MODEL]]       = relationship("PRODUCT_MODEL", back_populates="category")


# ── BRAND_MODEL ───────────────────────────────────────────────────────────────
class BRAND_MODEL(BASE_MODEL):
    __tablename__               = "brands"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(200), unique=True, nullable=False)
    slug                        : Mapped[str]                       = mapped_column(String(200), unique=True, nullable=False, index=True)
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    logo_url                    : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    products                    : Mapped[list[PRODUCT_MODEL]]       = relationship("PRODUCT_MODEL", back_populates="brand")


# ── COLOR_MODEL ───────────────────────────────────────────────────────────────
class COLOR_MODEL(BASE_MODEL):
    __tablename__               = "colors"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False)
    hex_code                    : Mapped[Optional[str]]             = mapped_column(String(7), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    variants                    : Mapped[list[PRODUCT_VARIANT_MODEL]] = relationship("PRODUCT_VARIANT_MODEL", back_populates="color")


# ── SIZE_MODEL ────────────────────────────────────────────────────────────────
class SIZE_MODEL(BASE_MODEL):
    __tablename__               = "sizes"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(50), nullable=False)
    type                        : Mapped[str]                       = mapped_column(String(20), default="LETTER", nullable=False)
    sort_order                  : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    variants                    : Mapped[list[PRODUCT_VARIANT_MODEL]] = relationship("PRODUCT_VARIANT_MODEL", back_populates="size")


# ── EXPENSE_CATEGORY_MODEL ────────────────────────────────────────────────────
class EXPENSE_CATEGORY_MODEL(BASE_MODEL):
    __tablename__               = "expense_categories"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False)
    code                        : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    is_system                   : Mapped[bool]                      = mapped_column(Boolean, default=False, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)


# ── LABEL_TEMPLATE_MODEL ──────────────────────────────────────────────────────
class LABEL_TEMPLATE_MODEL(BASE_MODEL):
    __tablename__               = "label_templates"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False)
    description                 : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    width_mm                    : Mapped[int]                       = mapped_column(Integer, nullable=False)
    height_mm                   : Mapped[int]                       = mapped_column(Integer, nullable=False)
    template_html               : Mapped[str]                       = mapped_column(Text, nullable=False)
    is_default                  : Mapped[bool]                      = mapped_column(Boolean, default=False, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)
