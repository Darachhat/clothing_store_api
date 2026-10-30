"""Customer and Loyalty Pydantic schemas."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import BaseSchema, PaginatedResponse, UUIDSchema


class LoyaltyTransactionSchema(UUIDSchema):
    account_id: UUID
    transaction_type: str
    points: int
    reference_type: str | None = None
    reference_id: UUID | None = None
    note: str | None = None


class LoyaltyAccountSchema(UUIDSchema):
    customer_id: UUID
    points_balance: int = 0
    total_points_earned: int = 0
    total_points_redeemed: int = 0
    tier: str = "BRONZE"


class CustomerBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    status: str = "ACTIVE"


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseSchema):
    name: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=50)
    email: EmailStr | None = None
    address: str | None = None
    date_of_birth: date | None = None
    notes: str | None = None
    status: str | None = None


class CustomerResponse(CustomerBase, UUIDSchema):
    customer_code: str
    loyalty_account: LoyaltyAccountSchema | None = None


class CustomerListResponse(PaginatedResponse):
    items: list[CustomerResponse]


class AdjustPointsRequest(BaseModel):
    points: int
    note: str | None = None
