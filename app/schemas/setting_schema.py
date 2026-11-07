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


class RECEIPT_TEMPLATE_SCHEMA(BaseModel):
    paper_width: str = Field(default="80mm", pattern="^(80mm|58mm)$")
    store_name: str = Field(default="VANNAK CLOTHING BOUTIQUE", max_length=150)
    store_name_kh: str = Field(default="គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់", max_length=150)
    tagline: Optional[str] = Field(default="Premium Streetwear & Contemporary Fashion", max_length=200)
    logo_url: Optional[str] = Field(default="", max_length=500)
    phone: Optional[str] = Field(default="+855 23 888 999", max_length=50)
    address: Optional[str] = Field(default="#123 Preah Norodom Blvd, Daun Penh, Phnom Penh", max_length=255)
    tax_id: Optional[str] = Field(default="K001-902348572", max_length=50)
    show_item_sku: bool = True
    show_variant_attrs: bool = True
    show_khr_conversion: bool = True
    show_tax_breakdown: bool = True
    show_cashier_name: bool = True
    show_customer_info: bool = True
    footer_message: Optional[str] = Field(default="THANK YOU FOR SHOPPING WITH US!", max_length=255)
    return_policy: Optional[str] = Field(
        default="Exchanges accepted within 7 days with original tag and receipt. Sale items are non-refundable.",
        max_length=500,
    )
    wifi_info: Optional[str] = Field(default="Guest Wi-Fi: Vannak_Store | Pass: fashion2026", max_length=100)
    qr_content: Optional[str] = Field(default="https://kimvannak.store", max_length=255)

    model_config = {"from_attributes": True}


class BRAND_SETTINGS_SCHEMA(BaseModel):
    store_name: str = Field(default="KIM VANNAK CLOTHING", max_length=150)
    store_name_kh: str = Field(default="គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់", max_length=150)
    tagline: Optional[str] = Field(default="Premium Streetwear & Contemporary Fashion", max_length=200)
    tagline_kh: Optional[str] = Field(default="សម្លៀកបំពាក់ទាន់សម័យ និងគុណភាពខ្ពស់", max_length=200)
    logo_url: Optional[str] = Field(default="", max_length=500, description="Primary brand logo (light surfaces)")
    logo_dark_url: Optional[str] = Field(default="", max_length=500, description="Brand logo (dark surfaces)")
    favicon_url: Optional[str] = Field(default="", max_length=500, description="Browser favicon URL")
    phone: Optional[str] = Field(default="+855 23 888 999", max_length=50)
    email: Optional[str] = Field(default="store@kimvannak.store", max_length=100)
    address: Optional[str] = Field(default="#123 Preah Norodom Blvd, Daun Penh, Phnom Penh", max_length=255)
    tax_id: Optional[str] = Field(default="K001-902348572", max_length=50)
    website_url: Optional[str] = Field(default="https://kimvannak.store", max_length=255)
    receipt_footer: Optional[str] = Field(default="THANK YOU FOR SHOPPING WITH US!\nសូមអរគុណដែលបានគាំទ្រហាងយើងខ្ញុំ!", max_length=255)
    return_policy: Optional[str] = Field(default="ទំនិញទិញរួចមិនអាចប្តូរប្រាក់វិញបានទេ (Exchange within 7 days with tag/receipt)", max_length=500)

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

