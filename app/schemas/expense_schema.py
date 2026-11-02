"""Expense and ExpenseCategory schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import Field, field_validator

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA, BASE_STATUS_UPDATE_SCHEMA


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


class EXPENSE_CATEGORY_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    name        : str
    code        : str
    description : Optional[str] = None
    is_system   : bool          = False


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


class EXPENSE_UPDATE_SCHEMA(BASE_STATUS_UPDATE_SCHEMA):
    category_id    : Optional[uuid.UUID] = None
    branch_id      : Optional[uuid.UUID] = None
    amount         : Optional[Decimal]   = Field(default=None, gt=0)
    payment_method : Optional[str]       = None
    expense_date   : Optional[date]      = None
    description    : Optional[str]       = None
    receipt_url    : Optional[str]       = None
    notes          : Optional[str]       = None


class EXPENSE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    expense_number : str
    category_id    : uuid.UUID
    branch_id      : uuid.UUID
    amount         : Decimal
    description    : Optional[str]                              = None
    payment_method : str
    receipt_url    : Optional[str]                              = None
    expense_date   : date
    created_by     : Optional[Any]                              = None
    approved_by    : Optional[Any]                              = None
    notes          : Optional[str]                              = None
    category       : Optional[EXPENSE_CATEGORY_RESPONSE_SCHEMA] = None


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
