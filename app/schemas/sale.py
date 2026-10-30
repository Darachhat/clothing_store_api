"""Sale, return, and payment schemas."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


class SaleItemCreate(BaseSchema):
    variant_id: UUID
    quantity: int = Field(gt=0)
    unit_price: Decimal | None = None  # if None, use variant's selling_price
    discount_amount: Decimal = Decimal("0")


class SaleItemOut(UUIDSchema):
    sale_id: UUID
    variant_id: UUID
    sku: str | None = None
    product_name: str | None = None
    color_name: str | None = None
    size_name: str | None = None
    quantity: int
    unit_price: Decimal
    cost_price: Decimal
    discount_amount: Decimal
    subtotal: Decimal


class SalePaymentCreate(BaseSchema):
    payment_method: str  # CASH | KHQR | BANK_TRANSFER | CARD | OTHER
    amount: Decimal = Field(gt=0)
    reference_number: str | None = None
    notes: str | None = None


class SalePaymentOut(UUIDSchema):
    sale_id: UUID
    payment_method: str
    amount: Decimal
    reference_number: str | None
    notes: str | None


class SaleCreate(BaseSchema):
    branch_id: UUID | None = None
    warehouse_id: UUID | None = None
    customer_id: UUID | None = None
    items: list[SaleItemCreate]
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    notes: str | None = None
    promotion_id: UUID | None = None


class SaleComplete(BaseSchema):
    payments: list[SalePaymentCreate]


class SaleOut(UUIDSchema):
    invoice_number: str
    customer_id: UUID | None
    customer_name: str | None = None
    branch_id: UUID
    branch_name: str | None = None
    warehouse_id: UUID
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    payment_status: str
    sale_status: str
    notes: str | None
    cashier_id: UUID
    cashier_name: str | None = None
    promotion_id: UUID | None
    items: list[SaleItemOut] = []
    payments: list[SalePaymentOut] = []


# ── Returns ───────────────────────────────────────────────────────────────────
class ReturnItemCreate(BaseSchema):
    sale_item_id: UUID
    quantity: int = Field(gt=0)


class ReturnPaymentCreate(BaseSchema):
    payment_method: str
    amount: Decimal = Field(gt=0)


class ReturnCreate(BaseSchema):
    original_sale_id: UUID
    return_type: str  # FULL | PARTIAL | EXCHANGE
    reason: str | None = None
    items: list[ReturnItemCreate]
    refund_payments: list[ReturnPaymentCreate] = []


class ReturnOut(UUIDSchema):
    return_number: str
    original_sale_id: UUID
    customer_id: UUID | None
    branch_id: UUID
    return_type: str
    reason: str | None
    total_refund: Decimal
    status: str
    processed_by: UUID
