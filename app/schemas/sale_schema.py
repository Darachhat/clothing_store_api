"""Sale, return, and payment schemas."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import Field

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA


# ── Sale Items ────────────────────────────────────────────────────────────────

class SALE_ITEM_CREATE_SCHEMA(BaseModel):
    variant_id      : uuid.UUID
    quantity        : int                 = Field(gt=0)
    unit_price      : Optional[Decimal]   = None  # if None, use variant's selling_price
    discount_amount : Decimal             = Decimal("0")

    model_config = {"from_attributes": True}


class SALE_ITEM_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    sale_id         : uuid.UUID
    variant_id      : uuid.UUID
    sku             : Optional[str]      = None
    product_name    : Optional[str]      = None
    color_name      : Optional[str]      = None
    size_name       : Optional[str]      = None
    quantity        : int
    unit_price      : Decimal
    cost_price      : Decimal
    discount_amount : Decimal
    subtotal        : Decimal


# ── Sale Payments ─────────────────────────────────────────────────────────────

class SALE_PAYMENT_CREATE_SCHEMA(BaseModel):
    payment_method   : str  # CASH | KHQR | BANK_TRANSFER | CARD | OTHER
    amount           : Decimal       = Field(gt=0)
    reference_number : Optional[str] = None
    notes            : Optional[str] = None

    model_config = {"from_attributes": True}


class SALE_PAYMENT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    sale_id          : uuid.UUID
    payment_method   : str
    amount           : Decimal
    reference_number : Optional[str] = None
    notes            : Optional[str] = None
    status           : str           = "PAID"
    status_code      : str           = "PAID"


# ── Sales ─────────────────────────────────────────────────────────────────────

class SALE_CREATE_SCHEMA(BaseModel):
    branch_id       : Optional[uuid.UUID]            = None
    warehouse_id    : Optional[uuid.UUID]            = None
    terminal_id     : Optional[uuid.UUID]            = None
    customer_id     : Optional[uuid.UUID]            = None
    items           : List[SALE_ITEM_CREATE_SCHEMA]
    discount_amount : Decimal                        = Decimal("0")
    tax_amount      : Decimal                        = Decimal("0")
    notes           : Optional[str]                  = None
    promotion_id    : Optional[uuid.UUID]            = None
    payments        : Optional[List[SALE_PAYMENT_CREATE_SCHEMA]] = None

    model_config = {"from_attributes": True}


class SALE_COMPLETE_SCHEMA(BaseModel):
    payments : List[SALE_PAYMENT_CREATE_SCHEMA]

    model_config = {"from_attributes": True}


SALE_COMPLETE_REQUEST_SCHEMA = SALE_COMPLETE_SCHEMA


class SALE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    invoice_number  : str
    customer_id     : Optional[uuid.UUID]               = None
    customer_name   : Optional[str]                     = None
    branch_id       : uuid.UUID
    branch_name     : Optional[str]                     = None
    warehouse_id    : uuid.UUID
    subtotal        : Decimal
    discount_amount : Decimal
    tax_amount      : Decimal
    total           : Decimal
    payment_status  : str
    sale_status     : str
    notes           : Optional[str]                     = None
    cashier_id      : uuid.UUID
    cashier_name    : Optional[str]                     = None
    terminal_id     : Optional[uuid.UUID]               = None
    terminal_code   : Optional[str]                     = None
    promotion_id    : Optional[uuid.UUID]               = None
    items           : List[SALE_ITEM_RESPONSE_SCHEMA]    = []
    payments        : List[SALE_PAYMENT_RESPONSE_SCHEMA] = []


# ── Returns ───────────────────────────────────────────────────────────────────

class RETURN_ITEM_CREATE_SCHEMA(BaseModel):
    sale_item_id : uuid.UUID
    quantity     : int       = Field(gt=0)

    model_config = {"from_attributes": True}


class RETURN_PAYMENT_CREATE_SCHEMA(BaseModel):
    payment_method : str
    amount         : Decimal = Field(gt=0)

    model_config = {"from_attributes": True}


class RETURN_CREATE_SCHEMA(BaseModel):
    original_sale_id : uuid.UUID
    return_type      : str                                  = "PARTIAL"  # FULL | PARTIAL | EXCHANGE
    reason           : Optional[str]                        = None
    items            : List[RETURN_ITEM_CREATE_SCHEMA]
    refund_payments  : List[RETURN_PAYMENT_CREATE_SCHEMA]   = []

    model_config = {"from_attributes": True}


RETURN_CREATE_REQUEST_SCHEMA = RETURN_CREATE_SCHEMA


class RETURN_CREATE_FOR_SALE_SCHEMA(BaseModel):
    original_sale_id : Optional[uuid.UUID]                  = None
    return_type      : str                                  = "PARTIAL"
    reason           : Optional[str]                        = None
    items            : List[RETURN_ITEM_CREATE_SCHEMA]
    refund_payments  : List[RETURN_PAYMENT_CREATE_SCHEMA]   = []

    model_config = {"from_attributes": True}


class RETURN_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    return_number    : str
    original_sale_id : uuid.UUID
    customer_id      : Optional[uuid.UUID] = None
    branch_id        : uuid.UUID
    return_type      : str
    reason           : Optional[str]       = None
    total_refund     : Decimal
    status           : str                 = "COMPLETED"
    status_code      : str                 = "COMPLETED"
    processed_by     : uuid.UUID


__all__ = [
    "SALE_ITEM_CREATE_SCHEMA",
    "SALE_ITEM_RESPONSE_SCHEMA",
    "SALE_PAYMENT_CREATE_SCHEMA",
    "SALE_PAYMENT_RESPONSE_SCHEMA",
    "SALE_CREATE_SCHEMA",
    "SALE_COMPLETE_SCHEMA",
    "SALE_COMPLETE_REQUEST_SCHEMA",
    "SALE_RESPONSE_SCHEMA",
    "RETURN_ITEM_CREATE_SCHEMA",
    "RETURN_PAYMENT_CREATE_SCHEMA",
    "RETURN_CREATE_SCHEMA",
    "RETURN_CREATE_REQUEST_SCHEMA",
    "RETURN_CREATE_FOR_SALE_SCHEMA",
    "RETURN_RESPONSE_SCHEMA",
]
