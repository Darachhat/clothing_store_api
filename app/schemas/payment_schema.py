"""Payment schemas following system_log_schema.py template."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import Field

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA


class PAYMENT_KHQR_CREATE_REQUEST_SCHEMA(BaseModel):
    sale_id : uuid.UUID

    model_config = {"from_attributes": True}


class PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA(BaseModel):
    sale_id        : uuid.UUID
    payment_option : str       = Field(default="cards", max_length=50)

    model_config = {"from_attributes": True}


class PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA(BaseModel):
    action_url : str
    script_url : str
    form_data  : Dict[str, str]
    payment_id : uuid.UUID
    tran_id    : str
    amount     : float
    currency   : str

    model_config = {"from_attributes": True}


class PAYMENT_TRANSACTION_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    tran_id      : str
    sale_id      : Optional[uuid.UUID] = None
    status       : str                 = "PENDING"
    status_code  : str                 = "PENDING"
    amount       : float
    currency     : str                 = "USD"
    qr_string    : Optional[str]       = None
    qr_image     : Optional[str]       = None
    checkout_url : Optional[str]       = None
    apv          : Optional[str]       = None
    expires_at   : Optional[Any]       = None
    paid_at      : Optional[Any]       = None

    model_config = {"from_attributes": True, "extra": "allow"}


class PAYMENT_TRANSACTION_LIST_OUT_SCHEMA(BaseModel):
    items : List[PAYMENT_TRANSACTION_RESPONSE_SCHEMA]
    total : int
    page  : Optional[int]                           = 1
    size  : Optional[int]                           = 50


__all__ = [
    "PAYMENT_KHQR_CREATE_REQUEST_SCHEMA",
    "PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA",
    "PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA",
    "PAYMENT_TRANSACTION_RESPONSE_SCHEMA",
    "PAYMENT_TRANSACTION_LIST_OUT_SCHEMA",
]
