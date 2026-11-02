"""Customer and Loyalty Pydantic schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field, model_validator


class LOYALTY_TRANSACTION_RESPONSE_SCHEMA(BaseModel):
    id                 : uuid.UUID
    account_id         : uuid.UUID
    transaction_type   : str
    points             : int
    reference_type     : Optional[str]       = None
    reference_id       : Optional[uuid.UUID] = None
    note               : Optional[str]       = None
    status_code        : str                 = "ACTIVE"
    created_datetime   : Optional[datetime]  = None
    updated_datetime   : Optional[datetime]  = None
    created_at         : Optional[datetime]  = None
    updated_at         : Optional[datetime]  = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class LOYALTY_ACCOUNT_RESPONSE_SCHEMA(BaseModel):
    id                    : uuid.UUID
    customer_id           : uuid.UUID
    points_balance        : int                                       = 0
    total_points_earned   : int                                       = 0
    total_points_redeemed : int                                       = 0
    tier                  : str                                       = "BRONZE"
    status_code           : str                                       = "ACTIVE"
    created_datetime      : Optional[datetime]                        = None
    updated_datetime      : Optional[datetime]                        = None
    created_at            : Optional[datetime]                        = None
    updated_at            : Optional[datetime]                        = None
    transactions          : List[LOYALTY_TRANSACTION_RESPONSE_SCHEMA]  = []

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


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


class CUSTOMER_RESPONSE_SCHEMA(CUSTOMER_BASE_SCHEMA):
    id               : uuid.UUID
    customer_code    : str
    created_datetime : Optional[datetime]                        = None
    updated_datetime : Optional[datetime]                        = None
    created_at       : Optional[datetime]                        = None
    updated_at       : Optional[datetime]                        = None
    loyalty_account  : Optional[LOYALTY_ACCOUNT_RESPONSE_SCHEMA] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class CUSTOMER_LIST_OUT_SCHEMA(BaseModel):
    items : List[CUSTOMER_RESPONSE_SCHEMA]
    total : int
    skip  : Optional[int] = 0
    limit : Optional[int] = 50
    page  : Optional[int] = 1
    size  : Optional[int] = 50


class ADJUST_POINTS_REQUEST_SCHEMA(BaseModel):
    points         : int
    note           : Optional[str]       = None
    reference_type : Optional[str]       = None
    reference_id   : Optional[uuid.UUID] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_loyalty_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if out.get("points") is None and out.get("points_delta") is not None:
            out["points"] = int(out["points_delta"])
        if out.get("note") is None and out.get("reason") is not None:
            out["note"] = str(out["reason"])
        return out


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


