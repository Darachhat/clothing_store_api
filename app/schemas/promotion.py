"""Promotion schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


class PromotionCreate(BaseSchema):
    name: str
    type: str  # PERCENTAGE | FIXED | COUPON | CATEGORY | PRODUCT
    value: Decimal = Field(gt=0)
    code: str | None = None
    min_purchase_amount: Decimal = Decimal("0")
    max_discount_amount: Decimal | None = None
    usage_limit: int | None = None
    applies_to: str = "ALL"  # ALL | CATEGORY | PRODUCT
    category_id: UUID | None = None
    start_datetime: datetime
    end_datetime: datetime
    status: str = "ACTIVE"


class PromotionUpdate(BaseSchema):
    name: str | None = None
    type: str | None = None
    value: Decimal | None = Field(None, gt=0)
    code: str | None = None
    min_purchase_amount: Decimal | None = None
    max_discount_amount: Decimal | None = None
    usage_limit: int | None = None
    applies_to: str | None = None
    category_id: UUID | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    status: str | None = None


class PromotionOut(UUIDSchema):
    name: str
    type: str
    value: Decimal
    code: str | None
    min_purchase_amount: Decimal
    max_discount_amount: Decimal | None
    usage_limit: int | None
    usage_count: int
    applies_to: str
    category_id: UUID | None
    start_datetime: datetime
    end_datetime: datetime
    status: str


class CouponValidationRequest(BaseSchema):
    code: str
    cart_total: Decimal = Field(gt=0)


class CouponValidationResponse(BaseSchema):
    valid: bool
    discount_amount: Decimal = Decimal("0")
    message: str
    promotion: PromotionOut | None = None
