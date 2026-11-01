"""Catalog metadata API endpoints: Categories, Colors, Sizes, Brands, Suppliers."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from slugify import slugify
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.services.product_service import ProductService
from app.repositories.product_repository import (
    BrandRepository,
    CategoryRepository,
    ColorRepository,
    SizeRepository,
    SupplierRepository,
)
from app.schemas.product_schema import (
    BRAND_CREATE_SCHEMA,
    BRAND_RESPONSE_SCHEMA,
    BRAND_UPDATE_SCHEMA,
    CATEGORY_CREATE_SCHEMA,
    CATEGORY_RESPONSE_SCHEMA,
    CATEGORY_UPDATE_SCHEMA,
    COLOR_CREATE_SCHEMA,
    COLOR_RESPONSE_SCHEMA,
    COLOR_UPDATE_SCHEMA,
    SIZE_CREATE_SCHEMA,
    SIZE_RESPONSE_SCHEMA,
    SIZE_UPDATE_SCHEMA,
    SUPPLIER_CREATE_SCHEMA,
    SUPPLIER_RESPONSE_SCHEMA,
    SUPPLIER_UPDATE_SCHEMA,
)

categories_router = APIRouter(prefix="/categories", tags=["Categories"])
colors_router = APIRouter(prefix="/colors", tags=["Colors"])
sizes_router = APIRouter(prefix="/sizes", tags=["Sizes"])
brands_router = APIRouter(prefix="/brands", tags=["Brands"])
suppliers_router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


# ─── Categories ───────────────────────────────────────────────────────────────
@categories_router.get("/", response_model=list[CATEGORY_RESPONSE_SCHEMA])
async def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> list:
    repo = CategoryRepository(db)
    return await repo.get_all(skip=skip, limit=limit)


@categories_router.post("/", response_model=CATEGORY_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CATEGORY_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.create")),
) -> CATEGORY_RESPONSE_SCHEMA:
    repo = CategoryRepository(db)
    slug = body.slug or slugify(body.name)
    data = body.model_dump(exclude_unset=True)
    data["slug"] = slug
    obj = await repo.create(**data)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@categories_router.get("/{id}", response_model=CATEGORY_RESPONSE_SCHEMA)
async def get_category(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> CATEGORY_RESPONSE_SCHEMA:
    repo = CategoryRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return obj


@categories_router.put("/{id}", response_model=CATEGORY_RESPONSE_SCHEMA)
@categories_router.patch("/{id}", response_model=CATEGORY_RESPONSE_SCHEMA)
async def update_category(
    id: UUID,
    body: CATEGORY_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.update")),
) -> CATEGORY_RESPONSE_SCHEMA:
    repo = CategoryRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and "slug" not in data:
        data["slug"] = slugify(data["name"])
    obj = await repo.update(obj, **data)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@categories_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_category(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.delete")),
) -> Response:
    repo = CategoryRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    await repo.delete(obj)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Colors ───────────────────────────────────────────────────────────────────
@colors_router.get("/", response_model=list[COLOR_RESPONSE_SCHEMA])
async def list_colors(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> list:
    repo = ColorRepository(db)
    return await repo.get_all(skip=skip, limit=limit)


@colors_router.post("/", response_model=COLOR_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_color(
    body: COLOR_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.create")),
) -> COLOR_RESPONSE_SCHEMA:
    repo = ColorRepository(db)
    obj = await repo.create(**body.model_dump(exclude_unset=True))
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@colors_router.get("/{id}", response_model=COLOR_RESPONSE_SCHEMA)
async def get_color(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> COLOR_RESPONSE_SCHEMA:
    repo = ColorRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color not found")
    return obj


@colors_router.put("/{id}", response_model=COLOR_RESPONSE_SCHEMA)
@colors_router.patch("/{id}", response_model=COLOR_RESPONSE_SCHEMA)
async def update_color(
    id: UUID,
    body: COLOR_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.update")),
) -> COLOR_RESPONSE_SCHEMA:
    repo = ColorRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color not found")
    obj = await repo.update(obj, **body.model_dump(exclude_unset=True))
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@colors_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_color(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.delete")),
) -> Response:
    repo = ColorRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color not found")
    await repo.delete(obj)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Sizes ────────────────────────────────────────────────────────────────────
@sizes_router.get("/", response_model=list[SIZE_RESPONSE_SCHEMA])
async def list_sizes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> list:
    repo = SizeRepository(db)
    return await repo.get_all(skip=skip, limit=limit)


@sizes_router.post("/", response_model=SIZE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_size(
    body: SIZE_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.create")),
) -> SIZE_RESPONSE_SCHEMA:
    repo = SizeRepository(db)
    obj = await repo.create(**body.model_dump(exclude_unset=True))
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@sizes_router.get("/{id}", response_model=SIZE_RESPONSE_SCHEMA)
async def get_size(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> SIZE_RESPONSE_SCHEMA:
    repo = SizeRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Size not found")
    return obj


@sizes_router.put("/{id}", response_model=SIZE_RESPONSE_SCHEMA)
@sizes_router.patch("/{id}", response_model=SIZE_RESPONSE_SCHEMA)
async def update_size(
    id: UUID,
    body: SIZE_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.update")),
) -> SIZE_RESPONSE_SCHEMA:
    repo = SizeRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Size not found")
    obj = await repo.update(obj, **body.model_dump(exclude_unset=True))
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@sizes_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_size(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.delete")),
) -> Response:
    repo = SizeRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Size not found")
    await repo.delete(obj)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Brands ───────────────────────────────────────────────────────────────────
@brands_router.get("/", response_model=list[BRAND_RESPONSE_SCHEMA])
async def list_brands(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> list:
    repo = BrandRepository(db)
    return await repo.get_all(skip=skip, limit=limit)


@brands_router.post("/", response_model=BRAND_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_brand(
    body: BRAND_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.create")),
) -> BRAND_RESPONSE_SCHEMA:
    repo = BrandRepository(db)
    slug = body.slug or slugify(body.name)
    data = body.model_dump(exclude_unset=True)
    data["slug"] = slug
    obj = await repo.create(**data)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@brands_router.get("/{id}", response_model=BRAND_RESPONSE_SCHEMA)
async def get_brand(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.read")),
) -> BRAND_RESPONSE_SCHEMA:
    repo = BrandRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return obj


@brands_router.put("/{id}", response_model=BRAND_RESPONSE_SCHEMA)
@brands_router.patch("/{id}", response_model=BRAND_RESPONSE_SCHEMA)
async def update_brand(
    id: UUID,
    body: BRAND_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.update")),
) -> BRAND_RESPONSE_SCHEMA:
    repo = BrandRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and "slug" not in data:
        data["slug"] = slugify(data["name"])
    obj = await repo.update(obj, **data)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return obj


@brands_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_brand(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.delete")),
) -> Response:
    repo = BrandRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    await repo.delete(obj)
    await ProductService.increment_catalog_version(db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Suppliers ────────────────────────────────────────────────────────────────
@suppliers_router.get("/", response_model=list[SUPPLIER_RESPONSE_SCHEMA])
async def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> list:
    repo = SupplierRepository(db)
    return await repo.get_all(skip=skip, limit=limit)


@suppliers_router.post("/", response_model=SUPPLIER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    body: SUPPLIER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.create")),
) -> SUPPLIER_RESPONSE_SCHEMA:
    repo = SupplierRepository(db)
    code = await repo.next_supplier_code()
    data = body.model_dump(exclude_unset=True)
    data["code"] = code
    obj = await repo.create(**data)
    await db.commit()
    return obj


@suppliers_router.get("/{id}", response_model=SUPPLIER_RESPONSE_SCHEMA)
async def get_supplier(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> SUPPLIER_RESPONSE_SCHEMA:
    repo = SupplierRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return obj


@suppliers_router.put("/{id}", response_model=SUPPLIER_RESPONSE_SCHEMA)
@suppliers_router.patch("/{id}", response_model=SUPPLIER_RESPONSE_SCHEMA)
async def update_supplier(
    id: UUID,
    body: SUPPLIER_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.create")),
) -> SUPPLIER_RESPONSE_SCHEMA:
    repo = SupplierRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    obj = await repo.update(obj, **body.model_dump(exclude_unset=True))
    await db.commit()
    return obj


@suppliers_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_supplier(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.create")),
) -> Response:
    repo = SupplierRepository(db)
    obj = await repo.get_by_id(id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    await repo.delete(obj)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
