"""Store & System Configuration Settings Endpoints."""
from __future__ import annotations

from typing import Any, Dict, Union
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import SystemSetting, User
from app.schemas.setting_schema import (
    GENERIC_SETTING_SCHEMA,
    RECEIPT_TEMPLATE_SCHEMA,
    STORE_SETTINGS_SCHEMA,
)

router = APIRouter(prefix="/settings", tags=["Store Settings"])

DEFAULT_RECEIPT_CONFIG: Dict[str, Any] = {
    "paper_width": "80mm",
    "store_name": "VANNAK CLOTHING BOUTIQUE",
    "store_name_kh": "គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់",
    "tagline": "Premium Streetwear & Contemporary Fashion",
    "phone": "+855 23 888 999",
    "address": "#123 Preah Norodom Blvd, Daun Penh, Phnom Penh",
    "tax_id": "K001-902348572",
    "show_item_sku": True,
    "show_variant_attrs": True,
    "show_khr_conversion": True,
    "show_tax_breakdown": True,
    "show_cashier_name": True,
    "show_customer_info": True,
    "footer_message": "THANK YOU FOR SHOPPING WITH US!",
    "return_policy": "Exchanges accepted within 7 days with original tag and receipt. Sale items are non-refundable.",
    "wifi_info": "Guest Wi-Fi: Vannak_Store | Pass: fashion2026",
    "qr_content": "https://kimvannak.store",
}


@router.get("/receipt", response_model=RECEIPT_TEMPLATE_SCHEMA)
async def get_receipt_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Get authoritative receipt and invoice template configuration (One Stop backend source)."""
    # 1. Fetch store info profile if present
    stmt_store = select(SystemSetting).where(
        SystemSetting.category == "store",
        SystemSetting.key == "store_info",
    )
    store_record = (await db.execute(stmt_store)).scalar_one_or_none()
    store_val = store_record.value if (store_record and isinstance(store_record.value, dict)) else {}

    # 2. Fetch custom receipt template
    stmt_receipt = select(SystemSetting).where(
        SystemSetting.category == "receipt",
        SystemSetting.key.in_(["template", "receipt_template"]),
    )
    receipt_records = (await db.execute(stmt_receipt)).scalars().all()
    receipt_val: Dict[str, Any] = {}
    for r in receipt_records:
        if isinstance(r.value, dict):
            receipt_val.update(r.value)

    # 3. Layered resolution: Canonical Backend Defaults -> Store Info -> Custom Receipt Template
    merged = dict(DEFAULT_RECEIPT_CONFIG)
    if store_val.get("name"):
        merged["store_name"] = store_val["name"]
    if store_val.get("store_name_kh"):
        merged["store_name_kh"] = store_val["store_name_kh"]
    if store_val.get("phone"):
        merged["phone"] = store_val["phone"]
    if store_val.get("address"):
        merged["address"] = store_val["address"]
    if store_val.get("receipt_footer"):
        merged["footer_message"] = store_val["receipt_footer"]

    merged.update(receipt_val)
    return merged


@router.put("/receipt", response_model=RECEIPT_TEMPLATE_SCHEMA)
async def update_receipt_settings(
    body: RECEIPT_TEMPLATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Update receipt and invoice template configuration (Admin only)."""
    stmt = select(SystemSetting).where(
        SystemSetting.category == "receipt",
        SystemSetting.key == "template",
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    target_data = body.model_dump()

    if record:
        record.value = target_data
        record.description = "Thermal slip and A4 sales invoice template configuration"
    else:
        record = SystemSetting(
            category="receipt",
            key="template",
            value=target_data,
            description="Thermal slip and A4 sales invoice template configuration",
        )
        db.add(record)

    await db.commit()
    return await get_receipt_settings(db=db, _=_)


@router.get("/store", response_model=STORE_SETTINGS_SCHEMA)
async def get_store_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Get active store information and tax configuration."""
    stmt = select(SystemSetting).where(SystemSetting.category.in_(["store", "tax"]))
    result = await db.execute(stmt)
    records = result.scalars().all()

    store_val: Dict[str, Any] = {}
    tax_val: Dict[str, Any] = {}

    for r in records:
        if r.category == "store":
            store_val.update(r.value or {})
        elif r.category == "tax":
            tax_val.update(r.value or {})

    return {
        "name": store_val.get("name", "Antigravity Clothing Store"),
        "currency": store_val.get("currency", "USD"),
        "phone": store_val.get("phone", "+855 23 888 999"),
        "email": store_val.get("email", "store@antigravity.kh"),
        "address": store_val.get("address", "Phnom Penh, Cambodia"),
        "receipt_footer": store_val.get("receipt_footer", "Thank you for shopping with us! Please come again."),
        "default_tax_rate": float(tax_val.get("default_tax_rate", 5.0)),
        "tax_inclusive": bool(tax_val.get("tax_inclusive", False)),
        "rounding": tax_val.get("rounding", "round"),
    }


@router.put("/store", response_model=STORE_SETTINGS_SCHEMA)
async def update_store_settings(
    body: STORE_SETTINGS_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Update store information and tax configuration (Admin only)."""
    # 1. Update or create store info setting
    stmt_store = select(SystemSetting).where(
        SystemSetting.category == "store",
        SystemSetting.key == "store_info",
    )
    store_record = (await db.execute(stmt_store)).scalar_one_or_none()
    store_data = {
        "name": body.name,
        "currency": body.currency,
        "phone": body.phone,
        "email": body.email,
        "address": body.address,
        "receipt_footer": body.receipt_footer,
    }

    if store_record:
        store_record.value = store_data
    else:
        store_record = SystemSetting(
            category="store",
            key="store_info",
            value=store_data,
            description="Store general profile",
        )
        db.add(store_record)

    # 2. Update or create tax setting
    stmt_tax = select(SystemSetting).where(
        SystemSetting.category == "tax",
        SystemSetting.key == "tax_settings",
    )
    tax_record = (await db.execute(stmt_tax)).scalar_one_or_none()
    tax_data = {
        "default_tax_rate": body.default_tax_rate,
        "tax_inclusive": body.tax_inclusive,
        "rounding": body.rounding,
    }

    if tax_record:
        tax_record.value = tax_data
    else:
        tax_record = SystemSetting(
            category="tax",
            key="tax_settings",
            value=tax_data,
            description="Tax configuration",
        )
        db.add(tax_record)

    await db.commit()
    return await get_store_settings(db=db, _=_)


@router.get("/{category}")
async def get_category_settings(
    category: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Retrieve raw settings dictionary for any category."""
    if category == "receipt":
        return await get_receipt_settings(db=db, _=_)

    stmt = select(SystemSetting).where(SystemSetting.category == category)
    result = await db.execute(stmt)
    records = result.scalars().all()

    merged: Dict[str, Any] = {}
    for r in records:
        if isinstance(r.value, dict):
            merged.update(r.value)
        merged[r.key] = r.value

    response: Dict[str, Any] = dict(merged)
    response["category"] = category
    response["settings"] = {r.key: r.value for r in records}
    return response


@router.put("/{category}")
async def update_category_setting(
    category: str,
    body: Union[GENERIC_SETTING_SCHEMA, Dict[str, Any]] = Body(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Update setting entry within a category (Admin only)."""
    if isinstance(body, GENERIC_SETTING_SCHEMA):
        target_key = body.key
        target_val = body.value
        description = body.description
    elif isinstance(body, dict) and "key" in body and "value" in body and isinstance(body["value"], dict):
        target_key = str(body["key"])
        target_val = body["value"]
        description = body.get("description")
    else:
        # Direct dictionary of settings (e.g. from thermal receipts page or frontend form)
        target_key = "template" if category == "receipt" else "config"
        target_val = body if isinstance(body, dict) else {}
        description = f"{category.capitalize()} settings"

    stmt = select(SystemSetting).where(
        SystemSetting.category == category,
        SystemSetting.key == target_key,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record:
        record.value = target_val
        if description:
            record.description = description
    else:
        record = SystemSetting(
            category=category,
            key=target_key,
            value=target_val,
            description=description,
        )
        db.add(record)

    await db.commit()

    result = dict(target_val) if isinstance(target_val, dict) else {}
    result["status"] = "success"
    result["category"] = category
    result["key"] = target_key
    result["value"] = target_val
    return result

