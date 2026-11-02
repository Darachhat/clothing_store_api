"""Version-aware Redis caching facade for product catalog pagination and filtering."""
from __future__ import annotations

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.cache_service import CacheService
from app.cache.product_cache import ProductCache
from app.core.redis import redis_delete, redis_get, redis_incr, redis_set
from app.services.product_service import PRODUCT_SERVICE


class ProductCacheService:
    """
    Facade preserving existing interface while routing through PRODUCT_SERVICE & ProductCache.
    PostgreSQL is the source of truth; Redis provides cache-aside performance.
    """

    PRODUCT_VERSION_KEY = ProductCache.get_version_key()
    INVENTORY_VERSION_KEY = ProductCache.get_inventory_version_key()

    @classmethod
    def normalize_query_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        return CacheService.normalize_query_params(params)

    @classmethod
    def generate_query_hash(cls, normalized_params: dict[str, Any]) -> str:
        return CacheService.generate_query_hash(normalized_params)

    @classmethod
    def build_cache_key(cls, query_hash: str) -> str:
        return ProductCache.get_cache_key(query_hash)

    @classmethod
    async def get_product_version(cls, db: AsyncSession | None = None) -> int:
        if db is not None:
            return await PRODUCT_SERVICE.get_catalog_version(db)
        ver = await ProductCache.get_cached_catalog_version()
        if ver is not None:
            return ver
        return 1

    @classmethod
    async def increment_product_version(cls, db: AsyncSession | None = None) -> int:
        if db is not None:
            return await PRODUCT_SERVICE.increment_catalog_version(db)
        # Standalone Redis increment fallback
        from app.core.redis import redis_incr
        new_v = await redis_incr(cls.PRODUCT_VERSION_KEY)
        await ProductCache.set_cached_catalog_version(new_v)
        return new_v

    @classmethod
    async def get_inventory_version(cls, db: AsyncSession | None = None) -> int:
        if db is not None:
            return await PRODUCT_SERVICE.get_inventory_version(db)
        ver = await ProductCache.get_cached_inventory_version()
        if ver is not None:
            return ver
        return 1

    @classmethod
    async def increment_inventory_version(cls, db: AsyncSession | None = None) -> int:
        if db is not None:
            return await PRODUCT_SERVICE.increment_inventory_version(db)
        from app.core.redis import redis_incr
        new_v = await redis_incr(cls.INVENTORY_VERSION_KEY)
        await ProductCache.set_cached_inventory_version(new_v)
        return new_v

    @classmethod
    async def get_paginated_products(
        cls,
        db: AsyncSession,
        raw_params: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        data, is_hit, _ = await PRODUCT_SERVICE.get_paginated_products(db, raw_params)
        return data, is_hit
