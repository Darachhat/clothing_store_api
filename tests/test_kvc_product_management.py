"""Comprehensive tests for KVC Product & Product Variant Management."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.product_cache import ProductCache
from app.core.security import hash_password


@pytest.fixture(autouse=True)
def fast_no_redis(monkeypatch):
    async def _noop_get():
        return None

    async def _noop_set(_v: int):
        return True

    monkeypatch.setattr(ProductCache, "get_cached_catalog_version", _noop_get)
    monkeypatch.setattr(ProductCache, "get_cached_inventory_version", _noop_get)
    monkeypatch.setattr(ProductCache, "set_cached_catalog_version", _noop_set)
    monkeypatch.setattr(ProductCache, "set_cached_inventory_version", _noop_set)
from app.models import (
    AUDIT_LOG_MODEL,
    BRAND_MODEL,
    Branch,
    CATEGORY_MODEL,
    Color,
    PERMISSION_MODEL,
    ROLE_MODEL,
    Size,
    User,
    Warehouse,
)


async def setup_kvc_test_env(db: AsyncSession):
    branch = Branch(code="KVC-HQ", name="KVC Flagship Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="KVC Main Warehouse", is_default=True)
    db.add(warehouse)

    category = CATEGORY_MODEL(name="T-Shirt", slug="t-shirt")
    brand = BRAND_MODEL(name="KVC", slug="kvc")
    db.add_all([category, brand])

    colors = {
        "Black": Color(name="Black", hex_code="#000000"),
        "White": Color(name="White", hex_code="#FFFFFF"),
        "Gray": Color(name="Gray", hex_code="#808080"),
    }
    sizes = {
        "S": Size(name="S", type="LETTER", sort_order=1),
        "M": Size(name="M", type="LETTER", sort_order=2),
        "L": Size(name="L", type="LETTER", sort_order=3),
    }
    db.add_all(list(colors.values()) + list(sizes.values()))
    await db.flush()

    perms = {
        code: PERMISSION_MODEL(code=code, name=code, module="products")
        for code in ["product.read", "product.create", "product.update", "product.delete"]
    }
    db.add_all(list(perms.values()))
    await db.flush()

    admin_role = ROLE_MODEL(
        name="ADMIN",
        is_system=True,
        permissions=list(perms.values()),
    )
    stock_role = ROLE_MODEL(
        name="WAREHOUSE",
        is_system=True,
        permissions=[perms["product.read"]],
    )
    db.add_all([admin_role, stock_role])
    await db.flush()

    admin_user = User(
        username="kvc_admin",
        email="admin@kvc.com",
        full_name="KVC Admin",
        hashed_password=hash_password("admin_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[admin_role],
    )
    stock_user = User(
        username="kvc_stock",
        email="stock@kvc.com",
        full_name="KVC Stock Manager",
        hashed_password=hash_password("stock_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
        roles=[stock_role],
    )
    db.add_all([admin_user, stock_user])
    await db.commit()

    return {
        "category": category,
        "brand": brand,
        "colors": colors,
        "sizes": sizes,
        "admin_user": admin_user,
        "stock_user": stock_user,
    }


async def login_headers(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_kvc_product_lifecycle_and_duplicate_code(client: AsyncClient, db: AsyncSession) -> None:
    """Test creating a product with custom code TSH-001, rejecting duplicate code, updating, and archiving."""
    env = await setup_kvc_test_env(db)
    headers = await login_headers(client, "kvc_admin", "admin_pass123")

    # 1. Create dynamic attribute and value
    attr_resp = await client.post(
        "/api/admin/v1/product-attributes",
        headers=headers,
        json={"name": "fit", "display_name": "Fit", "attribute_type": "SELECT", "sort_order": 1},
    )
    assert attr_resp.status_code == 201
    attr_id = attr_resp.json()["id"]

    val_resp = await client.post(
        f"/api/admin/v1/product-attributes/{attr_id}/values",
        headers=headers,
        json={"value": "OVERSIZE", "display_value": "Oversize", "sort_order": 1},
    )
    assert val_resp.status_code == 201
    val_id = val_resp.json()["id"]

    # 2. Create Product with custom code TSH-001, tags, gallery images, and dynamic attributes
    create_resp = await client.post(
        "/api/admin/v1/products",
        headers=headers,
        json={
            "name": "Basic Oversize T-Shirt",
            "code": "TSH-001",
            "description": "Heavyweight 100% cotton oversize tee",
            "category_id": str(env["category"].id),
            "brand_id": str(env["brand"].id),
            "tags": ["oversize", "cotton", "bestseller"],
            "images": [
                {"image_url": "/uploads/products/tsh-front.jpg", "is_primary": True, "sort_order": 0},
                {"image_url": "/uploads/products/tsh-back.jpg", "is_primary": False, "sort_order": 1},
            ],
            "attribute_value_ids": [val_id],
        },
    )
    assert create_resp.status_code == 201
    prod = create_resp.json()
    product_id = prod["id"]
    assert prod["code"] == "TSH-001"
    assert prod["tags"] == ["oversize", "cotton", "bestseller"]
    assert len(prod["images"]) == 2
    assert prod["image_url"] == "/uploads/products/tsh-front.jpg"
    assert len(prod["attribute_assignments"]) == 1
    assert prod["attribute_assignments"][0]["display_value"] == "Oversize"

    # 3. Duplicate product code should be rejected with 409 Conflict
    dup_resp = await client.post(
        "/api/admin/v1/products",
        headers=headers,
        json={"name": "Another Shirt", "code": "TSH-001"},
    )
    assert dup_resp.status_code == 409

    # 4. Generate Color x Size combinations (3 colors x 2 sizes = 6 variants, excluding Gray/S)
    bulk_items = []
    for c_name in ["Black", "White", "Gray"]:
        for s_name in ["S", "M"]:
            if c_name == "Gray" and s_name == "S":
                continue  # Excluded unavailable combination
            bulk_items.append(
                {
                    "color_id": str(env["colors"][c_name].id),
                    "size_id": str(env["sizes"][s_name].id),
                    "cost_price": 5.00,
                    "selling_price": 12.00,
                }
            )

    gen_resp = await client.post(
        f"/api/admin/v1/products/{product_id}/variants/generate",
        headers=headers,
        json={"items": bulk_items},
    )
    assert gen_resp.status_code == 201
    gen_data = gen_resp.json()
    assert len(gen_data["created"]) == 5
    skus = {v["sku"] for v in gen_data["created"]}
    assert "TSH-001-BLK-S" in skus
    assert "TSH-001-BLK-M" in skus
    assert "TSH-001-WHT-S" in skus
    assert "TSH-001-WHT-M" in skus
    assert "TSH-001-GRY-M" in skus

    # 5. Re-running bulk generation skips existing combinations instead of duplicating
    regen_resp = await client.post(
        f"/api/admin/v1/products/{product_id}/variants/generate",
        headers=headers,
        json={"items": bulk_items},
    )
    assert regen_resp.status_code == 201
    assert len(regen_resp.json()["created"]) == 0
    assert len(regen_resp.json()["skipped"]) == 5

    # 6. Updating parent product name/code keeps existing variant SKUs stable
    upd_resp = await client.put(
        f"/api/admin/v1/products/{product_id}",
        headers=headers,
        json={"name": "Basic Oversize T-Shirt V2"},
    )
    assert upd_resp.status_code == 200
    variants_resp = await client.get(f"/api/admin/v1/products/{product_id}/variants", headers=headers)
    assert variants_resp.status_code == 200
    assert {v["sku"] for v in variants_resp.json()} == skus

    # 7. Bulk update variant prices
    bulk_upd_resp = await client.patch(
        f"/api/admin/v1/products/{product_id}/variants/bulk-update",
        headers=headers,
        json={"selling_price": 15.00, "cost_price": 6.00},
    )
    assert bulk_upd_resp.status_code == 200
    for v in bulk_upd_resp.json():
        assert float(v["selling_price"]) == 15.00
        assert float(v["cost_price"]) == 6.00

    # 8. Archive product (DELETE sets status_code = DISCONTINUED)
    del_resp = await client.delete(f"/api/admin/v1/products/{product_id}", headers=headers)
    assert del_resp.status_code == 204
    detail_resp = await client.get(f"/api/admin/v1/products/{product_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status_code"] == "DISCONTINUED"


@pytest.mark.asyncio
async def test_kvc_barcode_qr_lookup_and_audit_regeneration(client: AsyncClient, db: AsyncSession) -> None:
    """Test barcode lookup, QR lookup, invalid code handling, and audit log on regeneration."""
    env = await setup_kvc_test_env(db)
    headers = await login_headers(client, "kvc_admin", "admin_pass123")

    create_resp = await client.post(
        "/api/admin/v1/products",
        headers=headers,
        json={
            "name": "KVC Denim Jacket",
            "code": "JKT-001",
            "initial_variant": {
                "color_id": str(env["colors"]["Black"].id),
                "size_id": str(env["sizes"]["L"].id),
                "cost_price": 15.00,
                "selling_price": 35.00,
            },
        },
    )
    assert create_resp.status_code == 201
    variant = create_resp.json()["variants"][0]
    variant_id = variant["id"]
    old_barcode = variant["barcode"]
    old_qr = variant["qr_reference"]
    assert variant["sku"] == "JKT-001-BLK-L"
    assert old_barcode is not None

    # Barcode lookup
    lookup_bc = await client.get(
        f"/api/admin/v1/product-variants/lookup?barcode={old_barcode}",
        headers=headers,
    )
    assert lookup_bc.status_code == 200
    assert lookup_bc.json()["variant"]["id"] == variant_id

    # QR lookup
    lookup_qr = await client.get(
        f"/api/admin/v1/product-variants/by-qr/{old_qr}",
        headers=headers,
    )
    assert lookup_qr.status_code == 200
    assert lookup_qr.json()["id"] == variant_id

    # Invalid code lookup returns 404
    invalid_resp = await client.get(
        "/api/admin/v1/product-variants/lookup?barcode=NON-EXISTENT-999999",
        headers=headers,
    )
    assert invalid_resp.status_code == 404

    # Regenerate barcode & QR code -> verify new codes and audit log entry
    regen_resp = await client.post(
        f"/api/admin/v1/product-variants/{variant_id}/regenerate-codes",
        headers=headers,
    )
    assert regen_resp.status_code == 200
    new_variant = regen_resp.json()
    assert new_variant["barcode"] != old_barcode
    assert new_variant["qr_reference"] != old_qr

    audit_rows = (
        await db.execute(
            select(AUDIT_LOG_MODEL).where(AUDIT_LOG_MODEL.action == "VARIANT_CODES_REGENERATED")
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].old_value["barcode"] == old_barcode
    assert audit_rows[0].new_value["barcode"] == new_variant["barcode"]


@pytest.mark.asyncio
async def test_kvc_permissions_stock_manager_readonly(client: AsyncClient, db: AsyncSession) -> None:
    """Verify Stock Manager can read/scan products and variants but cannot create, update, or delete."""
    env = await setup_kvc_test_env(db)
    admin_headers = await login_headers(client, "kvc_admin", "admin_pass123")
    stock_headers = await login_headers(client, "kvc_stock", "stock_pass123")

    # Admin creates product
    prod_resp = await client.post(
        "/api/admin/v1/products",
        headers=admin_headers,
        json={"name": "KVC Polo Shirt", "code": "PLO-001"},
    )
    assert prod_resp.status_code == 201
    product_id = prod_resp.json()["id"]

    # Stock Manager can read products and product detail
    sm_list = await client.get("/api/admin/v1/products", headers=stock_headers)
    assert sm_list.status_code == 200

    sm_detail = await client.get(f"/api/admin/v1/products/{product_id}", headers=stock_headers)
    assert sm_detail.status_code == 200

    # Stock Manager is forbidden (403) from creating, updating, or archiving products
    sm_create = await client.post(
        "/api/admin/v1/products",
        headers=stock_headers,
        json={"name": "Unauthorized Product", "code": "UNAUTH-01"},
    )
    assert sm_create.status_code == 403

    sm_update = await client.put(
        f"/api/admin/v1/products/{product_id}",
        headers=stock_headers,
        json={"name": "Tampered Name"},
    )
    assert sm_update.status_code == 403

    sm_delete = await client.delete(f"/api/admin/v1/products/{product_id}", headers=stock_headers)
    assert sm_delete.status_code == 403

    # Unauthenticated request is rejected (401)
    client.cookies.clear()
    unauth = await client.get("/api/admin/v1/products")
    assert unauth.status_code == 401

