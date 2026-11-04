"""Store & System Configuration Settings Endpoints."""
from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import SystemSetting, User
from app.schemas.setting_schema import (
    GENERIC_SETTING_SCHEMA,
    STORE_SETTINGS_SCHEMA,
)

router = APIRouter(prefix="/settings", tags=["Store Settings"])


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
    stmt = select(SystemSetting).where(SystemSetting.category == category)
    result = await db.execute(stmt)
    records = result.scalars().all()

    merged: Dict[str, Any] = {}
    for r in records:
        merged[r.key] = r.value
    return {"category": category, "settings": merged}


@router.put("/{category}")
async def update_category_setting(
    category: str,
    body: GENERIC_SETTING_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Update setting entry within a category (Admin only)."""
    stmt = select(SystemSetting).where(
        SystemSetting.category == category,
        SystemSetting.key == body.key,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record:
        record.value = body.value
        if body.description:
            record.description = body.description
    else:
        record = SystemSetting(
            category=category,
            key=body.key,
            value=body.value,
            description=body.description,
        )
        db.add(record)

    await db.commit()
    return {"status": "success", "category": category, "key": body.key, "value": body.value}

