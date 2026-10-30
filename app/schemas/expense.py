"""Expense and ExpenseCategory schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


class ExpenseCategoryCreate(BaseSchema):
    name: str
    code: str
    description: str | None = None


class ExpenseCategoryUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None


class ExpenseCategoryOut(UUIDSchema):
    name: str
    code: str
    description: str | None
    is_system: bool


class ExpenseCreate(BaseSchema):
    category_id: UUID
    branch_id: UUID
    amount: Decimal = Field(gt=0)
    payment_method: str = "CASH"
    expense_date: date
    description: str | None = None
    receipt_url: str | None = None
    notes: str | None = None


class ExpenseUpdate(BaseSchema):
    category_id: UUID | None = None
    branch_id: UUID | None = None
    amount: Decimal | None = Field(None, gt=0)
    payment_method: str | None = None
    expense_date: date | None = None
    description: str | None = None
    receipt_url: str | None = None
    notes: str | None = None
    status: str | None = None


class ExpenseOut(UUIDSchema):
    expense_number: str
    category_id: UUID
    branch_id: UUID
    amount: Decimal
    description: str | None
    payment_method: str
    receipt_url: str | None
    expense_date: date
    created_by: UUID
    approved_by: UUID | None
    status: str
    notes: str | None
    category: ExpenseCategoryOut | None = None
