"""Comprehensive test suite for version-aware Redis product caching and pagination."""
from __future__ import annotations

import asyncio
from decimal import Decimal
import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client, redis_get, redis_set
from app.core.security import create_access_token, hash_password
from app.models import Branch, Warehouse
from app.models import InventoryStock
from app.models import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.models import Permission, Role, User
from app.repositories.product_repository import ProductRepository
from app.services.product_cache_service import ProductCacheService

@pytest_asyncio.fixture(autouse=True)
async def clear_test_redis():
    """Ensure every test runs with a fresh Redis state."""
    client = get_redis_client()
    try:
        await client.flushdb()
    except Exception:
        pass
    yield
    try:
        await client.flushdb()
    except Exception:
        pass


async def setup_test_catalog(db: AsyncSession) -> dict:
    """Helper to populate mock categories, brands, products and admin user."""
    # 1. Permission and Role
    perm = Permission(code="product.read", name="Read Products", module="products")
    perm_create = Permission(code="product.create", name="Create Products", module="products")
    perm_update = Permission(code="product.update", name="Update Products", module="products")
    perm_delete = Permission(code="product.delete", name="Delete Products", module="products")
    db.add_all([perm, perm_create, perm_update, perm_delete])
    await db.flush()

    role = Role(name="ADMIN", description="Admin role", is_system=True)
    role.permissions = [perm, perm_create, perm_update, perm_delete]
    db.add(role)
    await db.flush()

    user = User(
        username="cache_tester",
        email="cache_tester@example.com",
        full_name="Cache Tester",
        hashed_password=hash_password("test_pass123"),
        status="ACTIVE",
    )
    user.roles = [role]
    db.add(user)

    # 2. Branch & Warehouse
    branch = Branch(name="Test Flagship", code="BR-TEST")
    db.add(branch)
    await db.flush()

    warehouse = Warehouse(name="Main Warehouse", branch_id=branch.id, is_default=True)
    db.add(warehouse)
    await db.flush()

    # 3. Categories
    cat_tshirts = Category(name="T-Shirts", slug="t-shirts", status="ACTIVE")
    cat_hoodies = Category(name="Hoodies", slug="hoodies", status="ACTIVE")
    cat_jeans = Category(name="Jeans", slug="jeans", status="ACTIVE")
    db.add_all([cat_tshirts, cat_hoodies, cat_jeans])
    await db.flush()

    # 4. Brands
    brand_fx = Brand(name="FashionX", slug="fashionx", status="ACTIVE")
    brand_sm = Brand(name="StreetMode", slug="streetmode", status="ACTIVE")
    db.add_all([brand_fx, brand_sm])
    await db.flush()

    # 5. Colors & Sizes
    color_black = Color(name="Black", hex_code="#000000", status="ACTIVE")
    size_m = Size(name="M", type="LETTER", sort_order=2, status="ACTIVE")
    db.add_all([color_black, size_m])
    await db.flush()

    # 6. Supplier
    supplier = Supplier(code="SUPP-001", name="Test Supplier", status="ACTIVE")
    db.add(supplier)
    await db.flush()

    # 7. Products (create 5 products)
    products = []
    for i in range(1, 6):
        cat = cat_tshirts if i <= 3 else cat_hoodies
        brand = brand_fx if i % 2 == 1 else brand_sm
        name = f"Test Product {i} {'Hoodie' if i > 3 else 'T-Shirt'}"
        p = Product(
            code=f"PROD-{i:05d}",
            name=name,
            slug=f"test-product-{i}",
            category_id=cat.id,
            brand_id=brand.id,
            supplier_id=supplier.id,
            status="ACTIVE",
        )
        db.add(p)
        await db.flush()

        v = ProductVariant(
            product_id=p.id,
            color_id=color_black.id,
            size_id=size_m.id,
            sku=f"SKU-{i:05d}-BLK-M",
            qr_reference=f"QR-{i:05d}",
            cost_price=Decimal("10.00"),
            selling_price=Decimal(f"{20.00 + i}"),
            status="ACTIVE",
        )
        db.add(v)
        await db.flush()

        st = InventoryStock(
            variant_id=v.id,
            warehouse_id=warehouse.id,
            quantity=50 + i * 10,
        )
        db.add(st)
        products.append(p)

    # 8. Seed CatalogVersion (id=1)
    from app.models import CatalogVersion
    stmt_cv = select(CatalogVersion).where(CatalogVersion.id == 1)
    res_cv = await db.execute(stmt_cv)
    if res_cv.scalar_one_or_none() is None:
        db.add(CatalogVersion(id=1, version=1, inventory_version=1))

    await db.commit()

    token = create_access_token(user.id)
    return {
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "cat_tshirts": cat_tshirts,
        "cat_hoodies": cat_hoodies,
        "brand_fx": brand_fx,
        "brand_sm": brand_sm,
        "products": products,
        "warehouse": warehouse,
    }


@pytest.mark.asyncio
async def test_page_1_cache_miss_and_hit(client: AsyncClient, db: AsyncSession) -> None:
    """Tests 1 & 2: First request is a Cache MISS, subsequent request is a Cache HIT."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 1. First request -> MISS
    resp1 = await client.get("/api/v1/products/?page=1&page_size=2", headers=headers)
    assert resp1.status_code == 200
    assert resp1.headers.get("X-Cache") == "MISS"
    res1_data = resp1.json()
    assert len(res1_data["items"]) == 2
    assert res1_data["pagination"]["page"] == 1
    assert res1_data["pagination"]["page_size"] == 2
    assert res1_data["pagination"]["total"] == 5
    assert res1_data["pagination"]["total_pages"] == 3
    assert res1_data["pagination"]["has_next"] is True
    assert res1_data["pagination"]["has_previous"] is False

    # 2. Second request with same params -> HIT
    resp2 = await client.get("/api/v1/products/?page=1&page_size=2", headers=headers)
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Cache") == "HIT"
    assert resp2.json() == res1_data


@pytest.mark.asyncio
async def test_page_2_cache_miss_and_hit(client: AsyncClient, db: AsyncSession) -> None:
    """Tests 3 & 4: Page 2 produces distinct key, misses first then hits."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Request Page 2
    resp1 = await client.get("/api/v1/products/?page=2&page_size=2", headers=headers)
    assert resp1.status_code == 200
    assert resp1.headers.get("X-Cache") == "MISS"
    res1_data = resp1.json()
    assert res1_data["pagination"]["page"] == 2
    assert res1_data["pagination"]["has_previous"] is True

    # Page 2 repeated -> HIT
    resp2 = await client.get("/api/v1/products/?page=2&page_size=2", headers=headers)
    assert resp2.status_code == 200
    assert resp2.headers.get("X-Cache") == "HIT"
    assert resp2.json() == res1_data


@pytest.mark.asyncio
async def test_category_and_brand_filters_generate_distinct_caches(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Tests 5 & 6: Filtering by category or brand creates independent caches."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Category: t-shirts
    resp_cat1 = await client.get("/api/v1/products/?category=t-shirts", headers=headers)
    assert resp_cat1.status_code == 200
    assert resp_cat1.headers.get("X-Cache") == "MISS"
    assert resp_cat1.json()["pagination"]["total"] == 3

    # Category: hoodies
    resp_cat2 = await client.get("/api/v1/products/?category=hoodies", headers=headers)
    assert resp_cat2.status_code == 200
    assert resp_cat2.headers.get("X-Cache") == "MISS"
    assert resp_cat2.json()["pagination"]["total"] == 2

    # Brand: FashionX
    resp_brand1 = await client.get("/api/v1/products/?brand=FashionX", headers=headers)
    assert resp_brand1.status_code == 200
    assert resp_brand1.headers.get("X-Cache") == "MISS"

    # Brand: StreetMode
    resp_brand2 = await client.get("/api/v1/products/?brand=StreetMode", headers=headers)
    assert resp_brand2.status_code == 200
    assert resp_brand2.headers.get("X-Cache") == "MISS"


@pytest.mark.asyncio
async def test_search_and_sorting_generate_distinct_caches(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Tests 7 & 8: Searching and sorting parameters are deterministically included in the key."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Search: hoodie
    resp_s1 = await client.get("/api/v1/products/?search=hoodie", headers=headers)
    assert resp_s1.status_code == 200
    assert resp_s1.headers.get("X-Cache") == "MISS"
    assert resp_s1.json()["pagination"]["total"] == 2

    # Search: t-shirt
    resp_s2 = await client.get("/api/v1/products/?search=t-shirt", headers=headers)
    assert resp_s2.status_code == 200
    assert resp_s2.headers.get("X-Cache") == "MISS"
    assert resp_s2.json()["pagination"]["total"] == 3

    # Sort: name asc
    resp_sort1 = await client.get("/api/v1/products/?sort=name&sort_direction=asc", headers=headers)
    assert resp_sort1.status_code == 200
    assert resp_sort1.headers.get("X-Cache") == "MISS"

    # Sort: name desc
    resp_sort2 = await client.get("/api/v1/products/?sort=name&sort_direction=desc", headers=headers)
    assert resp_sort2.status_code == 200
    assert resp_sort2.headers.get("X-Cache") == "MISS"


@pytest.mark.asyncio
async def test_parameter_normalization_and_order_independence() -> None:
    """Test parameter normalization: ordering, casing, and defaults."""
    # 1. Order independence
    p1 = {"page": 1, "page_size": 24, "category": "tshirts"}
    p2 = {"category": "tshirts", "page_size": 24, "page": 1}
    h1 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p1))
    h2 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p2))
    assert h1 == h2, "Query hashes must be identical regardless of parameter order"

    # 2. Casing normalization
    p3 = {"search": "Hoodie", "category": "T-Shirts"}
    p4 = {"search": "hoodie", "category": "t-shirts"}
    h3 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p3))
    h4 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p4))
    assert h3 == h4, "Casing normalization should produce identical hashes"

    # 3. Empty string vs omitted
    p5 = {"page": 1, "page_size": 24, "search": ""}
    p6 = {"page": 1, "page_size": 24}
    h5 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p5))
    h6 = ProductCacheService.generate_query_hash(ProductCacheService.normalize_query_params(p6))
    assert h5 == h6, "Empty string should normalize to omitted"


@pytest.mark.asyncio
async def test_product_version_change_and_cache_refresh(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Tests 9 & 10: Version increment invalidates old cached page and refreshes with new version."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 1. Populate cache (MISS -> HIT)
    r1 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r1.headers.get("X-Cache") == "MISS"

    r2 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r2.headers.get("X-Cache") == "HIT"

    # 2. Increment product version (simulating catalog mutation)
    v_new = await ProductCacheService.increment_product_version()
    assert v_new > 1

    # 3. Subsequent request for same page detects version mismatch and re-queries PostgreSQL
    r3 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r3.status_code == 200
    assert r3.headers.get("X-Cache") == "MISS", "Should miss cache due to version mismatch"

    # 4. Next request hits with new version
    r4 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r4.status_code == 200
    assert r4.headers.get("X-Cache") == "HIT"


@pytest.mark.asyncio
async def test_product_creation_and_deletion_pagination_updates(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Tests 11 & 12: Creating and deleting products logically updates pagination totals."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 1. Initial count = 5
    r1 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r1.json()["pagination"]["total"] == 5

    # 2. Create product via API
    create_payload = {
        "name": "Brand New Denim Jacket",
        "category_id": str(data["cat_tshirts"].id),
        "brand_id": str(data["brand_fx"].id),
        "status": "ACTIVE",
    }
    r_create = await client.post("/api/v1/products/", json=create_payload, headers=headers)
    assert r_create.status_code == 201
    created_id = r_create.json()["id"]

    # 3. List products again -> total should be 6
    r2 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "MISS"
    assert r2.json()["pagination"]["total"] == 6

    # 4. Delete the product
    r_del = await client.delete(f"/api/v1/products/{created_id}", headers=headers)
    assert r_del.status_code == 204

    # 5. List products again -> total is back to 5
    r3 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r3.status_code == 200
    assert r3.headers.get("X-Cache") == "MISS"
    assert r3.json()["pagination"]["total"] == 5


@pytest.mark.asyncio
async def test_inventory_version_update(client: AsyncClient, db: AsyncSession) -> None:
    """Test 14: Inventory updates increment inventory_version and invalidate stock-inclusive caches."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Request with include_stock=true
    r1 = await client.get("/api/v1/products/?include_stock=true", headers=headers)
    assert r1.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS"

    r2 = await client.get("/api/v1/products/?include_stock=true", headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT"

    # Increment inventory version
    await ProductCacheService.increment_inventory_version()

    # Next request with include_stock=true should detect inventory version mismatch
    r3 = await client.get("/api/v1/products/?include_stock=true", headers=headers)
    assert r3.status_code == 200
    assert r3.headers.get("X-Cache") == "MISS"


@pytest.mark.asyncio
async def test_concurrent_requests_cache_stampede(client: AsyncClient, db: AsyncSession) -> None:
    """Test 15: Concurrent requests to the same uncached page are protected against cache stampede."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Launch 10 concurrent requests to the same uncached query
    url = "/api/v1/products/?page=1&page_size=3&category=t-shirts"
    tasks = [client.get(url, headers=headers) for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    # All responses must be successful 200 OK
    assert all(r.status_code == 200 for r in responses)

    # All returned data must be identical
    first_data = responses[0].json()
    assert all(r.json() == first_data for r in responses)


@pytest.mark.asyncio
async def test_redis_failure_graceful_fallback(client: AsyncClient, db: AsyncSession) -> None:
    """Test 16: If Redis is completely unavailable, the API falls back cleanly to PostgreSQL."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Simulate Redis connection failure
    with patch("app.cache.product_cache.redis_get", side_effect=Exception("Redis connection refused")), \
         patch("app.services.product_cache_service.redis_get", side_effect=Exception("Redis connection refused")):
        resp = await client.get("/api/v1/products/?page=1&page_size=5", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["pagination"]["total"] == 5
        assert len(resp.json()["items"]) == 5


@pytest.mark.asyncio
async def test_race_condition_protection(db: AsyncSession) -> None:
    """Test 19: If version changes during DB execution, stale data is not stored in cache."""
    await setup_test_catalog(db)
    raw_params = {"page": 1, "page_size": 10}

    # Simulate version increment during DB query
    real_search = ProductRepository.search_paginated

    async def mocked_search(*args, **kwargs):
        # Product version increments while query is in-flight!
        await ProductCacheService.increment_product_version()
        repo = ProductRepository(db)
        return await real_search(repo, *args, **kwargs)

    with patch.object(ProductRepository, "search_paginated", side_effect=mocked_search):
        data, is_hit = await ProductCacheService.get_paginated_products(db, raw_params)
        assert is_hit is False
        assert data["pagination"]["total"] == 5

    # Check that Redis does not have the old data stored under the newly incremented version
    normalized = ProductCacheService.normalize_query_params(raw_params)
    cache_key = ProductCacheService.build_cache_key(ProductCacheService.generate_query_hash(normalized))
    cached = await redis_get(cache_key)
    assert cached is None, "Cache should NOT be written when race condition occurs"

    # The cache should be refreshed cleanly on next request
    data2, is_hit2 = await ProductCacheService.get_paginated_products(db, raw_params)
    assert is_hit2 is False
    assert data2["pagination"]["total"] == 5

    # Third call should hit the newly cached data
    data3, is_hit3 = await ProductCacheService.get_paginated_products(db, raw_params)
    assert is_hit3 is True
    assert data3 == data2


@pytest.mark.asyncio
async def test_price_update_invalidates_cache_and_returns_new_price(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Test 5 (Section 24): Variant price update increments catalog version and returns new price."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 1. Warm cache
    r1 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r1.headers.get("X-Cache") == "MISS"
    r2 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r2.headers.get("X-Cache") == "HIT"

    # 2. Update price on first product variant
    prod = data["products"][0]
    variant = prod.variants[0]
    update_payload = {"selling_price": 99.99}

    r_update = await client.put(f"/api/v1/product-variants/{variant.id}", json=update_payload, headers=headers)
    assert r_update.status_code == 200
    assert float(r_update.json()["selling_price"]) == 99.99

    # 3. Next request detects version mismatch, queries DB, and returns fresh response with new version
    r3 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r3.status_code == 200
    assert r3.headers.get("X-Cache") == "MISS"

    # Query product detail to verify the variant updated price
    r_detail = await client.get(f"/api/v1/products/{prod.id}", headers=headers)
    assert r_detail.status_code == 200
    detail_data = r_detail.json()
    matching_variant = next(v for v in detail_data["variants"] if v["id"] == str(variant.id))
    assert float(matching_variant["selling_price"]) == 99.99

    # 4. Subsequent request is a HIT
    r4 = await client.get("/api/v1/products/?page=1&page_size=10", headers=headers)
    assert r4.status_code == 200
    assert r4.headers.get("X-Cache") == "HIT"


@pytest.mark.asyncio
async def test_postgres_as_source_of_truth_recovers_after_redis_flush(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Test (Section 28): PostgreSQL catalog_versions is the source of truth when Redis loses state."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 1. Bump catalog version in PostgreSQL
    from app.services.product_service import ProductService
    v_db = await ProductService.increment_catalog_version(db)
    await db.commit()
    assert v_db > 1

    # 2. Simulate Redis restart / total cache loss
    redis_client = get_redis_client()
    await redis_client.flushdb()

    # 3. Request should query PostgreSQL for the true version and serve fresh data
    r = await client.get("/api/v1/products/?page=1&page_size=5", headers=headers)
    assert r.status_code == 200
    assert r.headers.get("X-Cache") == "MISS"
    assert r.headers.get("X-Cache-Version") == str(v_db)
    assert len(r.json()["items"]) == 5


# ─── NEW: Pagination Edge Case Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_last_page_has_no_next(client: AsyncClient, db: AsyncSession) -> None:
    """Test: Last page has has_next=False and has_previous=True."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 5 products, page_size=2 → 3 pages. Last page = page 3
    resp = await client.get("/api/v1/products/?page=3&page_size=2", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["page"] == 3
    assert body["pagination"]["has_next"] is False
    assert body["pagination"]["has_previous"] is True
    assert len(body["items"]) == 1  # Only 1 product on last page (5 total, page_size=2)


@pytest.mark.asyncio
async def test_empty_result_set(client: AsyncClient, db: AsyncSession) -> None:
    """Empty result: search term that matches nothing returns 0 items and valid pagination."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    resp = await client.get("/api/v1/products/?search=zzznotarealproductxyz", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 0
    assert len(body["items"]) == 0
    # total_pages should be >= 1 even for empty (avoids division-by-zero issues)
    assert body["pagination"]["total_pages"] >= 1


@pytest.mark.asyncio
async def test_page_beyond_total_pages_returns_empty(client: AsyncClient, db: AsyncSession) -> None:
    """Phase 3: Requesting a page beyond total_pages returns an empty items list."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 5 products, page_size=10 → 1 page. Requesting page=99 gracefully returns empty.
    resp = await client.get("/api/v1/products/?page=99&page_size=10", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 0
    assert body["pagination"]["page"] == 99


@pytest.mark.asyncio
async def test_combined_search_category_brand_sort_pagination(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Phase 4: Search + category + brand + sort + page all work together correctly."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Search for "hoodie" in hoodies category from FashionX brand, sorted by name asc
    resp = await client.get(
        "/api/v1/products/?page=1&page_size=5"
        "&search=hoodie&category=hoodies&brand=FashionX"
        "&sort=name&sort_direction=asc",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["page_size"] == 5
    # Items are sorted by name ascending
    names = [item["name"] for item in body["items"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_page_size_defaults_to_24_when_omitted(client: AsyncClient, db: AsyncSession) -> None:
    """Phase 3: Default page_size is 24 when not specified."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    resp = await client.get("/api/v1/products/", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["page_size"] == 24


@pytest.mark.asyncio
async def test_page_size_maximum_enforced(client: AsyncClient, db: AsyncSession) -> None:
    """Phase 3: page_size > 100 is rejected by the API validator."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    resp = await client.get("/api/v1/products/?page_size=200", headers=headers)
    # FastAPI Query validation rejects page_size > 100
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_include_variants_returns_variant_data(client: AsyncClient, db: AsyncSession) -> None:
    """Phase 8/16: include_variants=true returns products with embedded variant data for POS."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    resp = await client.get("/api/v1/products/?page=1&page_size=5&include_variants=true", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) > 0

    for item in body["items"]:
        assert "variants" in item, "Product should have 'variants' key when include_variants=true"
        for v in item["variants"]:
            assert "sku" in v


@pytest.mark.asyncio
async def test_include_variants_false_returns_product_without_variants(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Phase 8: include_variants=false (default) returns standard PRODUCT_RESPONSE_SCHEMA without variants list."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    resp = await client.get("/api/v1/products/?page=1&page_size=5", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) > 0
    for item in body["items"]:
        # PRODUCT_RESPONSE_SCHEMA does not include a nested variants list
        assert "sku" not in item  # sku is a variant field, not a product field


@pytest.mark.asyncio
async def test_different_pages_produce_distinct_cache_keys(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Phase 5: Each page produces a unique cache key — pages don't collide."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    r1 = await client.get("/api/v1/products/?page=1&page_size=2", headers=headers)
    r2 = await client.get("/api/v1/products/?page=2&page_size=2", headers=headers)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS"
    assert r2.headers.get("X-Cache") == "MISS"

    items_p1 = [item["id"] for item in r1.json()["items"]]
    items_p2 = [item["id"] for item in r2.json()["items"]]
    assert set(items_p1).isdisjoint(set(items_p2)), "Page 1 and Page 2 should contain different products"

    # Second request for page 2 should be a cache HIT
    r2_again = await client.get("/api/v1/products/?page=2&page_size=2", headers=headers)
    assert r2_again.headers.get("X-Cache") == "HIT"


@pytest.mark.asyncio
async def test_sort_direction_generates_distinct_results(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Phase 4/6: Sorting asc vs desc produces correctly ordered and distinct results."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    r_asc = await client.get("/api/v1/products/?sort=name&sort_direction=asc", headers=headers)
    r_desc = await client.get("/api/v1/products/?sort=name&sort_direction=desc", headers=headers)

    assert r_asc.status_code == 200
    assert r_desc.status_code == 200

    names_asc = [item["name"] for item in r_asc.json()["items"]]
    names_desc = [item["name"] for item in r_desc.json()["items"]]

    assert names_asc == sorted(names_asc), "ASC sort should be alphabetically ascending"
    assert names_desc == sorted(names_desc, reverse=True), "DESC sort should be alphabetically descending"
    assert names_asc != names_desc, "ASC and DESC should produce different orderings"


@pytest.mark.asyncio
async def test_showing_x_to_y_of_z_metadata(client: AsyncClient, db: AsyncSession) -> None:
    """Phase 10: Pagination metadata supports computing Showing X-Y of Z on the frontend."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # 5 products, page_size=2
    r1 = await client.get("/api/v1/products/?page=1&page_size=2", headers=headers)
    meta1 = r1.json()["pagination"]
    start1 = (meta1["page"] - 1) * meta1["page_size"] + 1
    end1 = min(meta1["page"] * meta1["page_size"], meta1["total"])
    assert start1 == 1
    assert end1 == 2

    r2 = await client.get("/api/v1/products/?page=2&page_size=2", headers=headers)
    meta2 = r2.json()["pagination"]
    start2 = (meta2["page"] - 1) * meta2["page_size"] + 1
    end2 = min(meta2["page"] * meta2["page_size"], meta2["total"])
    assert start2 == 3
    assert end2 == 4

    # Last page (page 3): showing 5-5 of 5
    r3 = await client.get("/api/v1/products/?page=3&page_size=2", headers=headers)
    meta3 = r3.json()["pagination"]
    start3 = (meta3["page"] - 1) * meta3["page_size"] + 1
    end3 = min(meta3["page"] * meta3["page_size"], meta3["total"])
    assert start3 == 5
    assert end3 == 5


@pytest.mark.asyncio
async def test_cache_key_isolates_include_variants_flag(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Phase 6: include_variants flag is part of the cache key — no sharing between responses."""
    data = await setup_test_catalog(db)
    headers = data["headers"]

    # Request without variants → MISS
    r1 = await client.get("/api/v1/products/?page=1&page_size=5", headers=headers)
    assert r1.headers.get("X-Cache") == "MISS"

    # Request with variants → separate MISS (different cache key)
    r2 = await client.get("/api/v1/products/?page=1&page_size=5&include_variants=true", headers=headers)
    assert r2.headers.get("X-Cache") == "MISS"

    for item in r2.json()["items"]:
        assert "variants" in item

    # Second request with variants → HIT
    r3 = await client.get("/api/v1/products/?page=1&page_size=5&include_variants=true", headers=headers)
    assert r3.headers.get("X-Cache") == "HIT"
