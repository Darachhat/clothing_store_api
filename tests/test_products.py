"""Tests for product, variant, QR, SKU, and catalog operations."""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import Branch, Warehouse
from app.models import Brand, Category, Color, Product, ProductVariant, Size
from app.models import Permission, Role, User
from app.repositories.product_repository import ProductRepository, ProductVariantRepository


async def create_catalog_infra(db: AsyncSession):
    branch = Branch(code="CAT-TEST", name="Catalog Test Branch")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(branch_id=branch.id, name="Catalog Warehouse", is_default=True)
    db.add(warehouse)
    await db.flush()

    category = Category(name="Catalog T-Shirts", slug="catalog-t-shirts")
    db.add(category)
    brand = Brand(name="CatalogBrand", slug="catalogbrand")
    db.add(brand)
    color_black = Color(name="CatalogBlack", hex_code="#000001")
    color_white = Color(name="CatalogWhite", hex_code="#FFFFFF")
    db.add_all([color_black, color_white])
    size_m = Size(name="Cat_M", type="LETTER")
    size_l = Size(name="Cat_L", type="LETTER")
    db.add_all([size_m, size_l])
    await db.flush()

    product_perm = Permission(code="product.read", name="Read Product", module="products")
    product_create_perm = Permission(code="product.create", name="Create Product", module="products")
    report_perm = Permission(code="report.read", name="Read Reports", module="reports")
    db.add_all([product_perm, product_create_perm, report_perm])
    await db.flush()

    role = Role(
        name="CATALOG_MANAGER_TEST",
        is_system=True,
        permissions=[product_perm, product_create_perm, report_perm],
    )
    db.add(role)
    await db.flush()

    user = User(
        username="catalog_tester",
        email="catalog@test.com",
        full_name="Catalog Tester",
        hashed_password=hash_password("cat_pass123"),
        branch_id=branch.id,
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)
    await db.flush()
    await db.commit()

    return {
        "branch": branch,
        "warehouse": warehouse,
        "category": category,
        "brand": brand,
        "color_black": color_black,
        "color_white": color_white,
        "size_m": size_m,
        "size_l": size_l,
        "user": user,
    }


@pytest.mark.asyncio
async def test_create_product_and_variants(db: AsyncSession) -> None:
    """Test creating a product with multiple variants."""
    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-CAT-001",
        name="Catalog T-Shirt",
        slug="catalog-t-shirt",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    variant_bm = ProductVariant(
        product_id=product.id,
        sku="TS-CAT-BLK-M-001",
        qr_reference="VAR-CAT-001",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    variant_bl = ProductVariant(
        product_id=product.id,
        sku="TS-CAT-BLK-L-001",
        qr_reference="VAR-CAT-002",
        color_id=infra["color_black"].id,
        size_id=infra["size_l"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    variant_wm = ProductVariant(
        product_id=product.id,
        sku="TS-CAT-WHT-M-001",
        qr_reference="VAR-CAT-003",
        color_id=infra["color_white"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add_all([variant_bm, variant_bl, variant_wm])
    await db.commit()

    # Verify via repository — use get_with_variants to eager-load in async context
    repo = ProductRepository(db)
    fetched = await repo.get_with_variants(product.id)
    assert fetched is not None
    assert fetched.name == "Catalog T-Shirt"
    assert len(fetched.variants) == 3


@pytest.mark.asyncio
async def test_variant_sku_unique_constraint(db: AsyncSession) -> None:
    """Duplicate SKU should fail at DB level."""
    from sqlalchemy.exc import IntegrityError

    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-SKU-UNIQUE",
        name="SKU Unique Test",
        slug="sku-unique-test",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    v1 = ProductVariant(
        product_id=product.id,
        sku="DUPLICATE-SKU-001",
        qr_reference="VAR-UNIQUE-001",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v1)
    await db.flush()

    v2 = ProductVariant(
        product_id=product.id,
        sku="DUPLICATE-SKU-001",  # same SKU — should fail
        qr_reference="VAR-UNIQUE-002",
        color_id=infra["color_white"].id,
        size_id=infra["size_l"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v2)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_variant_qr_unique_constraint(db: AsyncSession) -> None:
    """Duplicate QR reference should fail at DB level."""
    from sqlalchemy.exc import IntegrityError

    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-QR-UNIQUE",
        name="QR Unique Test",
        slug="qr-unique-test",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    v1 = ProductVariant(
        product_id=product.id,
        sku="QR-UNIQUE-001",
        qr_reference="DUPLICATE-QR-REF",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v1)
    await db.flush()

    v2 = ProductVariant(
        product_id=product.id,
        sku="QR-UNIQUE-002",
        qr_reference="DUPLICATE-QR-REF",  # duplicate
        color_id=infra["color_white"].id,
        size_id=infra["size_l"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v2)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_same_color_size_per_product_unique(db: AsyncSession) -> None:
    """Two variants on the same product with the same color+size should fail."""
    from sqlalchemy.exc import IntegrityError

    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-CS-UNIQUE",
        name="Color Size Unique Test",
        slug="cs-unique-test",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    v1 = ProductVariant(
        product_id=product.id,
        sku="CS-UNIQUE-001",
        qr_reference="VAR-CS-001",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v1)
    await db.flush()

    v2 = ProductVariant(
        product_id=product.id,
        sku="CS-UNIQUE-002",
        qr_reference="VAR-CS-002",
        color_id=infra["color_black"].id,  # same color
        size_id=infra["size_m"].id,         # same size
        cost_price=Decimal("5.00"),
        selling_price=Decimal("15.00"),
    )
    db.add(v2)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_lookup_variant_by_sku(db: AsyncSession) -> None:
    """ProductVariantRepository should find a variant by SKU."""
    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-SKU-LOOK",
        name="SKU Lookup Test",
        slug="sku-lookup-test",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="LOOKUP-SKU-001",
        qr_reference="VAR-LOOK-001",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("6.00"),
        selling_price=Decimal("18.00"),
    )
    db.add(variant)
    await db.commit()

    repo = ProductVariantRepository(db)
    found = await repo.get_by_sku("LOOKUP-SKU-001")
    assert found is not None
    assert found.sku == "LOOKUP-SKU-001"
    assert found.qr_reference == "VAR-LOOK-001"


@pytest.mark.asyncio
async def test_lookup_variant_by_qr(db: AsyncSession) -> None:
    """ProductVariantRepository should find a variant by QR reference."""
    infra = await create_catalog_infra(db)

    product = Product(
        code="TS-QR-LOOK",
        name="QR Lookup Test",
        slug="qr-lookup-test",
        category_id=infra["category"].id,
        brand_id=infra["brand"].id,
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        sku="LOOK-QR-SKU-001",
        qr_reference="VAR-QR-LOOK-001",
        color_id=infra["color_black"].id,
        size_id=infra["size_m"].id,
        cost_price=Decimal("6.00"),
        selling_price=Decimal("18.00"),
    )
    db.add(variant)
    await db.commit()

    repo = ProductVariantRepository(db)
    found = await repo.get_by_qr_reference("VAR-QR-LOOK-001")
    assert found is not None
    assert found.sku == "LOOK-QR-SKU-001"


@pytest.mark.asyncio
async def test_product_api_crud(client: AsyncClient, db: AsyncSession) -> None:
    """End-to-end: login → list products → create product via API."""
    await create_catalog_infra(db)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "catalog_tester", "password": "cat_pass123"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List products (should be empty)
    list_resp = await client.get("/api/v1/products/", headers=headers)
    assert list_resp.status_code == 200

    # Get categories, brands for product creation
    cats = await client.get("/api/v1/categories/", headers=headers)
    brands = await client.get("/api/v1/brands/", headers=headers)
    assert cats.status_code == 200
    assert brands.status_code == 200
