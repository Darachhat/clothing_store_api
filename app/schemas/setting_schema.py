"""System and Store Settings Schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic.main import BaseModel
from pydantic import Field


class STORE_SETTINGS_SCHEMA(BaseModel):
    name: str = Field(default="Antigravity Clothing Store", min_length=1, max_length=150)
    currency: str = Field(default="USD", pattern="^(USD|KHR|EUR)$")
    phone: Optional[str] = Field(default="")
    email: Optional[str] = Field(default="")
    address: Optional[str] = Field(default="")
    receipt_footer: Optional[str] = Field(default="Thank you for shopping with us! Please come again.")
    default_tax_rate: float = Field(default=5.0, ge=0, le=100)
    tax_inclusive: bool = False
    rounding: str = Field(default="round")

    model_config = {"from_attributes": True}


class GENERIC_SETTING_SCHEMA(BaseModel):
    category: str = Field(..., min_length=1, max_length=50)
    key: str = Field(..., min_length=1, max_length=100)
    value: Dict[str, Any]
    description: Optional[str] = None


class SETTING_RESPONSE_SCHEMA(BaseModel):
    id: uuid.UUID
    category: str
    key: str
    value: Dict[str, Any]
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

