"""Product catalog business service integrating PostgreSQL repository and version-aware Redis cache."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from slugify import slugify
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.product_cache import ProductCache
from app.core.exceptions import NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import CatalogVersion, Color, Product, ProductVariant, Size
from app.repositories.product_repository import ProductRepository, ProductVariantRepository
from app.schemas.product_schema import (
    PRODUCT_CREATE_SCHEMA
    , PRODUCT_UPDATE_SCHEMA
    , PRODUCT_VARIANT_CREATE_SCHEMA
    , PRODUCT_VARIANT_UPDATE_SCHEMA
)
from app.utils.generators import generate_qr_reference, generate_sku

logger = get_logger(__name__)


class PRODUCT_SERVICE:
    """
    High-level Product Catalog Service.
    Coordinates between PostgreSQL (Source of Truth) and Redis (Cache-Aside layer).
    """

    @classmethod
    async def get_catalog_versions(cls, db: AsyncSession) -> Tuple[int, int]:
        """
        Get current (product_version, inventory_version).
        1. Checks Redis cache first for sub-millisecond retrieval.
        2. If absent, queries PostgreSQL catalog_versions table (Source of Truth) and seeds Redis.
        """
        cached_prod_ver = await ProductCache.get_cached_catalog_version()
        cached_inv_ver  = await ProductCache.get_cached_inventory_version()

        if cached_prod_ver is not None and cached_inv_ver is not None:
            return cached_prod_ver, cached_inv_ver

        stmt   = select(CatalogVersion.version, CatalogVersion.inventory_version).where(CatalogVersion.id == 1)
        res    = await db.execute(stmt)
        record = res.first()
        if record:
            prod_ver, inv_ver = int(record[0]), int(record[1])
        else:
            prod_ver, inv_ver = 1, 1

        await ProductCache.set_cached_catalog_version(prod_ver)
        await ProductCache.set_cached_inventory_version(inv_ver)
        return prod_ver, inv_ver

    @classmethod
    async def get_catalog_version(cls, db: AsyncSession) -> int:
        """Get current catalog/product version."""
        p_ver, _ = await cls.get_catalog_versions(db)
        return p_ver

    @classmethod
    async def get_inventory_version(cls, db: AsyncSession) -> int:
        """Get current inventory version."""
        _, i_ver = await cls.get_catalog_versions(db)
        return i_ver

    @classmethod
    async def increment_catalog_version(cls, db: AsyncSession) -> int:
        """
        Increment product catalog version inside the caller's PostgreSQL transaction.
        After commit, syncs new version to Redis.
        """
        stmt = (
            update(CatalogVersion)
            .where(CatalogVersion.id == 1)
            .values(
                version            = CatalogVersion.version + 1
                , updated_datetime = func.now()
            )
            .returning(CatalogVersion.version)
        )
        res         = await db.execute(stmt)
        new_version = res.scalar_one_or_none()
        if new_version is None:
            new_version = 2
            try:
                db.add(CatalogVersion(id=1, version=new_version, inventory_version=1))
                await db.flush()
            except Exception:
                pass

        await ProductCache.set_cached_catalog_version(new_version)
        logger.info(f"Catalog version incremented to: {new_version}")
        return new_version

    @classmethod
    async def increment_inventory_version(cls, db: AsyncSession) -> int:
        """
        Increment inventory version inside the caller's PostgreSQL transaction.
        After commit, syncs new inventory version to Redis.
        """
        stmt = (
            update(CatalogVersion)
            .where(CatalogVersion.id == 1)
            .values(
                inventory_version  = CatalogVersion.inventory_version + 1
                , updated_datetime = func.now()
            )
            .returning(CatalogVersion.inventory_version)
        )
        res         = await db.execute(stmt)
        new_version = res.scalar_one_or_none()
        if new_version is None:
            new_version = 2
            try:
                db.add(CatalogVersion(id=1, version=1, inventory_version=new_version))
                await db.flush()
            except Exception:
                pass

        await ProductCache.set_cached_inventory_version(new_version)
        logger.info(f"Inventory version incremented to: {new_version}")
        return new_version

    @classmethod
    async def get_paginated_products(
        cls
        , db         : AsyncSession
        , raw_params : Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool, int]:
        """
        Fetch paginated products using version-aware Redis cache.
        Returns: (data_dict, is_cache_hit, current_version)
        """
        return await ProductCache.get_or_set_products(
            db                      = db
            , raw_params            = raw_params
            , get_current_versions_fn = cls.get_catalog_versions
        )

    @classmethod
    async def create_product(cls, db: AsyncSession, body: PRODUCT_CREATE_SCHEMA) -> Product:
        repo = ProductRepository(db)

        slug      = slugify(body.name)
        base_slug = slug
        counter   = 1
        while True:
            existing = await db.execute(
                select(Product.id).where(Product.slug == slug)
            )
            if existing.scalar_one_or_none() is None:
                break
            slug     = f"{base_slug}-{counter}"
            counter += 1

        count_result = await db.execute(select(func.count()).select_from(Product))
        count        = count_result.scalar_one()
        seq_num      = count + 1
        while True:
            code = f"PROD-{seq_num:05d}"
            existing_code = await db.execute(
                select(Product.id).where(Product.code == code)
            )
            if existing_code.scalar_one_or_none() is None:
                break
            seq_num += 1

        product = await repo.create(
            code   = code
            , slug = slug
            , **body.model_dump()
        )
        await cls.increment_catalog_version(db)
        await db.commit()
        return product

    @classmethod
    async def get_product(cls, db: AsyncSession, product_id: UUID) -> Product:
        repo    = ProductRepository(db)
        product = await repo.get_with_variants(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")
        return product

    @classmethod
    async def update_product(cls, db: AsyncSession, product_id: UUID, body: PRODUCT_UPDATE_SCHEMA) -> Product:
        repo    = ProductRepository(db)
        product = await repo.get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")
        product = await repo.update(product, **body.model_dump(exclude_none=True))
        await cls.increment_catalog_version(db)
        await db.commit()
        return product

    @classmethod
    async def delete_product(cls, db: AsyncSession, product_id: UUID) -> None:
        repo    = ProductRepository(db)
        product = await repo.get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")
        await repo.delete(product)
        await cls.increment_catalog_version(db)
        await db.commit()

    @classmethod
    async def list_variants(
        cls
        , db         : AsyncSession
        , q          : Optional[str] = None
        , product_id : Optional[UUID] = None
        , color_id   : Optional[UUID] = None
        , size_id    : Optional[UUID] = None
        , skip       : int = 0
        , limit      : int = 50
    ) -> List[ProductVariant]:
        repo = ProductVariantRepository(db)
        return await repo.search(
            q            = q
            , product_id = product_id
            , color_id   = color_id
            , size_id    = size_id
            , skip       = skip
            , limit      = limit
        )

    @classmethod
    async def create_variant(cls, db: AsyncSession, body: PRODUCT_VARIANT_CREATE_SCHEMA) -> ProductVariant:
        repo         = ProductVariantRepository(db)
        product_repo = ProductRepository(db)

        product = await product_repo.get_by_id(body.product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        color_name = None
        size_name  = None
        if body.color_id:
            res        = await db.execute(select(Color).where(Color.id == body.color_id))
            c          = res.scalar_one_or_none()
            color_name = c.name if c else None
        if body.size_id:
            res       = await db.execute(select(Size).where(Size.id == body.size_id))
            s         = res.scalar_one_or_none()
            size_name = s.name if s else None

        count_res = await db.execute(
            select(func.count()).select_from(ProductVariant)
            .where(ProductVariant.product_id == body.product_id)
        )
        count   = count_res.scalar_one()
        seq_num = count + 1
        while True:
            sku = generate_sku(product.code, color_name, size_name, seq_num)
            existing_sku = await db.execute(
                select(ProductVariant.id).where(ProductVariant.sku == sku)
            )
            if existing_sku.scalar_one_or_none() is None:
                break
            seq_num += 1
        qr_reference = await generate_qr_reference(db)

        variant = await repo.create(sku=sku, qr_reference=qr_reference, **body.model_dump())
        await cls.increment_catalog_version(db)
        await db.commit()
        created = await repo.get_by_id(variant.id)
        return created or variant

    @classmethod
    async def delete_variant(cls, db: AsyncSession, variant_id: UUID) -> None:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        await repo.delete(variant)
        await cls.increment_catalog_version(db)
        await db.commit()

    @classmethod
    async def get_variant_by_qr(cls, db: AsyncSession, reference: str) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_qr_reference(reference)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        return variant

    @classmethod
    async def get_variant_by_barcode(cls, db: AsyncSession, barcode: str) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_barcode(barcode)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        return variant

    @classmethod
    async def get_variant_by_sku(cls, db: AsyncSession, sku: str) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_sku(sku)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        return variant

    @classmethod
    async def get_variant(cls, db: AsyncSession, variant_id: UUID) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        return variant

    @classmethod
    async def update_variant(cls, db: AsyncSession, variant_id: UUID, body: PRODUCT_VARIANT_UPDATE_SCHEMA) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        variant = await repo.update(variant, **body.model_dump(exclude_none=True))
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant

    @classmethod
    async def regenerate_variant_codes(cls, db: AsyncSession, variant_id: UUID) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        new_qr = await generate_qr_reference(db)
        variant = await repo.update(variant, qr_reference=new_qr)
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant


PRODUCT_SERVICE = PRODUCT_SERVICE
