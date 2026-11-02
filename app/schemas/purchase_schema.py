"""Purchase order and goods receipt schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import Field

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA, BASE_STATUS_UPDATE_SCHEMA


# ── Purchase Items ────────────────────────────────────────────────────────────

class PURCHASE_ITEM_CREATE_SCHEMA(BaseModel):
    variant_id       : uuid.UUID
    quantity_ordered : int        = Field(gt=0)
    unit_cost        : Decimal    = Field(ge=0)

    model_config = {"from_attributes": True}


class PURCHASE_ITEM_UPDATE_SCHEMA(BaseModel):
    quantity_ordered : Optional[int]     = Field(default=None, gt=0)
    unit_cost        : Optional[Decimal] = Field(default=None, ge=0)

    model_config = {"from_attributes": True}


class PURCHASE_ITEM_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    purchase_order_id : uuid.UUID
    variant_id        : uuid.UUID
    quantity_ordered  : int
    quantity_received : int
    unit_cost         : Decimal
    subtotal          : Decimal


# ── Goods Receipt Items ───────────────────────────────────────────────────────

class GOODS_RECEIPT_ITEM_CREATE_SCHEMA(BaseModel):
    purchase_item_id  : Optional[uuid.UUID] = None
    variant_id        : uuid.UUID
    quantity_received : int                 = Field(gt=0)
    unit_cost         : Optional[Decimal]   = Field(default=None, ge=0)
    notes             : Optional[str]       = None

    model_config = {"from_attributes": True}


class GOODS_RECEIPT_ITEM_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    goods_receipt_id  : uuid.UUID
    purchase_item_id  : uuid.UUID
    variant_id        : uuid.UUID
    quantity_received : int
    unit_cost         : Decimal
    notes             : Optional[str] = None


# ── Goods Receipts ────────────────────────────────────────────────────────────

class GOODS_RECEIPT_CREATE_SCHEMA(BaseModel):
    purchase_order_id : uuid.UUID
    warehouse_id      : Optional[uuid.UUID]                    = None
    notes             : Optional[str]                          = None
    note              : Optional[str]                          = None
    items             : List[GOODS_RECEIPT_ITEM_CREATE_SCHEMA]

    model_config = {"from_attributes": True}


class GOODS_RECEIPT_CREATE_FOR_ORDER_SCHEMA(BaseModel):
    purchase_order_id : Optional[uuid.UUID]                    = None
    warehouse_id      : Optional[uuid.UUID]                    = None
    notes             : Optional[str]                          = None
    note              : Optional[str]                          = None
    items             : List[GOODS_RECEIPT_ITEM_CREATE_SCHEMA]

    model_config = {"from_attributes": True}


class GOODS_RECEIPT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    gr_number         : str
    purchase_order_id : uuid.UUID
    warehouse_id      : uuid.UUID
    status            : str                                       = "RECEIVED"
    status_code       : str                                       = "RECEIVED"
    notes             : Optional[str]                             = None
    received_by       : uuid.UUID
    items             : List[GOODS_RECEIPT_ITEM_RESPONSE_SCHEMA]  = []


# ── Purchase Orders ───────────────────────────────────────────────────────────

class PURCHASE_ORDER_CREATE_SCHEMA(BaseModel):
    supplier_id   : uuid.UUID
    branch_id     : Optional[uuid.UUID]               = None
    warehouse_id  : Optional[uuid.UUID]               = None
    expected_date : Optional[date]                    = None
    notes         : Optional[str]                     = None
    tax_amount    : Decimal                           = Decimal("0")
    items         : List[PURCHASE_ITEM_CREATE_SCHEMA] = []

    model_config = {"from_attributes": True}


class PURCHASE_ORDER_UPDATE_SCHEMA(BASE_STATUS_UPDATE_SCHEMA):
    supplier_id   : Optional[uuid.UUID] = None
    branch_id     : Optional[uuid.UUID] = None
    warehouse_id  : Optional[uuid.UUID] = None
    expected_date : Optional[date]      = None
    notes         : Optional[str]       = None
    tax_amount    : Optional[Decimal]   = None


class PURCHASE_ORDER_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    po_number      : str
    supplier_id    : uuid.UUID
    branch_id      : uuid.UUID
    warehouse_id   : uuid.UUID
    status         : str                                  = "ORDERED"
    status_code    : str                                  = "ORDERED"
    subtotal       : Decimal
    tax_amount     : Decimal
    total          : Decimal
    expected_date  : Optional[date]                       = None
    notes          : Optional[str]                        = None
    created_by     : Optional[Any]                        = None
    approved_by    : Optional[Any]                        = None
    items          : List[PURCHASE_ITEM_RESPONSE_SCHEMA]  = []
    goods_receipts : List[GOODS_RECEIPT_RESPONSE_SCHEMA] = []


__all__ = [
    "PURCHASE_ITEM_CREATE_SCHEMA",
    "PURCHASE_ITEM_UPDATE_SCHEMA",
    "PURCHASE_ITEM_RESPONSE_SCHEMA",
    "GOODS_RECEIPT_ITEM_CREATE_SCHEMA",
    "GOODS_RECEIPT_ITEM_RESPONSE_SCHEMA",
    "GOODS_RECEIPT_CREATE_SCHEMA",
    "GOODS_RECEIPT_CREATE_FOR_ORDER_SCHEMA",
    "GOODS_RECEIPT_RESPONSE_SCHEMA",
    "PURCHASE_ORDER_CREATE_SCHEMA",
    "PURCHASE_ORDER_UPDATE_SCHEMA",
    "PURCHASE_ORDER_RESPONSE_SCHEMA",
]
