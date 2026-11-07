"""Product catalog business service integrating PostgreSQL repository and version-aware Redis cache."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from slugify import slugify
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.product_cache import ProductCache
from app.core.enum.common_enum import INVENTORY_MOVEMENT_TYPE_ENUM
from app.core.exceptions import NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import CatalogVersion, Color, Product, ProductVariant, Size, Warehouse
from app.repositories.inventory_repository import InventoryStockRepository
from app.repositories.product_repository import ProductRepository, ProductVariantRepository
from app.schemas.product_schema import (
    PRODUCT_CREATE_SCHEMA
    , PRODUCT_UPDATE_SCHEMA
    , PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA
    , PRODUCT_VARIANT_CREATE_SCHEMA
    , PRODUCT_VARIANT_UPDATE_SCHEMA
    , VARIANT_SCAN_RESPONSE_SCHEMA
)
from app.utils.codes import generate_compact_barcode, normalize_scanned_code
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
    async def _apply_initial_stock(
        cls,
        db: AsyncSession,
        variant_id: UUID,
        initial_stock: int,
        warehouse_id: Optional[UUID] = None,
    ) -> None:
        if not initial_stock or initial_stock <= 0:
            return
        target_wh_id = warehouse_id
        if not target_wh_id:
            wh_res = await db.execute(
                select(Warehouse.id)
                .where(Warehouse.status_code == "ACTIVE")
                .order_by(Warehouse.is_default.desc())
                .limit(1)
            )
            target_wh_id = wh_res.scalar_one_or_none()
            if not target_wh_id:
                wh_res_any = await db.execute(
                    select(Warehouse.id).order_by(Warehouse.is_default.desc()).limit(1)
                )
                target_wh_id = wh_res_any.scalar_one_or_none()
        if not target_wh_id:
            return

        stock_repo = InventoryStockRepository(db)
        await stock_repo.adjust_stock(
            variant_id=variant_id,
            warehouse_id=target_wh_id,
            delta=int(initial_stock),
            movement_type=INVENTORY_MOVEMENT_TYPE_ENUM.INITIAL_STOCK.value,
            reference_type="manual",
            note="Initial stock on product/variant creation",
        )
        await cls.increment_inventory_version(db)

    @classmethod
    async def _create_variant_internal(
        cls,
        db: AsyncSession,
        product: Product,
        body: PRODUCT_VARIANT_CREATE_SCHEMA | PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA,
    ) -> ProductVariant:
        repo = ProductVariantRepository(db)

        color_name = None
        size_name = None
        if body.color_id:
            res = await db.execute(select(Color).where(Color.id == body.color_id))
            c = res.scalar_one_or_none()
            color_name = c.name if c else None
        if body.size_id:
            res = await db.execute(select(Size).where(Size.id == body.size_id))
            s = res.scalar_one_or_none()
            size_name = s.name if s else None

        count_res = await db.execute(
            select(func.count())
            .select_from(ProductVariant)
            .where(ProductVariant.product_id == product.id)
        )
        count = count_res.scalar_one()
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

        raw_barcode = (body.barcode or "").strip()
        if raw_barcode:
            resolved_barcode = normalize_scanned_code(raw_barcode) or raw_barcode
        else:
            b_seq = seq_num
            while True:
                candidate = generate_compact_barcode(product.code, b_seq)
                existing_bc = await db.execute(
                    select(ProductVariant.id).where(ProductVariant.barcode == candidate)
                )
                if existing_bc.scalar_one_or_none() is None:
                    resolved_barcode = candidate
                    break
                b_seq += 1

        dump_data = body.model_dump(exclude={"initial_stock", "warehouse_id", "product_id", "barcode"})
        variant = await repo.create(
            product_id=product.id,
            sku=sku,
            qr_reference=qr_reference,
            barcode=resolved_barcode,
            **dump_data,
        )

        if getattr(body, "initial_stock", 0) and body.initial_stock > 0:
            await cls._apply_initial_stock(
                db=db,
                variant_id=variant.id,
                initial_stock=body.initial_stock,
                warehouse_id=getattr(body, "warehouse_id", None),
            )

        return variant

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

        product_payload = body.model_dump(exclude={"initial_variant", "variants"})
        product = await repo.create(
            code   = code
            , slug = slug
            , **product_payload
        )

        # Create initial variant(s) if provided on product creation
        variants_to_create: List[PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA] = []
        if body.initial_variant is not None:
            variants_to_create.append(body.initial_variant)
        if body.variants:
            variants_to_create.extend(body.variants)

        for v_body in variants_to_create:
            await cls._create_variant_internal(db, product, v_body)

        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            db,
            action="PRODUCT_CREATED",
            entity_type="product",
            entity_id=product.id,
            new_data={"code": product.code, "name": product.name},
        )
        await cls.increment_catalog_version(db)
        await db.commit()
        created = await repo.get_with_variants(product.id)
        return created or product

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
        old_name = product.name
        old_status = product.status
        product = await repo.update(product, **body.model_dump(exclude_none=True))
        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            db,
            action="PRODUCT_UPDATED",
            entity_type="product",
            entity_id=product.id,
            old_data={"name": old_name, "status": old_status},
            new_data={"name": product.name, "status": product.status},
        )
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_with_variants(product.id)
        return updated or product

    @classmethod
    async def delete_product(cls, db: AsyncSession, product_id: UUID) -> None:
        repo    = ProductRepository(db)
        product = await repo.get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")
        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            db,
            action="PRODUCT_DELETED",
            entity_type="product",
            entity_id=product.id,
            old_data={"code": product.code, "name": product.name},
        )
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

        variant = await cls._create_variant_internal(db, product, body)
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
        update_kwargs: Dict[str, Any] = {"qr_reference": new_qr}
        if not variant.barcode:
            prod_code = variant.product.code if variant.product else "PROD-00001"
            b_seq = 1
            while True:
                candidate = generate_compact_barcode(prod_code, b_seq)
                existing_bc = await db.execute(
                    select(ProductVariant.id).where(ProductVariant.barcode == candidate)
                )
                if existing_bc.scalar_one_or_none() is None:
                    update_kwargs["barcode"] = candidate
                    break
                b_seq += 1
        variant = await repo.update(variant, **update_kwargs)
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant

    @classmethod
    async def scan_lookup(
        cls,
        db: AsyncSession,
        code: str,
        warehouse_id: Optional[UUID] = None,
    ) -> VARIANT_SCAN_RESPONSE_SCHEMA:
        """
        Unified 1-scan lookup for 1D Barcode, 2D QR Code (including full URLs), SKU, or Product Code.
        """
        clean_code = normalize_scanned_code(code)
        if not clean_code:
            raise NOT_FOUND_EXCEPTION("Empty scan code")

        variant_repo = ProductVariantRepository(db)
        variant = await variant_repo.lookup_by_any_code(clean_code)
        if variant:
            stock_sum = 0
            for st in getattr(variant, "inventory_stocks", []) or []:
                if warehouse_id and st.warehouse_id != warehouse_id:
                    continue
                stock_sum += st.quantity
            return VARIANT_SCAN_RESPONSE_SCHEMA(
                match_type="variant",
                normalized_code=clean_code,
                variant=variant,
                product=None,
                variants=[variant],
                total_stock=stock_sum,
            )

        # Fallback: check if user scanned a parent Product code (e.g. PROD-00024)
        product_repo = ProductRepository(db)
        product = await product_repo.get_by_code(clean_code)
        if product:
            all_variants = list(getattr(product, "variants", []) or [])
            active_variants = [
                v for v in all_variants if getattr(v, "status", "ACTIVE") == "ACTIVE"
            ] or all_variants

            total_stock = 0
            for v in active_variants:
                for st in getattr(v, "inventory_stocks", []) or []:
                    if warehouse_id and st.warehouse_id != warehouse_id:
                        continue
                    total_stock += st.quantity
            product.total_stock = total_stock

            if len(active_variants) == 1:
                hydrated_single = await variant_repo.get_by_id(active_variants[0].id)
                return VARIANT_SCAN_RESPONSE_SCHEMA(
                    match_type="variant",
                    normalized_code=clean_code,
                    variant=hydrated_single or active_variants[0],
                    product=product,
                    variants=active_variants,
                    total_stock=total_stock,
                )

            return VARIANT_SCAN_RESPONSE_SCHEMA(
                match_type="product",
                normalized_code=clean_code,
                variant=None,
                product=product,
                variants=active_variants,
                total_stock=total_stock,
            )

        raise NOT_FOUND_EXCEPTION(f"No product or variant found for code '{clean_code}'")


PRODUCT_SERVICE = PRODUCT_SERVICE
