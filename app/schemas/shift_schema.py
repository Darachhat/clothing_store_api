"""Cashier Shift & Drawer Float Schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic.main import BaseModel
from pydantic import Field


class SHIFT_OPEN_SCHEMA(BaseModel):
    terminal_id       : uuid.UUID
    opening_float_usd : Decimal       = Field(default=Decimal("0.00"), ge=0, description="Opening drawer float in USD")
    opening_float_khr : Decimal       = Field(default=Decimal("0.00"), ge=0, description="Opening drawer float in KHR")
    notes             : Optional[str] = None


class SHIFT_CLOSE_SCHEMA(BaseModel):
    closing_cash_usd  : Decimal       = Field(..., ge=0, description="Actual counted drawer cash in USD")
    closing_cash_khr  : Decimal       = Field(..., ge=0, description="Actual counted drawer cash in KHR")
    notes             : Optional[str] = None


class SHIFT_SUMMARY_SCHEMA(BaseModel):
    shift_id               : uuid.UUID
    terminal_id            : uuid.UUID
    terminal_code          : Optional[str]     = None
    branch_id              : uuid.UUID
    branch_name            : Optional[str]     = None
    cashier_id             : uuid.UUID
    cashier_name           : Optional[str]     = None
    opened_at              : datetime
    closed_at              : Optional[datetime] = None
    status_code            : str               = "OPEN"
    opening_float_usd      : Decimal           = Decimal("0.00")
    opening_float_khr      : Decimal           = Decimal("0.00")
    total_sales_count      : int               = 0
    total_sales_amount     : Decimal           = Decimal("0.00")
    cash_sales_amount      : Decimal           = Decimal("0.00")
    cash_payments_count    : int               = 0
    aba_sales_amount       : Decimal           = Decimal("0.00")
    aba_payments_count     : int               = 0
    card_sales_amount      : Decimal           = Decimal("0.00")
    card_payments_count    : int               = 0
    bank_sales_amount      : Decimal           = Decimal("0.00")
    expected_cash_usd      : Decimal           = Decimal("0.00")
    expected_cash_khr      : Decimal           = Decimal("0.00")
    closing_cash_usd       : Optional[Decimal] = None
    closing_cash_khr       : Optional[Decimal] = None
    discrepancy_usd        : Optional[Decimal] = None
    discrepancy_khr        : Optional[Decimal] = None
    notes                  : Optional[str]     = None

    model_config = {"from_attributes": True}


class SHIFT_RESPONSE_SCHEMA(BaseModel):
    id                 : uuid.UUID
    terminal_id        : uuid.UUID
    terminal_code      : Optional[str]     = None
    branch_id          : uuid.UUID
    branch_name        : Optional[str]     = None
    cashier_id         : uuid.UUID
    cashier_name       : Optional[str]     = None
    opened_at          : datetime
    closed_at          : Optional[datetime] = None
    opening_float_usd  : Decimal           = Decimal("0.00")
    opening_float_khr  : Decimal           = Decimal("0.00")
    closing_cash_usd   : Optional[Decimal] = None
    closing_cash_khr   : Optional[Decimal] = None
    expected_cash_usd  : Optional[Decimal] = None
    expected_cash_khr  : Optional[Decimal] = None
    status_code        : str               = "OPEN"
    notes              : Optional[str]     = None
    created_at         : datetime

    model_config = {"from_attributes": True}

