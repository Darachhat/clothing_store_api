"""
Data Schema Models: business entity, transactional, and operational records.
Schema: data
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.database import BASE_MODEL

if TYPE_CHECKING:
    from app.models.base_data_schema_model import (
        BRAND_MODEL,
        Brand,
        CATEGORY_MODEL,
        Category,
        COLOR_MODEL,
        Color,
        EXPENSE_CATEGORY_MODEL,
        ExpenseCategory,
        PERMISSION_MODEL,
        Permission,
        ROLE_MODEL,
        Role,
        SIZE_MODEL,
        Size,
    )


# ── Association Table: user_roles ─────────────────────────────────────────────
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("base_data.roles.id", ondelete="CASCADE"), primary_key=True),
    schema="data",
)


# ── USER_MODEL ────────────────────────────────────────────────────────────────
class USER_MODEL(BASE_MODEL):
    __tablename__               = "users"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_code               : Mapped[Optional[str]]             = mapped_column(String(50), unique=True, nullable=True)
    username                    : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False, index=True)
    email                       : Mapped[str]                       = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name                   : Mapped[str]                       = mapped_column(String(200), nullable=False)
    hashed_password             : Mapped[str]                       = mapped_column(String(255), nullable=False)
    branch_id                   : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="SET NULL"), nullable=True
    )
    last_login_at               : Mapped[Optional[datetime]]        = mapped_column(DateTime(timezone=True), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    branch                      : Mapped[Optional[BRANCH_MODEL]]    = relationship("BRANCH_MODEL", back_populates="users")
    roles                       : Mapped[list[ROLE_MODEL]]          = relationship(
        "ROLE_MODEL", secondary="data.user_roles", back_populates="users", lazy="selectin"
    )
    refresh_tokens              : Mapped[list[REFRESH_TOKEN_MODEL]] = relationship(
        "REFRESH_TOKEN_MODEL", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def permission_codes(self) -> set[str]:
        return {perm.code for role in self.roles for perm in role.permissions}

    def has_permission(self, code: str) -> bool:
        return code in self.permission_codes


# ── REFRESH_TOKEN_MODEL ───────────────────────────────────────────────────────
class REFRESH_TOKEN_MODEL(BASE_MODEL):
    __tablename__               = "refresh_tokens"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                     : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash                  : Mapped[str]                       = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at                  : Mapped[datetime]                  = mapped_column(DateTime(timezone=True), nullable=False)
    revoked                     : Mapped[bool]                      = mapped_column(Boolean, default=False, nullable=False)
    ip_address                  : Mapped[Optional[str]]             = mapped_column(String(45), nullable=True)
    user_agent                  : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    user                        : Mapped[USER_MODEL]                = relationship("USER_MODEL", back_populates="refresh_tokens")


# ── BRANCH_MODEL ──────────────────────────────────────────────────────────────
class BRANCH_MODEL(BASE_MODEL):
    __tablename__               = "branches"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    address                     : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    phone                       : Mapped[Optional[str]]             = mapped_column(String(50), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    warehouses                  : Mapped[list[WAREHOUSE_MODEL]]     = relationship("WAREHOUSE_MODEL", back_populates="branch")
    users                       : Mapped[list[USER_MODEL]]          = relationship("USER_MODEL", back_populates="branch")


# ── WAREHOUSE_MODEL ───────────────────────────────────────────────────────────
class WAREHOUSE_MODEL(BASE_MODEL):
    __tablename__               = "warehouses"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    address                     : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    is_default                  : Mapped[bool]                      = mapped_column(Boolean, default=False, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    branch                      : Mapped[BRANCH_MODEL]              = relationship("BRANCH_MODEL", back_populates="warehouses")
    inventory_stocks            : Mapped[list[INVENTORY_STOCK_MODEL]] = relationship(
        "INVENTORY_STOCK_MODEL", back_populates="warehouse"
    )


# ── SUPPLIER_MODEL ────────────────────────────────────────────────────────────
class SUPPLIER_MODEL(BASE_MODEL):
    __tablename__               = "suppliers"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    phone                       : Mapped[Optional[str]]             = mapped_column(String(50), nullable=True)
    email                       : Mapped[Optional[str]]             = mapped_column(String(255), nullable=True)
    address                     : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    contact_person              : Mapped[Optional[str]]             = mapped_column(String(200), nullable=True)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    products                    : Mapped[list[PRODUCT_MODEL]]       = relationship("PRODUCT_MODEL", back_populates="supplier")


# ── PRODUCT_MODEL ─────────────────────────────────────────────────────────────
class PRODUCT_MODEL(BASE_MODEL):
    __tablename__               = "products"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code                        : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False, index=True)
    name                        : Mapped[str]                       = mapped_column(String(300), nullable=False)
    slug                        : Mapped[str]                       = mapped_column(String(300), unique=True, nullable=False, index=True)
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    category_id                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL"), nullable=True
    )
    brand_id                    : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.brands.id", ondelete="SET NULL"), nullable=True
    )
    supplier_id                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.suppliers.id", ondelete="SET NULL"), nullable=True
    )
    image_url                   : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    category                    : Mapped[Optional[CATEGORY_MODEL]]  = relationship("CATEGORY_MODEL", back_populates="products")
    brand                       : Mapped[Optional[BRAND_MODEL]]     = relationship("BRAND_MODEL", back_populates="products")
    supplier                    : Mapped[Optional[SUPPLIER_MODEL]]  = relationship("SUPPLIER_MODEL", back_populates="products")
    variants                    : Mapped[list[PRODUCT_VARIANT_MODEL]] = relationship(
        "PRODUCT_VARIANT_MODEL", back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


# ── PRODUCT_VARIANT_MODEL ─────────────────────────────────────────────────────
class PRODUCT_VARIANT_MODEL(BASE_MODEL):
    __tablename__               = "product_variants"
    __table_args__              = (
        UniqueConstraint("product_id", "color_id", "size_id", name="uq_variant_product_color_size"),
        {"schema": "data"},
    )

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.products.id", ondelete="CASCADE"), nullable=False
    )
    sku                         : Mapped[str]                       = mapped_column(String(200), unique=True, nullable=False, index=True)
    barcode                     : Mapped[Optional[str]]             = mapped_column(String(200), unique=True, index=True, nullable=True)
    qr_reference                : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False, index=True)
    color_id                    : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.colors.id", ondelete="SET NULL"), nullable=True
    )
    size_id                     : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.sizes.id", ondelete="SET NULL"), nullable=True
    )
    cost_price                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    selling_price               : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    wholesale_price             : Mapped[Optional[Decimal]]         = mapped_column(Numeric(12, 2), nullable=True)
    weight_grams                : Mapped[Optional[int]]             = mapped_column(Integer, nullable=True)
    image_url                   : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    product                     : Mapped[PRODUCT_MODEL]             = relationship("PRODUCT_MODEL", back_populates="variants")
    color                       : Mapped[Optional[COLOR_MODEL]]     = relationship("COLOR_MODEL", back_populates="variants")
    size                        : Mapped[Optional[SIZE_MODEL]]      = relationship("SIZE_MODEL", back_populates="variants")
    inventory_stocks            : Mapped[list[INVENTORY_STOCK_MODEL]] = relationship(
        "INVENTORY_STOCK_MODEL", back_populates="variant"
    )


# ── CATALOG_VERSION_MODEL ─────────────────────────────────────────────────────
class CATALOG_VERSION_MODEL(BASE_MODEL):
    __tablename__               = "catalog_versions"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[int]                       = mapped_column(Integer, primary_key=True, default=1)
    version                     : Mapped[int]                       = mapped_column(Integer, default=1, nullable=False)
    inventory_version           : Mapped[int]                       = mapped_column(Integer, default=1, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    @property
    def product_version(self) -> int:
        return self.version

    @product_version.setter
    def product_version(self, val: int) -> None:
        self.version = val


# ── INVENTORY_STOCK_MODEL ─────────────────────────────────────────────────────
class INVENTORY_STOCK_MODEL(BASE_MODEL):
    __tablename__               = "inventory_stocks"
    __table_args__              = (
        UniqueConstraint("variant_id", "warehouse_id", name="uq_stock_variant_warehouse"),
        CheckConstraint("quantity >= 0", name="ck_stock_quantity_non_negative"),
        {"schema": "data"},
    )

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="CASCADE"), nullable=False
    )
    quantity                    : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    reorder_level               : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL", back_populates="inventory_stocks")
    warehouse                   : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL", back_populates="inventory_stocks")


# ── INVENTORY_MOVEMENT_MODEL ──────────────────────────────────────────────────
class INVENTORY_MOVEMENT_MODEL(BASE_MODEL):
    __tablename__               = "inventory_movements"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type               : Mapped[str]                       = mapped_column(String(30), nullable=False, index=True)
    quantity                    : Mapped[int]                       = mapped_column(Integer, nullable=False)
    before_quantity             : Mapped[int]                       = mapped_column(Integer, nullable=False)
    after_quantity              : Mapped[int]                       = mapped_column(Integer, nullable=False)
    reference_type              : Mapped[Optional[str]]             = mapped_column(String(50), nullable=True)
    reference_id                : Mapped[Optional[uuid.UUID]]       = mapped_column(UUID(as_uuid=True), nullable=True)
    note                        : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")
    warehouse                   : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL")


# ── STOCK_TRANSFER_MODEL ──────────────────────────────────────────────────────
class STOCK_TRANSFER_MODEL(BASE_MODEL):
    __tablename__               = "stock_transfers"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_number             : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    from_warehouse_id           : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    to_warehouse_id             : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    created_by_user_id          : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL"), nullable=True
    )
    shipped_at                  : Mapped[Optional[datetime]]        = mapped_column(DateTime(timezone=True), nullable=True)
    received_at                 : Mapped[Optional[datetime]]        = mapped_column(DateTime(timezone=True), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    from_warehouse              : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL", foreign_keys=[from_warehouse_id])
    to_warehouse                : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL", foreign_keys=[to_warehouse_id])
    items                       : Mapped[list[STOCK_TRANSFER_ITEM_MODEL]] = relationship(
        "STOCK_TRANSFER_ITEM_MODEL", back_populates="transfer", cascade="all, delete-orphan"
    )


# ── STOCK_TRANSFER_ITEM_MODEL ─────────────────────────────────────────────────
class STOCK_TRANSFER_ITEM_MODEL(BASE_MODEL):
    __tablename__               = "stock_transfer_items"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_id                 : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_requested          : Mapped[int]                       = mapped_column(Integer, nullable=False)
    quantity_sent               : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    quantity_received           : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    transfer                    : Mapped[STOCK_TRANSFER_MODEL]      = relationship("STOCK_TRANSFER_MODEL", back_populates="items")
    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")


# ── PURCHASE_ORDER_MODEL ──────────────────────────────────────────────────────
class PURCHASE_ORDER_MODEL(BASE_MODEL):
    __tablename__               = "purchase_orders"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_number                   : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    supplier_id                 : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    subtotal                    : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_amount                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total                       : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False, default=0)
    expected_date               : Mapped[Optional[date]]            = mapped_column(Date, nullable=True)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    created_by_user_id          : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL"), nullable=True
    )
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    supplier                    : Mapped[SUPPLIER_MODEL]            = relationship("SUPPLIER_MODEL")
    branch                      : Mapped[BRANCH_MODEL]              = relationship("BRANCH_MODEL")
    warehouse                   : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL")
    items                       : Mapped[list[PURCHASE_ITEM_MODEL]] = relationship(
        "PURCHASE_ITEM_MODEL", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    goods_receipts              : Mapped[list[GOODS_RECEIPT_MODEL]] = relationship(
        "GOODS_RECEIPT_MODEL", back_populates="purchase_order"
    )


# ── PURCHASE_ITEM_MODEL ───────────────────────────────────────────────────────
class PURCHASE_ITEM_MODEL(BASE_MODEL):
    __tablename__               = "purchase_items"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purchase_order_id           : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ordered            : Mapped[int]                       = mapped_column(Integer, nullable=False)
    quantity_received           : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    unit_cost                   : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    subtotal                    : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    purchase_order              : Mapped[PURCHASE_ORDER_MODEL]      = relationship("PURCHASE_ORDER_MODEL", back_populates="items")
    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")


# ── GOODS_RECEIPT_MODEL ───────────────────────────────────────────────────────
class GOODS_RECEIPT_MODEL(BASE_MODEL):
    __tablename__               = "goods_receipts"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gr_number                   : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    purchase_order_id           : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    received_by                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    purchase_order              : Mapped[PURCHASE_ORDER_MODEL]      = relationship("PURCHASE_ORDER_MODEL", back_populates="goods_receipts")
    warehouse                   : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL")
    items                       : Mapped[list[GOODS_RECEIPT_ITEM_MODEL]] = relationship(
        "GOODS_RECEIPT_ITEM_MODEL", back_populates="goods_receipt", cascade="all, delete-orphan"
    )


# ── GOODS_RECEIPT_ITEM_MODEL ──────────────────────────────────────────────────
class GOODS_RECEIPT_ITEM_MODEL(BASE_MODEL):
    __tablename__               = "goods_receipt_items"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goods_receipt_id            : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    purchase_item_id            : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_received           : Mapped[int]                       = mapped_column(Integer, nullable=False)
    unit_cost                   : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    goods_receipt               : Mapped[GOODS_RECEIPT_MODEL]       = relationship("GOODS_RECEIPT_MODEL", back_populates="items")
    purchase_item               : Mapped[PURCHASE_ITEM_MODEL]       = relationship("PURCHASE_ITEM_MODEL")
    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")


# ── SALE_MODEL ────────────────────────────────────────────────────────────────
class SALE_MODEL(BASE_MODEL):
    __tablename__               = "sales"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number              : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="SET NULL"), nullable=True
    )
    branch_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    subtotal                    : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount             : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total                       : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    payment_status              : Mapped[str]                       = mapped_column(String(20), default="PENDING", nullable=False)
    sale_status                 : Mapped[str]                       = mapped_column(String(20), default="DRAFT", nullable=False)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    cashier_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=False
    )
    promotion_id                : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.promotions.id", ondelete="SET NULL"), nullable=True
    )
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    customer                    : Mapped[Optional[CUSTOMER_MODEL]]  = relationship("CUSTOMER_MODEL", back_populates="sales")
    branch                      : Mapped[BRANCH_MODEL]              = relationship("BRANCH_MODEL")
    warehouse                   : Mapped[WAREHOUSE_MODEL]           = relationship("WAREHOUSE_MODEL")
    cashier                     : Mapped[USER_MODEL]                = relationship("USER_MODEL")
    promotion                   : Mapped[Optional[PROMOTION_MODEL]] = relationship("PROMOTION_MODEL")
    items                       : Mapped[list[SALE_ITEM_MODEL]]     = relationship(
        "SALE_ITEM_MODEL", back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )
    payments                    : Mapped[list[SALE_PAYMENT_MODEL]]  = relationship(
        "SALE_PAYMENT_MODEL", back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def customer_name(self) -> str | None:
        cust = self.__dict__.get("customer")
        return getattr(cust, "name", None) if cust is not None else None

    @property
    def branch_name(self) -> str | None:
        br = self.__dict__.get("branch")
        return getattr(br, "name", None) if br is not None else None

    @property
    def cashier_name(self) -> str | None:
        cs = self.__dict__.get("cashier")
        if cs is None:
            return None
        return getattr(cs, "full_name", None) or getattr(cs, "username", None)


# ── SALE_ITEM_MODEL ───────────────────────────────────────────────────────────
class SALE_ITEM_MODEL(BASE_MODEL):
    __tablename__               = "sale_items"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id                     : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="CASCADE"), nullable=False
    )
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity                    : Mapped[int]                       = mapped_column(Integer, nullable=False)
    unit_price                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    cost_price                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount             : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), default=0, nullable=False)
    subtotal                    : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    sale                        : Mapped[SALE_MODEL]                = relationship("SALE_MODEL", back_populates="items")
    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")

    @property
    def sku(self) -> str | None:
        v = self.__dict__.get("variant")
        return getattr(v, "sku", None) if v is not None else None

    @property
    def product_name(self) -> str | None:
        v = self.__dict__.get("variant")
        if v is None:
            return None
        p = v.__dict__.get("product")
        return getattr(p, "name", None) if p is not None else None

    @property
    def color_name(self) -> str | None:
        v = self.__dict__.get("variant")
        if v is None:
            return None
        c = v.__dict__.get("color")
        return getattr(c, "name", None) if c is not None else None

    @property
    def size_name(self) -> str | None:
        v = self.__dict__.get("variant")
        if v is None:
            return None
        s = v.__dict__.get("size")
        return getattr(s, "name", None) if s is not None else None


# ── SALE_PAYMENT_MODEL ────────────────────────────────────────────────────────
class SALE_PAYMENT_MODEL(BASE_MODEL):
    __tablename__               = "sale_payments"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id                     : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="CASCADE"), nullable=False
    )
    payment_method              : Mapped[str]                       = mapped_column(String(30), nullable=False)
    amount                      : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    reference_number            : Mapped[Optional[str]]             = mapped_column(String(100), nullable=True)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    sale                        : Mapped[SALE_MODEL]                = relationship("SALE_MODEL", back_populates="payments")


# ── RETURN_MODEL ──────────────────────────────────────────────────────────────
class RETURN_MODEL(BASE_MODEL):
    __tablename__               = "returns"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_number               : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    original_sale_id            : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="SET NULL"), nullable=True
    )
    branch_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    return_type                 : Mapped[str]                       = mapped_column(String(20), nullable=False)
    reason                      : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    total_refund                : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    processed_by                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=False
    )
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    original_sale               : Mapped[SALE_MODEL]                = relationship("SALE_MODEL")
    items                       : Mapped[list[RETURN_ITEM_MODEL]]   = relationship(
        "RETURN_ITEM_MODEL", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )
    refund_payments             : Mapped[list[RETURN_PAYMENT_MODEL]] = relationship(
        "RETURN_PAYMENT_MODEL", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )


# ── RETURN_ITEM_MODEL ─────────────────────────────────────────────────────────
class RETURN_ITEM_MODEL(BASE_MODEL):
    __tablename__               = "return_items"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.returns.id", ondelete="CASCADE"), nullable=False
    )
    sale_item_id                : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sale_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity                    : Mapped[int]                       = mapped_column(Integer, nullable=False)
    unit_price                  : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    subtotal                    : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    return_record               : Mapped[RETURN_MODEL]              = relationship("RETURN_MODEL", back_populates="items")
    variant                     : Mapped[PRODUCT_VARIANT_MODEL]     = relationship("PRODUCT_VARIANT_MODEL")


# ── RETURN_PAYMENT_MODEL ──────────────────────────────────────────────────────
class RETURN_PAYMENT_MODEL(BASE_MODEL):
    __tablename__               = "return_payments"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.returns.id", ondelete="CASCADE"), nullable=False
    )
    payment_method              : Mapped[str]                       = mapped_column(String(30), nullable=False)
    amount                      : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    return_record               : Mapped[RETURN_MODEL]              = relationship("RETURN_MODEL", back_populates="refund_payments")


# ── CUSTOMER_MODEL ────────────────────────────────────────────────────────────
class CUSTOMER_MODEL(BASE_MODEL):
    __tablename__               = "customers"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_code               : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False, index=True)
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    phone                       : Mapped[Optional[str]]             = mapped_column(String(50), index=True, nullable=True)
    email                       : Mapped[Optional[str]]             = mapped_column(String(255), index=True, nullable=True)
    address                     : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    date_of_birth               : Mapped[Optional[date]]            = mapped_column(Date, nullable=True)
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    sales                       : Mapped[list[SALE_MODEL]]          = relationship("SALE_MODEL", back_populates="customer")
    loyalty_account             : Mapped[Optional[LOYALTY_ACCOUNT_MODEL]] = relationship(
        "LOYALTY_ACCOUNT_MODEL", back_populates="customer", uselist=False
    )


# ── LOYALTY_ACCOUNT_MODEL ─────────────────────────────────────────────────────
class LOYALTY_ACCOUNT_MODEL(BASE_MODEL):
    __tablename__               = "loyalty_accounts"
    __table_args__              = (
        UniqueConstraint("customer_id", name="uq_loyalty_customer"),
        {"schema": "data"},
    )

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id                 : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="CASCADE"), nullable=False
    )
    points_balance              : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    total_points_earned         : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    total_points_redeemed       : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    tier                        : Mapped[str]                       = mapped_column(String(20), default="BRONZE", nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    customer                    : Mapped[CUSTOMER_MODEL]            = relationship("CUSTOMER_MODEL", back_populates="loyalty_account")
    transactions                : Mapped[list[LOYALTY_TRANSACTION_MODEL]] = relationship(
        "LOYALTY_TRANSACTION_MODEL", back_populates="account", cascade="all, delete-orphan"
    )


# ── LOYALTY_TRANSACTION_MODEL ─────────────────────────────────────────────────
class LOYALTY_TRANSACTION_MODEL(BASE_MODEL):
    __tablename__               = "loyalty_transactions"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id                  : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.loyalty_accounts.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type            : Mapped[str]                       = mapped_column(String(20), nullable=False)
    points                      : Mapped[int]                       = mapped_column(Integer, nullable=False)
    reference_type              : Mapped[Optional[str]]             = mapped_column(String(50), nullable=True)
    reference_id                : Mapped[Optional[uuid.UUID]]       = mapped_column(UUID(as_uuid=True), nullable=True)
    note                        : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    account                     : Mapped[LOYALTY_ACCOUNT_MODEL]     = relationship("LOYALTY_ACCOUNT_MODEL", back_populates="transactions")


# ── PAYMENT_TRANSACTION_MODEL ─────────────────────────────────────────────────
class PAYMENT_TRANSACTION_MODEL(BASE_MODEL):
    __tablename__               = "payment_transactions"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider                    : Mapped[str]                       = mapped_column(String(30), nullable=False, default="ABA_PAYWAY")
    tran_id                     : Mapped[str]                       = mapped_column(String(20), unique=True, nullable=False, index=True)
    sale_id                     : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="SET NULL"), index=True, nullable=True
    )
    channel                     : Mapped[str]                       = mapped_column(String(10), nullable=False, default="POS")
    payment_option              : Mapped[str]                       = mapped_column(String(30), nullable=False, default="abapay_khqr_deeplink")
    amount                      : Mapped[float]                     = mapped_column(Numeric(12, 2), nullable=False)
    currency                    : Mapped[str]                       = mapped_column(String(3), nullable=False, default="USD")
    apv                         : Mapped[Optional[str]]             = mapped_column(String(30), nullable=True)
    qr_string                   : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    checkout_url                : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    expires_at                  : Mapped[Optional[datetime]]        = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at                     : Mapped[Optional[datetime]]        = mapped_column(DateTime(timezone=True), nullable=True)
    request_payload             : Mapped[Optional[dict]]            = mapped_column(JSONB, nullable=True)
    last_response               : Mapped[Optional[dict]]            = mapped_column(JSONB, nullable=True)
    created_by_user_id          : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL"), nullable=True
    )
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    sale                        : Mapped[Optional[SALE_MODEL]]      = relationship("SALE_MODEL")


# ── EXPENSE_MODEL ─────────────────────────────────────────────────────────────
class EXPENSE_MODEL(BASE_MODEL):
    __tablename__               = "expenses"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_number              : Mapped[str]                       = mapped_column(String(50), unique=True, nullable=False)
    category_id                 : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.expense_categories.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id                   : Mapped[uuid.UUID]                 = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    amount                      : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    payment_method              : Mapped[str]                       = mapped_column(String(30), nullable=False)
    receipt_url                 : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    expense_date                : Mapped[date]                      = mapped_column(Date, nullable=False)
    created_by_user_id          : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL"), nullable=True
    )
    notes                       : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)

    category                    : Mapped[EXPENSE_CATEGORY_MODEL]    = relationship("EXPENSE_CATEGORY_MODEL")


# ── PROMOTION_MODEL ───────────────────────────────────────────────────────────
class PROMOTION_MODEL(BASE_MODEL):
    __tablename__               = "promotions"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                        : Mapped[str]                       = mapped_column(String(200), nullable=False)
    type                        : Mapped[str]                       = mapped_column(String(30), nullable=False)
    value                       : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), nullable=False)
    code                        : Mapped[Optional[str]]             = mapped_column(String(100), unique=True, index=True, nullable=True)
    min_purchase_amount         : Mapped[Decimal]                   = mapped_column(Numeric(12, 2), default=0, nullable=False)
    max_discount_amount         : Mapped[Optional[Decimal]]         = mapped_column(Numeric(12, 2), nullable=True)
    usage_limit                 : Mapped[Optional[int]]             = mapped_column(Integer, nullable=True)
    usage_count                 : Mapped[int]                       = mapped_column(Integer, default=0, nullable=False)
    applies_to                  : Mapped[str]                       = mapped_column(String(20), default="ALL", nullable=False)
    category_id                 : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL"), nullable=True
    )
    start_datetime              : Mapped[datetime]                  = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime                : Mapped[datetime]                  = mapped_column(DateTime(timezone=True), nullable=False)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)


# ── AUDIT_LOG_MODEL ───────────────────────────────────────────────────────────
class AUDIT_LOG_MODEL(BASE_MODEL):
    __tablename__               = "audit_logs"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id                     : Mapped[Optional[uuid.UUID]]       = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL"), nullable=True
    )
    action                      : Mapped[str]                       = mapped_column(String(50), nullable=False, index=True)
    entity_type                 : Mapped[Optional[str]]             = mapped_column(String(100), nullable=True)
    entity_id                   : Mapped[Optional[uuid.UUID]]       = mapped_column(UUID(as_uuid=True), nullable=True)
    old_data                    : Mapped[Optional[dict]]            = mapped_column(JSONB, nullable=True)
    new_data                    : Mapped[Optional[dict]]            = mapped_column(JSONB, nullable=True)
    ip_address                  : Mapped[Optional[str]]             = mapped_column(String(45), nullable=True)
    user_agent                  : Mapped[Optional[str]]             = mapped_column(String(500), nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)


# ── NOTIFICATION_SETTING_MODEL ────────────────────────────────────────────────
class NOTIFICATION_SETTING_MODEL(BASE_MODEL):
    __tablename__               = "notification_settings"
    __table_args__              = {"schema": "data"}

    id                          : Mapped[uuid.UUID]                 = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key                         : Mapped[str]                       = mapped_column(String(100), unique=True, nullable=False)
    value                       : Mapped[dict]                      = mapped_column(JSONB, nullable=False, default=dict)
    description                 : Mapped[Optional[str]]             = mapped_column(Text, nullable=True)
    status_code                 : Mapped[str]                       = mapped_column(String(50), default="ACTIVE", nullable=False)
