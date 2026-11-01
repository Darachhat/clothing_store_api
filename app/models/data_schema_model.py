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
from app.core.database import TEMPLATE_BASE_MODEL, UUID_BASE_MODEL

if TYPE_CHECKING:
    from app.models.base_data_schema_model import (
        Brand,
        Category,
        Color,
        ExpenseCategory,
        Permission,
        Role,
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


# ── User & RefreshToken ───────────────────────────────────────────────────────
class User(UUID_BASE_MODEL):
    __tablename__ = "users"
    __table_args__ = {"schema": "data"}

    employee_code: Mapped[str | None] = mapped_column(String(50), unique=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="SET NULL")
    )
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    branch: Mapped[Branch | None] = relationship("Branch", back_populates="users")
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="data.user_roles", back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def permission_codes(self) -> set[str]:
        return {perm.code for role in self.roles for perm in role.permissions}

    def has_permission(self, code: str) -> bool:
        return code in self.permission_codes


class RefreshToken(UUID_BASE_MODEL):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "data"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    user: Mapped[User] = relationship("User", back_populates="refresh_tokens")


# ── Branch & Warehouse ────────────────────────────────────────────────────────
class Branch(UUID_BASE_MODEL):
    __tablename__ = "branches"
    __table_args__ = {"schema": "data"}

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))

    warehouses: Mapped[list[Warehouse]] = relationship("Warehouse", back_populates="branch")
    users: Mapped[list[User]] = relationship("User", back_populates="branch")


class Warehouse(UUID_BASE_MODEL):
    __tablename__ = "warehouses"
    __table_args__ = {"schema": "data"}

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    branch: Mapped[Branch] = relationship("Branch", back_populates="warehouses")
    inventory_stocks: Mapped[list[InventoryStock]] = relationship(
        "InventoryStock", back_populates="warehouse"
    )


# ── Supplier, Product & Variant ───────────────────────────────────────────────
class Supplier(UUID_BASE_MODEL):
    __tablename__ = "suppliers"
    __table_args__ = {"schema": "data"}

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    contact_person: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)

    products: Mapped[list[Product]] = relationship("Product", back_populates="supplier")


class Product(UUID_BASE_MODEL):
    __tablename__ = "products"
    __table_args__ = {"schema": "data"}

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL")
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.brands.id", ondelete="SET NULL")
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.suppliers.id", ondelete="SET NULL")
    )
    image_url: Mapped[str | None] = mapped_column(String(500))

    category: Mapped[Category | None] = relationship("Category", back_populates="products")
    brand: Mapped[Brand | None] = relationship("Brand", back_populates="products")
    supplier: Mapped[Supplier | None] = relationship("Supplier", back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class ProductVariant(UUID_BASE_MODEL):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "color_id", "size_id", name="uq_variant_product_color_size"),
        {"schema": "data"},
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.products.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    qr_reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.colors.id", ondelete="SET NULL")
    )
    size_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.sizes.id", ondelete="SET NULL")
    )
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    wholesale_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500))

    product: Mapped[Product] = relationship("Product", back_populates="variants")
    color: Mapped[Color | None] = relationship("Color", back_populates="variants")
    size: Mapped[Size | None] = relationship("Size", back_populates="variants")
    inventory_stocks: Mapped[list[InventoryStock]] = relationship(
        "InventoryStock", back_populates="variant"
    )


class CatalogVersion(TEMPLATE_BASE_MODEL):
    __tablename__ = "catalog_versions"
    __table_args__ = {"schema": "data"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    inventory_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status_code: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    @property
    def product_version(self) -> int:
        return self.version

    @product_version.setter
    def product_version(self, val: int) -> None:
        self.version = val


# ── Inventory ─────────────────────────────────────────────────────────────────
class InventoryStock(UUID_BASE_MODEL):
    __tablename__ = "inventory_stocks"
    __table_args__ = (
        UniqueConstraint("variant_id", "warehouse_id", name="uq_stock_variant_warehouse"),
        CheckConstraint("quantity >= 0", name="ck_stock_quantity_non_negative"),
        {"schema": "data"},
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variant: Mapped[ProductVariant] = relationship("ProductVariant", back_populates="inventory_stocks")
    warehouse: Mapped[Warehouse] = relationship("Warehouse", back_populates="inventory_stocks")


class InventoryMovement(UUID_BASE_MODEL):
    __tablename__ = "inventory_movements"
    __table_args__ = {"schema": "data"}

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    before_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    after_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)

    variant: Mapped[ProductVariant] = relationship("ProductVariant")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")


class StockTransfer(UUID_BASE_MODEL):
    __tablename__ = "stock_transfers"
    __table_args__ = {"schema": "data"}

    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL")
    )
    shipped_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    from_warehouse: Mapped[Warehouse] = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped[Warehouse] = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    items: Mapped[list[StockTransferItem]] = relationship(
        "StockTransferItem", back_populates="transfer", cascade="all, delete-orphan"
    )


class StockTransferItem(UUID_BASE_MODEL):
    __tablename__ = "stock_transfer_items"
    __table_args__ = {"schema": "data"}

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    transfer: Mapped[StockTransfer] = relationship("StockTransfer", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


# ── Purchase ──────────────────────────────────────────────────────────────────
class PurchaseOrder(UUID_BASE_MODEL):
    __tablename__ = "purchase_orders"
    __table_args__ = {"schema": "data"}

    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    expected_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL")
    )

    supplier: Mapped[Supplier] = relationship("Supplier")
    branch: Mapped[Branch] = relationship("Branch")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    items: Mapped[list[PurchaseItem]] = relationship(
        "PurchaseItem", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    goods_receipts: Mapped[list[GoodsReceipt]] = relationship(
        "GoodsReceipt", back_populates="purchase_order"
    )


class PurchaseItem(UUID_BASE_MODEL):
    __tablename__ = "purchase_items"
    __table_args__ = {"schema": "data"}

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


class GoodsReceipt(UUID_BASE_MODEL):
    __tablename__ = "goods_receipts"
    __table_args__ = {"schema": "data"}

    gr_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="goods_receipts")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    items: Mapped[list[GoodsReceiptItem]] = relationship(
        "GoodsReceiptItem", back_populates="goods_receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptItem(UUID_BASE_MODEL):
    __tablename__ = "goods_receipt_items"
    __table_args__ = {"schema": "data"}

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    purchase_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.purchase_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    goods_receipt: Mapped[GoodsReceipt] = relationship("GoodsReceipt", back_populates="items")
    purchase_item: Mapped[PurchaseItem] = relationship("PurchaseItem")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


# ── Sale & Return ─────────────────────────────────────────────────────────────
class Sale(UUID_BASE_MODEL):
    __tablename__ = "sales"
    __table_args__ = {"schema": "data"}

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    sale_status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=False
    )
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.promotions.id", ondelete="SET NULL")
    )

    customer: Mapped[Customer | None] = relationship("Customer", back_populates="sales")
    branch: Mapped[Branch] = relationship("Branch")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    cashier: Mapped[User] = relationship("User")
    promotion: Mapped[Promotion | None] = relationship("Promotion")
    items: Mapped[list[SaleItem]] = relationship(
        "SaleItem", back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list[SalePayment]] = relationship(
        "SalePayment", back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
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


class SaleItem(UUID_BASE_MODEL):
    __tablename__ = "sale_items"
    __table_args__ = {"schema": "data"}

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped[Sale] = relationship("Sale", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")

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


class SalePayment(UUID_BASE_MODEL):
    __tablename__ = "sale_payments"
    __table_args__ = {"schema": "data"}

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    sale: Mapped[Sale] = relationship("Sale", back_populates="payments")


class Return(UUID_BASE_MODEL):
    __tablename__ = "returns"
    __table_args__ = {"schema": "data"}

    return_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    original_sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    return_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    total_refund: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    processed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=False
    )

    original_sale: Mapped[Sale] = relationship("Sale")
    items: Mapped[list[ReturnItem]] = relationship(
        "ReturnItem", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )
    refund_payments: Mapped[list[ReturnPayment]] = relationship(
        "ReturnPayment", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )


class ReturnItem(UUID_BASE_MODEL):
    __tablename__ = "return_items"
    __table_args__ = {"schema": "data"}

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.returns.id", ondelete="CASCADE"), nullable=False
    )
    sale_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sale_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    return_record: Mapped[Return] = relationship("Return", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


class ReturnPayment(UUID_BASE_MODEL):
    __tablename__ = "return_payments"
    __table_args__ = {"schema": "data"}

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.returns.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    return_record: Mapped[Return] = relationship("Return", back_populates="refund_payments")


# ── Customer & Loyalty ────────────────────────────────────────────────────────
class Customer(UUID_BASE_MODEL):
    __tablename__ = "customers"
    __table_args__ = {"schema": "data"}

    customer_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    sales: Mapped[list[Sale]] = relationship("Sale", back_populates="customer")
    loyalty_account: Mapped[LoyaltyAccount | None] = relationship(
        "LoyaltyAccount", back_populates="customer", uselist=False
    )


class LoyaltyAccount(UUID_BASE_MODEL):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_loyalty_customer"),
        {"schema": "data"},
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.customers.id", ondelete="CASCADE"), nullable=False
    )
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="BRONZE", nullable=False)

    customer: Mapped[Customer] = relationship("Customer", back_populates="loyalty_account")
    transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        "LoyaltyTransaction", back_populates="account", cascade="all, delete-orphan"
    )


class LoyaltyTransaction(UUID_BASE_MODEL):
    __tablename__ = "loyalty_transactions"
    __table_args__ = {"schema": "data"}

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.loyalty_accounts.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)

    account: Mapped[LoyaltyAccount] = relationship("LoyaltyAccount", back_populates="transactions")


# ── PaymentTransaction ────────────────────────────────────────────────────────
class PaymentTransaction(UUID_BASE_MODEL):
    __tablename__ = "payment_transactions"
    __table_args__ = {"schema": "data"}

    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="ABA_PAYWAY")
    tran_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.sales.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="POS")
    payment_option: Mapped[str] = mapped_column(String(30), nullable=False, default="abapay_khqr_deeplink")
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    apv: Mapped[str | None] = mapped_column(String(30))
    qr_string: Mapped[str | None] = mapped_column(Text)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_payload: Mapped[dict | None] = mapped_column(JSONB)
    last_response: Mapped[dict | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL")
    )

    sale: Mapped[Sale | None] = relationship("Sale")


# ── Expense, Promotion, AuditLog & Notification ───────────────────────────────
class Expense(UUID_BASE_MODEL):
    __tablename__ = "expenses"
    __table_args__ = {"schema": "data"}

    expense_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.expense_categories.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.branches.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(500))
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)

    category: Mapped[ExpenseCategory] = relationship("ExpenseCategory")


class Promotion(UUID_BASE_MODEL):
    __tablename__ = "promotions"
    __table_args__ = {"schema": "data"}

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    min_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("base_data.categories.id", ondelete="SET NULL")
    )
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(UUID_BASE_MODEL):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "data"}

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data.users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    old_data: Mapped[dict | None] = mapped_column(JSONB)
    new_data: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))


class NotificationSetting(UUID_BASE_MODEL):
    __tablename__ = "notification_settings"
    __table_args__ = {"schema": "data"}

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text)


# Model Aliases
USER_MODEL                 = User
REFRESH_TOKEN_MODEL        = RefreshToken
BRANCH_MODEL               = Branch
WAREHOUSE_MODEL            = Warehouse
SUPPLIER_MODEL             = Supplier
PRODUCT_MODEL              = Product
PRODUCT_VARIANT_MODEL      = ProductVariant
CATALOG_VERSION_MODEL      = CatalogVersion
INVENTORY_STOCK_MODEL      = InventoryStock
INVENTORY_MOVEMENT_MODEL   = InventoryMovement
STOCK_TRANSFER_MODEL       = StockTransfer
STOCK_TRANSFER_ITEM_MODEL  = StockTransferItem
PURCHASE_ORDER_MODEL       = PurchaseOrder
PURCHASE_ITEM_MODEL        = PurchaseItem
GOODS_RECEIPT_MODEL        = GoodsReceipt
GOODS_RECEIPT_ITEM_MODEL   = GoodsReceiptItem
SALE_MODEL                 = Sale
SALE_ITEM_MODEL            = SaleItem
SALE_PAYMENT_MODEL         = SalePayment
RETURN_MODEL               = Return
RETURN_ITEM_MODEL          = ReturnItem
RETURN_PAYMENT_MODEL       = ReturnPayment
CUSTOMER_MODEL             = Customer
LOYALTY_ACCOUNT_MODEL      = LoyaltyAccount
LOYALTY_TRANSACTION_MODEL  = LoyaltyTransaction
PAYMENT_TRANSACTION_MODEL  = PaymentTransaction
EXPENSE_MODEL              = Expense
PROMOTION_MODEL            = Promotion
AUDIT_LOG_MODEL            = AuditLog
NOTIFICATION_SETTING_MODEL = NotificationSetting

