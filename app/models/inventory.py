"""Inventory models: InventoryStock, InventoryMovement, StockTransfer, StockTransferItem."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.branch import Warehouse
    from app.models.product import ProductVariant
    from app.models.user import User


class InventoryStock(UUIDBase):
    """Current stock level per variant per warehouse (denormalized snapshot)."""

    __tablename__ = "inventory_stocks"
    __table_args__ = (
        UniqueConstraint("variant_id", "warehouse_id", name="uq_stock_variant_warehouse"),
        CheckConstraint("quantity >= 0", name="ck_stock_quantity_non_negative"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variant: Mapped[ProductVariant] = relationship("ProductVariant", back_populates="inventory_stocks")
    warehouse: Mapped[Warehouse] = relationship("Warehouse", back_populates="inventory_stocks")


class InventoryMovement(Base):
    """Immutable ledger of every stock change."""

    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # PURCHASE | SALE | RETURN | ADJUSTMENT | TRANSFER_IN | TRANSFER_OUT | DAMAGE | LOST | INITIAL_STOCK
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # can be negative
    before_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    after_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))  # sale, purchase_receipt, transfer, adjustment
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    from sqlalchemy import DateTime as SADateTime
    from sqlalchemy import func
    created_at: Mapped[DateTime] = mapped_column(
        SADateTime(timezone=True), server_default=func.now(), nullable=False
    )

    variant: Mapped[ProductVariant] = relationship("ProductVariant")
    warehouse: Mapped[Warehouse] = relationship("Warehouse")
    creator: Mapped[User | None] = relationship("User")


class StockTransfer(UUIDBase):
    __tablename__ = "stock_transfers"

    transfer_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    # DRAFT | PENDING | IN_TRANSIT | RECEIVED | CANCELLED
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    shipped_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))

    from_warehouse: Mapped[Warehouse] = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped[Warehouse] = relationship("Warehouse", foreign_keys=[to_warehouse_id])
    items: Mapped[list[StockTransferItem]] = relationship(
        "StockTransferItem", back_populates="transfer", cascade="all, delete-orphan"
    )


class StockTransferItem(UUIDBase):
    __tablename__ = "stock_transfer_items"

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_transfers.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    transfer: Mapped[StockTransfer] = relationship("StockTransfer", back_populates="items")
    variant: Mapped[ProductVariant] = relationship("ProductVariant")
