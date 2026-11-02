"""Customer and Loyalty Pydantic schemas."""
from __future__ import annotations

from datetime import date
from typing import Any, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import AliasChoices, EmailStr, Field, model_validator

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA, BASE_TIMESTAMP_RESPONSE_SCHEMA


class LOYALTY_TRANSACTION_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    account_id         : uuid.UUID
    transaction_type   : str
    points             : int
    reference_type     : Optional[str]       = None
    reference_id       : Optional[uuid.UUID] = None
    note               : Optional[str]       = None


class LOYALTY_ACCOUNT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    customer_id           : uuid.UUID
    points_balance        : int                                       = 0
    total_points_earned   : int                                       = 0
    total_points_redeemed : int                                       = 0
    tier                  : str                                       = "BRONZE"
    transactions          : List[LOYALTY_TRANSACTION_RESPONSE_SCHEMA]  = []


class CUSTOMER_BASE_SCHEMA(BaseModel):
    name          : str                = Field(..., min_length=1, max_length=200)
    phone         : Optional[str]      = Field(default=None, max_length=50)
    email         : Optional[EmailStr] = None
    address       : Optional[str]      = None
    date_of_birth : Optional[date]     = None
    notes         : Optional[str]      = None
    status        : str                = "ACTIVE"
    status_code   : str                = "ACTIVE"

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


class CUSTOMER_CREATE_SCHEMA(CUSTOMER_BASE_SCHEMA):
    pass


class CUSTOMER_UPDATE_SCHEMA(BaseModel):
    name          : Optional[str]      = Field(default=None, min_length=1, max_length=200)
    phone         : Optional[str]      = Field(default=None, max_length=50)
    email         : Optional[EmailStr] = None
    address       : Optional[str]      = None
    date_of_birth : Optional[date]     = None
    notes         : Optional[str]      = None
    status        : Optional[str]      = None
    status_code   : Optional[str]      = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _normalize_status(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "status" in data and "status_code" not in data:
                data["status_code"] = data["status"]
            elif "status_code" in data and "status" not in data:
                data["status"] = data["status_code"]
        return data


class CUSTOMER_RESPONSE_SCHEMA(CUSTOMER_BASE_SCHEMA, BASE_TIMESTAMP_RESPONSE_SCHEMA):
    id               : uuid.UUID
    customer_code    : str
    loyalty_account  : Optional[LOYALTY_ACCOUNT_RESPONSE_SCHEMA] = None


class CUSTOMER_LIST_OUT_SCHEMA(BaseModel):
    items : List[CUSTOMER_RESPONSE_SCHEMA]
    total : int
    skip  : Optional[int] = 0
    limit : Optional[int] = 50
    page  : Optional[int] = 1
    size  : Optional[int] = 50


class ADJUST_POINTS_REQUEST_SCHEMA(BaseModel):
    points         : int                 = Field(..., validation_alias=AliasChoices("points", "points_delta"))
    note           : Optional[str]       = Field(default=None, validation_alias=AliasChoices("note", "reason"))
    reference_type : Optional[str]       = None
    reference_id   : Optional[uuid.UUID] = None


LOYALTY_ADJUST_REQUEST_SCHEMA = ADJUST_POINTS_REQUEST_SCHEMA


class LOYALTY_AWARD_REQUEST_SCHEMA(BaseModel):
    customer_id    : uuid.UUID
    points         : int
    sale_id        : uuid.UUID
    invoice_number : str

    model_config = {"from_attributes": True}


class LOYALTY_CLAWBACK_REQUEST_SCHEMA(BaseModel):
    customer_id    : uuid.UUID
    points         : int
    reference_type : str
    reference_id   : uuid.UUID
    note           : str

    model_config = {"from_attributes": True}


__all__ = [
    "LOYALTY_TRANSACTION_RESPONSE_SCHEMA",
    "LOYALTY_ACCOUNT_RESPONSE_SCHEMA",
    "CUSTOMER_BASE_SCHEMA",
    "CUSTOMER_CREATE_SCHEMA",
    "CUSTOMER_UPDATE_SCHEMA",
    "CUSTOMER_RESPONSE_SCHEMA",
    "CUSTOMER_LIST_OUT_SCHEMA",
    "ADJUST_POINTS_REQUEST_SCHEMA",
    "LOYALTY_ADJUST_REQUEST_SCHEMA",
    "LOYALTY_AWARD_REQUEST_SCHEMA",
    "LOYALTY_CLAWBACK_REQUEST_SCHEMA",
]
