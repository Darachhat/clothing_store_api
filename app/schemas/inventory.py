"""Inventory schemas."""
from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


class InventoryStockOut(UUIDSchema):
    variant_id: UUID
    warehouse_id: UUID
    quantity: int
    reorder_level: int


class InventoryMovementOut(BaseSchema):
    id: UUID
    variant_id: UUID
    warehouse_id: UUID
    movement_type: str
    quantity: int
    before_quantity: int
    after_quantity: int
    reference_type: str | None
    reference_id: UUID | None
    note: str | None
    created_by: UUID | None


class StockAdjustmentCreate(BaseSchema):
    variant_id: UUID
    warehouse_id: UUID
    quantity_delta: int | None = None  # positive = add, negative = remove
    new_quantity: int | None = None    # when setting absolute stock count
    movement_type: str = "ADJUSTMENT"  # ADJUSTMENT | DAMAGE | LOST | INITIAL_STOCK
    note: str | None = None


class StockTransferItemCreate(BaseSchema):
    variant_id: UUID
    quantity: int = Field(gt=0)


class StockTransferCreate(BaseSchema):
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    items: list[StockTransferItemCreate]
    notes: str | None = None


class StockTransferItemOut(UUIDSchema):
    transfer_id: UUID
    variant_id: UUID
    quantity_requested: int
    quantity_sent: int
    quantity_received: int
    notes: str | None


class StockTransferOut(UUIDSchema):
    transfer_number: str
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    status: str
    notes: str | None
    created_by: UUID
    approved_by: UUID | None
    items: list[StockTransferItemOut] = []
