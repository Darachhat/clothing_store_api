"""Expense and ExpenseCategory schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class EXPENSE_CATEGORY_CREATE_SCHEMA(BaseModel):
    name        : str
    code        : str
    description : Optional[str] = None
    status_code : str           = "ACTIVE"

    model_config = {"from_attributes": True}


class EXPENSE_CATEGORY_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str] = None
    description : Optional[str] = None
    status_code : Optional[str] = None

    model_config = {"from_attributes": True}


class EXPENSE_CATEGORY_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    code             : str
    description      : Optional[str]      = None
    is_system        : bool               = False
    status           : str                = "ACTIVE"
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class EXPENSE_CREATE_SCHEMA(BaseModel):
    category_id    : uuid.UUID
    branch_id      : Optional[uuid.UUID] = None
    amount         : Decimal             = Field(gt=0)
    payment_method : str                 = "CASH"
    expense_date   : date
    description    : Optional[str]       = None
    receipt_url    : Optional[str]       = None
    notes          : Optional[str]       = None
    status_code    : str                 = "ACTIVE"

    model_config = {"from_attributes": True}

    @field_validator("branch_id", mode="before")
    @classmethod
    def _normalize_nil_branch(cls, v: Any) -> Any:
        if v is None or str(v) == "00000000-0000-0000-0000-000000000000" or str(v).strip() == "":
            return None
        return v


class EXPENSE_UPDATE_SCHEMA(BaseModel):
    category_id    : Optional[uuid.UUID] = None
    branch_id      : Optional[uuid.UUID] = None
    amount         : Optional[Decimal]   = Field(default=None, gt=0)
    payment_method : Optional[str]       = None
    expense_date   : Optional[date]      = None
    description    : Optional[str]       = None
    receipt_url    : Optional[str]       = None
    notes          : Optional[str]       = None
    status         : Optional[str]       = None
    status_code    : Optional[str]       = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


class EXPENSE_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    expense_number   : str
    category_id      : uuid.UUID
    branch_id        : uuid.UUID
    amount           : Decimal
    description      : Optional[str]                               = None
    payment_method   : str
    receipt_url      : Optional[str]                               = None
    expense_date     : date
    created_by       : Optional[Any]                               = None
    approved_by      : Optional[Any]                               = None
    status           : str                                         = "ACTIVE"
    status_code      : str                                         = "ACTIVE"
    notes            : Optional[str]                               = None
    category         : Optional[EXPENSE_CATEGORY_RESPONSE_SCHEMA]  = None
    created_datetime : Optional[datetime]                          = None
    updated_datetime : Optional[datetime]                          = None
    created_at       : Optional[datetime]                          = None
    updated_at       : Optional[datetime]                          = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class EXPENSE_LIST_OUT_SCHEMA(BaseModel):
    items : List[EXPENSE_RESPONSE_SCHEMA]
    total : int
    skip  : Optional[int] = 0
    limit : Optional[int] = 50
    page  : Optional[int] = 1
    size  : Optional[int] = 50


__all__ = [
    "EXPENSE_CATEGORY_CREATE_SCHEMA",
    "EXPENSE_CATEGORY_UPDATE_SCHEMA",
    "EXPENSE_CATEGORY_RESPONSE_SCHEMA",
    "EXPENSE_CREATE_SCHEMA",
    "EXPENSE_UPDATE_SCHEMA",
    "EXPENSE_RESPONSE_SCHEMA",
    "EXPENSE_LIST_OUT_SCHEMA",
]

