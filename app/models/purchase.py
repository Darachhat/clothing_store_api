"""Purchase Order, PurchaseItem, GoodsReceipt, GoodsReceiptItem models."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.branch import Branch, Warehouse
    from app.models.product import ProductVariant, Supplier
    from app.models.user import User


class PurchaseOrder(UUIDBase):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    # DRAFT | ORDERED | PARTIAL | RECEIVED | CANCELLED
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    expected_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    supplier: Mapped[Supplier] = relationship("Supplier")
    branch: Mapped[Branch] = relationship("Branch")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    approver: Mapped[User | None] = relationship("User", foreign_keys=[approved_by])
    items: Mapped[list[PurchaseItem]] = relationship(
        "PurchaseItem", back_populates="purchase_order", cascade="all, delete-orphan"
    )
    goods_receipts: Mapped[list[GoodsReceipt]] = relationship(
        "GoodsReceipt", back_populates="purchase_order"
    )


class PurchaseItem(UUIDBase):
    __tablename__ = "purchase_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")


class GoodsReceipt(UUIDBase):
    __tablename__ = "goods_receipts"

    gr_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    received_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="goods_receipts")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    items: Mapped[list[GoodsReceiptItem]] = relationship(
        "GoodsReceiptItem", back_populates="goods_receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptItem(UUIDBase):
    __tablename__ = "goods_receipt_items"

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    purchase_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_items.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    goods_receipt: Mapped[GoodsReceipt] = relationship("GoodsReceipt", back_populates="items")
    purchase_item: Mapped[PurchaseItem] = relationship("PurchaseItem")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")
