"""Version-aware Redis caching layer for product catalog queries."""
from __future__ import annotations

import asyncio
import json
import math
from typing import Any, Callable, Coroutine
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.cache_service import CacheService
from app.core.config import settings
from app.core.redis import (
    redis_distributed_lock,
    redis_get,
    redis_incr,
    redis_set,
)
from app.models.product import CatalogVersion
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    PaginationMetadata,
    ProductOut,
    ProductPaginationResponse,
    ProductPaginationWithVariantsResponse,
    ProductWithVariants,
)


class ProductCache:
    """
    Manages version-aware Redis caching for product catalog queries.
    PostgreSQL catalog_versions table is the ultimate source of truth.
    Redis serves as a high-performance cache-aside layer.
    """

    NAMESPACE = "catalog"

    @classmethod
    def get_version_key(cls) -> str:
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:catalog:version"

    @classmethod
    def get_inventory_version_key(cls) -> str:
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:inventory:version"

    @classmethod
    def get_cache_key(cls, query_hash: str) -> str:
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:catalog:data:{query_hash}"

    @classmethod
    def get_lock_key(cls, query_hash: str) -> str:
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:lock:catalog:{query_hash}"

    # ── Redis Fast-Cache Version Helpers ──────────────────────────────
    @classmethod
    async def get_cached_catalog_version(cls) -> int | None:
        """Read catalog version from Redis."""
        try:
            val = await redis_get(cls.get_version_key())
            if val is not None:
                return int(val)
            # Check legacy key fallback
            val_legacy = await redis_get("clothing:products:version")
            if val_legacy is not None:
                return int(val_legacy)
            return None
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Failed to get catalog version from Redis: {e}")
            return None

    @classmethod
    async def set_cached_catalog_version(cls, version: int) -> bool:
        """Sync catalog version into Redis."""
        try:
            await redis_set(cls.get_version_key(), str(version))
            await redis_set("clothing:products:version", str(version))
            return True
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Failed to set catalog version in Redis: {e}")
            return False

    @classmethod
    async def get_cached_inventory_version(cls) -> int | None:
        """Read inventory version from Redis."""
        try:
            val = await redis_get(cls.get_inventory_version_key())
            if val is not None:
                return int(val)
            val_legacy = await redis_get("clothing:inventory:version")
            if val_legacy is not None:
                return int(val_legacy)
            return None
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Failed to get inventory version from Redis: {e}")
            return None

    @classmethod
    async def set_cached_inventory_version(cls, version: int) -> bool:
        """Sync inventory version into Redis."""
        try:
            await redis_set(cls.get_inventory_version_key(), str(version))
            await redis_set("clothing:inventory:version", str(version))
            return True
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Failed to set inventory version in Redis: {e}")
            return False

    # ── Main Read Flow ────────────────────────────────────────────────
    @classmethod
    async def get_or_set_products(
        cls,
        db: AsyncSession,
        raw_params: dict[str, Any],
        get_current_versions_fn: Callable[[AsyncSession], Coroutine[Any, Any, tuple[int, int]]],
    ) -> tuple[dict[str, Any], bool, int]:
        """
        Version-aware read flow:
        1. Normalize params & compute query hash -> Redis cache key
        2. Get current product_version and inventory_version (from PostgreSQL source of truth)
        3. Check Redis cache
        4. If cached version == current version -> Return cached data (PRODUCT_CACHE_HIT)
        5. If miss or version mismatch -> Protect stampede via lock, query DB, verify race condition, store & return (PRODUCT_CACHE_MISS / PRODUCT_CACHE_REFRESH)
        Returns: (response_data_dict, is_cache_hit, current_version)
        """
        normalized = CacheService.normalize_query_params(raw_params)
        query_hash = CacheService.generate_query_hash(normalized)
        cache_key = cls.get_cache_key(query_hash)
        legacy_cache_key = f"clothing:products:list:{query_hash}"
        lock_key = cls.get_lock_key(query_hash)
        include_stock = normalized.get("include_stock", False)
        include_variants = normalized.get("include_variants", False)

        # 1. Determine current data versions (PostgreSQL is source of truth)
        try:
            current_prod_ver, current_inv_ver = await get_current_versions_fn(db)
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Error resolving current catalog version: {e}")
            current_prod_ver, current_inv_ver = 1, 1

        # 2. Check Redis Cache
        cached_payload = None
        try:
            cached_raw = await redis_get(cache_key)
            if not cached_raw:
                cached_raw = await redis_get(legacy_cache_key)

            if cached_raw:
                parsed = json.loads(cached_raw)
                cached_prod_ver = parsed.get("version") or parsed.get("product_version")
                cached_inv_ver = parsed.get("inventory_version")

                prod_ver_ok = cached_prod_ver == current_prod_ver
                inv_ver_ok = True
                if include_stock:
                    inv_ver_ok = cached_inv_ver == current_inv_ver

                if prod_ver_ok and inv_ver_ok and "data" in parsed:
                    logger.info(f"PRODUCT_CACHE_HIT key={cache_key} version={current_prod_ver}")
                    return parsed["data"], True, current_prod_ver
                else:
                    logger.info(
                        f"PRODUCT_CACHE_VERSION_MISMATCH key={cache_key} "
                        f"cached_ver={cached_prod_ver} current_ver={current_prod_ver} "
                        f"cached_inv={cached_inv_ver} current_inv={current_inv_ver}"
                    )
            else:
                logger.info(f"PRODUCT_CACHE_MISS key={cache_key}")
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Error reading cache {cache_key}: {e}")

        # Helper to query PostgreSQL and format standard pagination contract
        async def _query_database() -> tuple[dict[str, Any], int, int]:
            v_prod_start, v_inv_start = await get_current_versions_fn(db)

            repo = ProductRepository(db)
            cat_id = None
            if normalized.get("category_id"):
                try:
                    cat_id = UUID(normalized["category_id"])
                except ValueError:
                    cat_id = None

            br_id = None
            if normalized.get("brand_id"):
                try:
                    br_id = UUID(normalized["brand_id"])
                except ValueError:
                    br_id = None

            wh_id = None
            if normalized.get("warehouse_id"):
                try:
                    wh_id = UUID(normalized["warehouse_id"])
                except ValueError:
                    wh_id = None

            branch_uuid = None
            if normalized.get("branch_id"):
                try:
                    branch_uuid = UUID(normalized["branch_id"])
                except ValueError:
                    branch_uuid = None

            products, total = await repo.search_paginated(
                page=normalized["page"],
                page_size=normalized["page_size"],
                search=normalized.get("search"),
                category=normalized.get("category"),
                category_id=cat_id,
                brand=normalized.get("brand"),
                brand_id=br_id,
                status=normalized.get("status"),
                sort=normalized.get("sort", "created_at"),
                sort_direction=normalized.get("sort_direction", "desc"),
                branch_id=branch_uuid,
                warehouse_id=wh_id,
                include_stock=include_stock,
                include_variants=include_variants,
            )

            page_num = normalized["page"]
            page_sz = normalized["page_size"]
            total_pages = math.ceil(total / page_sz) if total > 0 else 1

            pagination_meta = PaginationMetadata(
                page=page_num,
                page_size=page_sz,
                total=total,
                total_pages=total_pages,
                has_next=page_num < total_pages,
                has_previous=page_num > 1,
            )

            if include_variants or include_stock:
                # Serialize with variant data using ProductWithVariants
                pydantic_items = [ProductWithVariants.model_validate(p) for p in products]
                response_obj = ProductPaginationWithVariantsResponse(
                    items=pydantic_items, pagination=pagination_meta
                )
            else:
                pydantic_items = [ProductOut.model_validate(p) for p in products]
                response_obj = ProductPaginationResponse(
                    items=pydantic_items, pagination=pagination_meta
                )
            return response_obj.model_dump(mode="json"), v_prod_start, v_inv_start

        # 3. Cache Stampede Protection (single-flight mutex lock)
        try:
            async with redis_distributed_lock(lock_key, timeout=10, wait_timeout=2.0) as acquired:
                if not acquired:
                    logger.debug(f"PRODUCT_CACHE_LOCK_WAIT lock={lock_key}")
                    # Another concurrent worker acquired lock; re-check if cache was refreshed
                    try:
                        retry_raw = await redis_get(cache_key) or await redis_get(legacy_cache_key)
                        if retry_raw:
                            retry_parsed = json.loads(retry_raw)
                            c_ver = retry_parsed.get("version") or retry_parsed.get("product_version")
                            if c_ver == current_prod_ver:
                                logger.info(f"PRODUCT_CACHE_HIT key={cache_key} version={current_prod_ver} (after lock wait)")
                                return retry_parsed["data"], True, current_prod_ver
                    except Exception:
                        pass
                else:
                    logger.debug(f"PRODUCT_CACHE_LOCK_ACQUIRED lock={lock_key}")

                # Query database
                data, start_p_ver, start_i_ver = await _query_database()

                # 4. Version Race Condition Protection:
                # Re-check current version after DB query completes
                end_p_ver, end_i_ver = await get_current_versions_fn(db)
                if end_p_ver != start_p_ver or (include_stock and end_i_ver != start_i_ver):
                    logger.warning(
                        f"PRODUCT_CACHE_VERSION_MISMATCH Race condition during query for {cache_key}: "
                        f"start_ver={start_p_ver} != end_ver={end_p_ver}. Skipping cache write."
                    )
                    return data, False, end_p_ver

                # 5. Store fresh data with version and TTL
                ttl = getattr(settings, "REDIS_PRODUCT_CACHE_TTL", 300)
                cache_payload = {
                    "version": end_p_ver,
                    "product_version": end_p_ver,
                    "inventory_version": end_i_ver if include_stock else None,
                    "data": data,
                }
                payload_str = json.dumps(cache_payload)
                try:
                    await redis_set(cache_key, payload_str, ex=ttl)
                    await redis_set(legacy_cache_key, payload_str, ex=ttl)
                    logger.info(f"PRODUCT_CACHE_REFRESH key={cache_key} version={end_p_ver} TTL={ttl}s")
                except Exception as e:
                    logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Failed writing to cache {cache_key}: {e}")

                return data, False, end_p_ver
        except Exception as e:
            logger.warning(f"PRODUCT_CACHE_REDIS_ERROR Redis lock/cache failure, falling back to PostgreSQL: {e}")
            data, _, cur_ver = await _query_database()
            return data, False, cur_ver
