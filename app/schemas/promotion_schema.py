"""Promotion schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


def _normalize_promo_payload(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    out = dict(data)
    if out.get("type") is None and out.get("discount_type") is not None:
        out["type"] = out["discount_type"]
    if out.get("value") is None and out.get("discount_value") is not None:
        out["value"] = out["discount_value"]
    if out.get("start_datetime") is None and out.get("start_date") is not None:
        out["start_datetime"] = out["start_date"]
    if out.get("end_datetime") is None and out.get("end_date") is not None:
        out["end_datetime"] = out["end_date"]
    if out.get("status_code") is None:
        if out.get("status") is not None:
            out["status_code"] = out["status"]
        elif "is_active" in out and out["is_active"] is not None:
            out["status_code"] = "ACTIVE" if bool(out["is_active"]) else "INACTIVE"
    return out


class PROMOTION_CREATE_SCHEMA(BaseModel):
    name                : str
    type                : str  # PERCENTAGE | FIXED | COUPON | CATEGORY | PRODUCT
    value               : Decimal             = Field(gt=0)
    code                : Optional[str]       = None
    min_purchase_amount : Decimal             = Decimal("0")
    max_discount_amount : Optional[Decimal]   = None
    usage_limit         : Optional[int]       = None
    applies_to          : str                 = "ALL"  # ALL | CATEGORY | PRODUCT
    category_id         : Optional[uuid.UUID] = None
    start_datetime      : datetime
    end_datetime        : datetime
    status              : str                 = "ACTIVE"
    status_code         : str                 = "ACTIVE"

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_create(cls, data: Any) -> Any:
        return _normalize_promo_payload(data)

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


class PROMOTION_UPDATE_SCHEMA(BaseModel):
    name                : Optional[str]       = None
    type                : Optional[str]       = None
    value               : Optional[Decimal]   = Field(default=None, gt=0)
    code                : Optional[str]       = None
    min_purchase_amount : Optional[Decimal]   = None
    max_discount_amount : Optional[Decimal]   = None
    usage_limit         : Optional[int]       = None
    applies_to          : Optional[str]       = None
    category_id         : Optional[uuid.UUID] = None
    start_datetime      : Optional[datetime]  = None
    end_datetime        : Optional[datetime]  = None
    status              : Optional[str]       = None
    status_code         : Optional[str]       = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_update(cls, data: Any) -> Any:
        return _normalize_promo_payload(data)

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


class PROMOTION_RESPONSE_SCHEMA(BaseModel):
    id                  : uuid.UUID
    name                : str
    type                : str
    value               : Decimal
    code                : Optional[str]       = None
    min_purchase_amount : Decimal             = Decimal("0")
    max_discount_amount : Optional[Decimal]   = None
    usage_limit         : Optional[int]       = None
    usage_count         : int                 = 0
    applies_to          : str                 = "ALL"
    category_id         : Optional[uuid.UUID] = None
    start_datetime      : datetime
    end_datetime        : datetime
    status              : str                 = "ACTIVE"
    status_code         : str                 = "ACTIVE"
    created_datetime    : Optional[datetime]  = None
    updated_datetime    : Optional[datetime]  = None
    created_at          : Optional[datetime]  = None
    updated_at          : Optional[datetime]  = None

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


class COUPON_VALIDATION_REQUEST_SCHEMA(BaseModel):
    code       : str
    cart_total : Decimal = Field(gt=0)


class COUPON_VALIDATION_RESPONSE_SCHEMA(BaseModel):
    valid           : bool
    discount_amount : Decimal                              = Decimal("0")
    message         : str
    promotion       : Optional[PROMOTION_RESPONSE_SCHEMA]  = None


class PROMOTION_LIST_OUT_SCHEMA(BaseModel):
    items : List[PROMOTION_RESPONSE_SCHEMA]
    total : int
    skip  : Optional[int] = 0
    limit : Optional[int] = 50
    page  : Optional[int] = 1
    size  : Optional[int] = 50


__all__ = [
    "PROMOTION_CREATE_SCHEMA",
    "PROMOTION_UPDATE_SCHEMA",
    "PROMOTION_RESPONSE_SCHEMA",
    "COUPON_VALIDATION_REQUEST_SCHEMA",
    "COUPON_VALIDATION_RESPONSE_SCHEMA",
    "PROMOTION_LIST_OUT_SCHEMA",
]

