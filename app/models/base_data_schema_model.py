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
from app.core.database import TEMPLATE_BASE_MODEL, UUID_BASE_MODEL

if TYPE_CHECKING:
    from app.models.data_schema_model import Product, ProductVariant, User


# ── Association Table: role_permissions ───────────────────────────────────────
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("base_data.roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("base_data.permissions.id", ondelete="CASCADE"), primary_key=True),
    schema="base_data",
)


# ── TRANSLATE_MODEL ───────────────────────────────────────────────────────────
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


# ── STATUS_MODEL ──────────────────────────────────────────────────────────────
class STATUS_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "status"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                 = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]                 = mapped_column(String(255), nullable=False)
    translate_id                : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    description                 : Mapped[Optional[str]]       = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                 = mapped_column(String(50), default="active", nullable=False)


# ── AUTH_TYPE_MODEL ───────────────────────────────────────────────────────────
class AUTH_TYPE_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "auth_type"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(255), nullable=False)
    description                 : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


# ── LANGUAGE_MODEL ────────────────────────────────────────────────────────────
class LANGUAGE_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "language"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    native_name                 : Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order                  : Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


# ── CURRENCY_MODEL ────────────────────────────────────────────────────────────
class CURRENCY_MODEL(TEMPLATE_BASE_MODEL):
    __tablename__               = "currency"
    __table_args__              = {"schema": "base_data"}

    id                          : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]           = mapped_column(String(10), unique=True, nullable=False)
    name                        : Mapped[str]           = mapped_column(String(100), nullable=False)
    symbol                      : Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    decimal_places              : Mapped[int]           = mapped_column(Integer, default=2, nullable=False)
    status_code                 : Mapped[str]           = mapped_column(String(10), default="active", nullable=False)


# ── Role & Permission ─────────────────────────────────────────────────────────
class Permission(UUID_BASE_MODEL):
    __tablename__ = "permissions"
    __table_args__ = {"schema": "base_data"}

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    module: Mapped[str] = mapped_column(String(100), nullable=False)

    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="base_data.role_permissions", back_populates="permissions"
    )


class Role(UUID_BASE_MODEL):
    __tablename__ = "roles"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary="base_data.role_permissions", back_populates="roles", lazy="selectin"
    )
    users: Mapped[list[User]] = relationship(
        "User", secondary="data.user_roles", back_populates="roles"
    )


# ── Product Catalog Base Lookups ──────────────────────────────────────────────
class Category(UUID_BASE_MODEL):
    __tablename__ = "categories"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    parent: Mapped[Category | None] = relationship("Category", remote_side="Category.id", back_populates="children")
    products: Mapped[list[Product]] = relationship("Product", back_populates="category")


class Brand(UUID_BASE_MODEL):
    __tablename__ = "brands"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(500))

    products: Mapped[list[Product]] = relationship("Product", back_populates="brand")


class Color(UUID_BASE_MODEL):
    __tablename__ = "colors"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hex_code: Mapped[str | None] = mapped_column(String(7))  # #RRGGBB

    variants: Mapped[list[ProductVariant]] = relationship("ProductVariant", back_populates="color")


class Size(UUID_BASE_MODEL):
    __tablename__ = "sizes"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="LETTER", nullable=False)
    # LETTER (S/M/L), NUMERIC (28/30/32), CUSTOM
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variants: Mapped[list[ProductVariant]] = relationship("ProductVariant", back_populates="size")


# ── Expense Category & Label Template ─────────────────────────────────────────
class ExpenseCategory(UUID_BASE_MODEL):
    __tablename__ = "expense_categories"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LabelTemplate(UUID_BASE_MODEL):
    __tablename__ = "label_templates"
    __table_args__ = {"schema": "base_data"}

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    width_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    height_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    template_html: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# Model Aliases
ROLE_MODEL             = Role
PERMISSION_MODEL       = Permission
CATEGORY_MODEL         = Category
BRAND_MODEL            = Brand
COLOR_MODEL            = Color
SIZE_MODEL             = Size
EXPENSE_CATEGORY_MODEL = ExpenseCategory
LABEL_TEMPLATE_MODEL   = LabelTemplate

