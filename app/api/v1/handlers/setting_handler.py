"""Store & System Configuration Settings Endpoints."""
from __future__ import annotations

from typing import Any, Dict, Optional, Union
from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import SystemSetting, User
from app.schemas.setting_schema import (
    BRAND_SETTINGS_SCHEMA,
    GENERIC_SETTING_SCHEMA,
    RECEIPT_TEMPLATE_SCHEMA,
    STORE_SETTINGS_SCHEMA,
)

router = APIRouter(prefix="/settings", tags=["Store Settings"])
public_brand_router = APIRouter(prefix="/brand", tags=["Brand & Identity"])

DEFAULT_BRAND_CONFIG: Dict[str, Any] = {
    "store_name": "KIM VANNAK CLOTHING",
    "store_name_kh": "គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់",
    "tagline": "Premium Streetwear & Contemporary Fashion",
    "tagline_kh": "សម្លៀកបំពាក់ទាន់សម័យ និងគុណភាពខ្ពស់",
    "logo_url": "",
    "logo_dark_url": "",
    "favicon_url": "",
    "phone": "+855 23 888 999",
    "email": "store@kimvannak.store",
    "address": "#123 Preah Norodom Blvd, Daun Penh, Phnom Penh",
    "tax_id": "K001-902348572",
    "website_url": "https://kimvannak.store",
    "receipt_footer": "THANK YOU FOR SHOPPING WITH US!\nសូមអរគុណដែលបានគាំទ្រហាងយើងខ្ញុំ!",
    "return_policy": "ទំនិញទិញរួចមិនអាចប្តូរប្រាក់វិញបានទេ (Exchange within 7 days with tag/receipt)",
}

DEFAULT_RECEIPT_CONFIG: Dict[str, Any] = {
    "paper_width": "80mm",
    "store_name": "VANNAK CLOTHING BOUTIQUE",
    "store_name_kh": "គឹម វណ្ណាក់ ហាងលក់សម្លៀកបំពាក់",
    "tagline": "Premium Streetwear & Contemporary Fashion",
    "logo_url": "",
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


async def resolve_brand_settings(db: AsyncSession) -> dict:
    """Resolve layered brand settings: Defaults -> Store Info -> Receipt Template -> Brand Profile."""
    stmt_brand = select(SystemSetting).where(
        SystemSetting.category == "brand",
        SystemSetting.key == "profile",
    )
    brand_record = (await db.execute(stmt_brand)).scalar_one_or_none()
    brand_val = brand_record.value if (brand_record and isinstance(brand_record.value, dict)) else {}

    stmt_store = select(SystemSetting).where(
        SystemSetting.category == "store",
        SystemSetting.key == "store_info",
    )
    store_record = (await db.execute(stmt_store)).scalar_one_or_none()
    store_val = store_record.value if (store_record and isinstance(store_record.value, dict)) else {}

    stmt_receipt = select(SystemSetting).where(
        SystemSetting.category == "receipt",
        SystemSetting.key.in_(["template", "receipt_template"]),
    )
    receipt_records = (await db.execute(stmt_receipt)).scalars().all()
    receipt_val: Dict[str, Any] = {}
    for r in receipt_records:
        if isinstance(r.value, dict):
            receipt_val.update(r.value)

    merged = dict(DEFAULT_BRAND_CONFIG)
    if store_val.get("name"):
        merged["store_name"] = store_val["name"]
    if store_val.get("phone"):
        merged["phone"] = store_val["phone"]
    if store_val.get("email"):
        merged["email"] = store_val["email"]
    if store_val.get("address"):
        merged["address"] = store_val["address"]
    if store_val.get("receipt_footer"):
        merged["receipt_footer"] = store_val["receipt_footer"]

    if receipt_val.get("store_name"):
        merged["store_name"] = receipt_val["store_name"]
    if receipt_val.get("store_name_kh"):
        merged["store_name_kh"] = receipt_val["store_name_kh"]
    if receipt_val.get("tagline"):
        merged["tagline"] = receipt_val["tagline"]
    if receipt_val.get("logo_url"):
        merged["logo_url"] = receipt_val["logo_url"]
    if receipt_val.get("tax_id"):
        merged["tax_id"] = receipt_val["tax_id"]
    if receipt_val.get("return_policy"):
        merged["return_policy"] = receipt_val["return_policy"]

    merged.update(brand_val)
    return merged


@public_brand_router.get("", response_model=BRAND_SETTINGS_SCHEMA)
@public_brand_router.get("/public", response_model=BRAND_SETTINGS_SCHEMA)
async def get_public_brand_profile(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Public read-only brand & logo profile for login screens, customer displays, and web storefronts."""
    return await resolve_brand_settings(db)


@router.get("/brand/public", response_model=BRAND_SETTINGS_SCHEMA)
async def get_public_brand_settings(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve brand identity & logo configuration for public surfaces (login, customer display)."""
    return await resolve_brand_settings(db)


@router.get("/brand", response_model=BRAND_SETTINGS_SCHEMA)
async def get_brand_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Get authoritative brand and logo identity configuration (One Stop source)."""
    return await resolve_brand_settings(db)


@router.put("/brand", response_model=BRAND_SETTINGS_SCHEMA)
async def update_brand_settings(
    body: BRAND_SETTINGS_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Update unified brand and logo identity configuration (One Stop Admin feature)."""
    target_data = body.model_dump()

    # 1. Update or create brand profile
    stmt_brand = select(SystemSetting).where(
        SystemSetting.category == "brand",
        SystemSetting.key == "profile",
    )
    brand_record = (await db.execute(stmt_brand)).scalar_one_or_none()
    if brand_record:
        brand_record.value = target_data
        brand_record.description = "Unified brand identity, logos, and store credentials"
    else:
        brand_record = SystemSetting(
            category="brand",
            key="profile",
            value=target_data,
            description="Unified brand identity, logos, and store credentials",
        )
        db.add(brand_record)

    # 2. Synchronize store_info for consistency
    stmt_store = select(SystemSetting).where(
        SystemSetting.category == "store",
        SystemSetting.key == "store_info",
    )
    store_record = (await db.execute(stmt_store)).scalar_one_or_none()
    store_data = {
        "name": body.store_name,
        "phone": body.phone or "",
        "email": body.email or "",
        "address": body.address or "",
        "receipt_footer": body.receipt_footer or "",
    }
    if store_record:
        curr = store_record.value if isinstance(store_record.value, dict) else {}
        curr.update(store_data)
        store_record.value = curr
    else:
        store_record = SystemSetting(
            category="store",
            key="store_info",
            value=store_data,
            description="Store general profile",
        )
        db.add(store_record)

    # 3. Synchronize receipt template for thermal receipts and invoices
    stmt_receipt = select(SystemSetting).where(
        SystemSetting.category == "receipt",
        SystemSetting.key == "template",
    )
    receipt_record = (await db.execute(stmt_receipt)).scalar_one_or_none()
    receipt_sync = {
        "store_name": body.store_name,
        "store_name_kh": body.store_name_kh,
        "tagline": body.tagline or "",
        "logo_url": body.logo_url or "",
        "phone": body.phone or "",
        "address": body.address or "",
        "tax_id": body.tax_id or "",
        "footer_message": body.receipt_footer or "",
        "return_policy": body.return_policy or "",
    }
    if receipt_record:
        r_curr = receipt_record.value if isinstance(receipt_record.value, dict) else {}
        r_curr.update(receipt_sync)
        receipt_record.value = r_curr
    else:
        receipt_record = SystemSetting(
            category="receipt",
            key="template",
            value={**DEFAULT_RECEIPT_CONFIG, **receipt_sync},
            description="Thermal slip and A4 sales invoice template configuration",
        )
        db.add(receipt_record)

    await db.commit()
    return await resolve_brand_settings(db)


@router.post("/brand/upload-logo")
async def upload_brand_logo(
    file: UploadFile = File(..., description="Brand logo image file (PNG, SVG, WEBP, JPG)"),
    asset_type: str = Form("logo", description="Asset type: logo | logo_dark | favicon"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> dict:
    """Upload brand logo file to storage and return its public URL."""
    try:
        from app.services.r2_service import R2_SERVICE
        res = R2_SERVICE.upload_file(file=file, folder="brand")
        url = res.get("url") or f"/uploads/brand/{res.get('filename')}"
        return {
            "url": url,
            "filename": res.get("filename"),
            "asset_type": asset_type,
            "size": res.get("size", 0),
        }
    except Exception as e:
        logger.error(f"Upload brand asset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload brand asset failed: {str(e)}",
        )


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

    # 3. Layered resolution: Canonical Backend Defaults -> Store Info -> Brand Profile -> Custom Receipt Template
    merged = dict(DEFAULT_RECEIPT_CONFIG)

    # Layer brand profile
    stmt_brand = select(SystemSetting).where(
        SystemSetting.category == "brand",
        SystemSetting.key == "profile",
    )
    brand_record = (await db.execute(stmt_brand)).scalar_one_or_none()
    brand_val = brand_record.value if (brand_record and isinstance(brand_record.value, dict)) else {}

    if brand_val.get("store_name"):
        merged["store_name"] = brand_val["store_name"]
    if brand_val.get("store_name_kh"):
        merged["store_name_kh"] = brand_val["store_name_kh"]
    if brand_val.get("tagline"):
        merged["tagline"] = brand_val["tagline"]
    if brand_val.get("logo_url"):
        merged["logo_url"] = brand_val["logo_url"]
    if brand_val.get("phone"):
        merged["phone"] = brand_val["phone"]
    if brand_val.get("address"):
        merged["address"] = brand_val["address"]
    if brand_val.get("tax_id"):
        merged["tax_id"] = brand_val["tax_id"]
    if brand_val.get("receipt_footer"):
        merged["footer_message"] = brand_val["receipt_footer"]
    if brand_val.get("return_policy"):
        merged["return_policy"] = brand_val["return_policy"]

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

