"""Sale, SaleItem, SalePayment models."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.branch import Branch, Warehouse
    from app.models.customer import Customer
    from app.models.product import ProductVariant
    from app.models.promotion import Promotion
    from app.models.user import User


class Sale(UUIDBase):
    __tablename__ = "sales"

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    # PENDING | PARTIAL | PAID | REFUNDED
    sale_status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    # DRAFT | COMPLETED | CANCELLED | RETURNED
    notes: Mapped[str | None] = mapped_column(Text)
    cashier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("promotions.id", ondelete="SET NULL")
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


class SaleItem(UUIDBase):
    __tablename__ = "sale_items"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
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


class SalePayment(UUIDBase):
    __tablename__ = "sale_payments"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    # CASH | KHQR | BANK_TRANSFER | CARD | OTHER
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    sale: Mapped[Sale] = relationship("Sale", back_populates="payments")


class Return(UUIDBase):
    __tablename__ = "returns"

    return_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    original_sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    return_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # FULL | PARTIAL | EXCHANGE
    reason: Mapped[str | None] = mapped_column(Text)
    total_refund: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    processed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    original_sale: Mapped[Sale] = relationship("Sale")
    items: Mapped[list[ReturnItem]] = relationship(
        "ReturnItem", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )
    refund_payments: Mapped[list[ReturnPayment]] = relationship(
        "ReturnPayment", back_populates="return_record", cascade="all, delete-orphan", lazy="selectin"
    )


class ReturnItem(UUIDBase):
    __tablename__ = "return_items"

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("returns.id", ondelete="CASCADE"), nullable=False
    )
    sale_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    return_record: Mapped[Return] = relationship("Return", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


class ReturnPayment(UUIDBase):
    __tablename__ = "return_payments"

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("returns.id", ondelete="CASCADE"), nullable=False
    )
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    return_record: Mapped[Return] = relationship("Return", back_populates="refund_payments")
