"""Payment schemas following system_log_schema.py template."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


class PAYMENT_KHQR_CREATE_REQUEST_SCHEMA(BaseModel):
    sale_id : uuid.UUID

    model_config = {"from_attributes": True}


class PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA(BaseModel):
    sale_id        : uuid.UUID
    payment_option : str       = Field(default="cards", max_length=50)

    model_config = {"from_attributes": True}


class PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA(BaseModel):
    action_url : str
    form_data  : Dict[str, str]
    payment_id : uuid.UUID
    tran_id    : str
    amount     : float
    currency   : str

    model_config = {"from_attributes": True}


class PAYMENT_TRANSACTION_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    tran_id          : str
    sale_id          : Optional[uuid.UUID]      = None
    status           : str                      = "PENDING"
    status_code      : str                      = "PENDING"
    amount           : float
    currency         : str                      = "USD"
    qr_string        : Optional[str]            = None
    qr_image         : Optional[str]            = None
    checkout_url     : Optional[str]            = None
    apv              : Optional[str]            = None
    expires_at       : Optional[Any]            = None
    paid_at          : Optional[Any]            = None
    created_datetime : Optional[datetime]       = None
    updated_datetime : Optional[datetime]       = None

    model_config = {"from_attributes": True, "extra": "allow"}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


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

