"""Purchase order and goods receipt schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


# ── Purchase Items ────────────────────────────────────────────────────────────
class PurchaseItemCreate(BaseSchema):
    variant_id: UUID
    quantity_ordered: int = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseItemUpdate(BaseSchema):
    quantity_ordered: int | None = Field(None, gt=0)
    unit_cost: Decimal | None = Field(None, ge=0)


class PurchaseItemOut(UUIDSchema):
    purchase_order_id: UUID
    variant_id: UUID
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal
    subtotal: Decimal


# ── Goods Receipt Items ───────────────────────────────────────────────────────
class GoodsReceiptItemCreate(BaseSchema):
    purchase_item_id: UUID
    variant_id: UUID
    quantity_received: int = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    notes: str | None = None


class GoodsReceiptItemOut(UUIDSchema):
    goods_receipt_id: UUID
    purchase_item_id: UUID
    variant_id: UUID
    quantity_received: int
    unit_cost: Decimal
    notes: str | None = None


# ── Goods Receipts ────────────────────────────────────────────────────────────
class GoodsReceiptCreate(BaseSchema):
    purchase_order_id: UUID
    warehouse_id: UUID | None = None  # defaults to PO warehouse_id if not given
    notes: str | None = None
    items: list[GoodsReceiptItemCreate]


class GoodsReceiptOut(UUIDSchema):
    gr_number: str
    purchase_order_id: UUID
    warehouse_id: UUID
    status: str
    notes: str | None = None
    received_by: UUID
    items: list[GoodsReceiptItemOut] = []


# ── Purchase Orders ───────────────────────────────────────────────────────────
class PurchaseOrderCreate(BaseSchema):
    supplier_id: UUID
    branch_id: UUID
    warehouse_id: UUID
    expected_date: date | None = None
    notes: str | None = None
    tax_amount: Decimal = Decimal("0")
    items: list[PurchaseItemCreate] = []


class PurchaseOrderUpdate(BaseSchema):
    supplier_id: UUID | None = None
    branch_id: UUID | None = None
    warehouse_id: UUID | None = None
    expected_date: date | None = None
    notes: str | None = None
    tax_amount: Decimal | None = None
    status: str | None = None


class PurchaseOrderOut(UUIDSchema):
    po_number: str
    supplier_id: UUID
    branch_id: UUID
    warehouse_id: UUID
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    expected_date: date | None = None
    notes: str | None = None
    created_by: UUID
    approved_by: UUID | None = None
    items: list[PurchaseItemOut] = []
    goods_receipts: list[GoodsReceiptOut] = []
