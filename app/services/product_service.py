"""Product catalog business service integrating PostgreSQL repository and version-aware Redis cache."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from slugify import slugify
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.cache.product_cache import ProductCache
from app.core.enum.common_enum import INVENTORY_MOVEMENT_TYPE_ENUM
from app.core.exceptions import CONFLICT_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import (
    CatalogVersion,
    Color,
    InventoryMovement,
    InventoryStock,
    Product,
    ProductAttribute,
    ProductAttributeAssignment,
    ProductAttributeValue,
    ProductImage,
    ProductVariant,
    Size,
    Warehouse,
)
from app.repositories.inventory_repository import InventoryStockRepository
from app.repositories.product_repository import ProductRepository, ProductVariantRepository
from app.schemas.product_schema import (
    PRODUCT_ATTRIBUTE_CREATE_SCHEMA,
    PRODUCT_ATTRIBUTE_UPDATE_SCHEMA,
    PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA,
    PRODUCT_CREATE_SCHEMA,
    PRODUCT_IMAGE_CREATE_SCHEMA,
    PRODUCT_IMAGE_UPDATE_SCHEMA,
    PRODUCT_UPDATE_SCHEMA,
    PRODUCT_VARIANT_BULK_CREATE_SCHEMA,
    PRODUCT_VARIANT_BULK_UPDATE_SCHEMA,
    PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA,
    PRODUCT_VARIANT_CREATE_SCHEMA,
    PRODUCT_VARIANT_UPDATE_SCHEMA,
    VARIANT_SCAN_RESPONSE_SCHEMA,
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
    async def _find_existing_variant_by_code(
        cls,
        db: AsyncSession,
        code: str,
        exclude_variant_id: Optional[UUID] = None,
    ) -> Optional[ProductVariant]:
        """Find any variant whose barcode, QR reference, or SKU matches ``code`` (case-insensitive)."""
        clean = (normalize_scanned_code(code) or code).strip()
        if not clean:
            return None
        clean_lower = clean.lower()
        stmt = (
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(
                or_(
                    func.lower(ProductVariant.barcode) == clean_lower,
                    func.lower(ProductVariant.qr_reference) == clean_lower,
                    func.lower(ProductVariant.sku) == clean_lower,
                )
            )
        )
        if exclude_variant_id is not None:
            stmt = stmt.where(ProductVariant.id != exclude_variant_id)
        res = await db.execute(stmt.limit(1))
        return res.scalars().first()

    @classmethod
    async def _find_existing_color_size_variant(
        cls,
        db: AsyncSession,
        product_id: UUID,
        color_id: Optional[UUID],
        size_id: Optional[UUID],
        exclude_variant_id: Optional[UUID] = None,
    ) -> Optional[ProductVariant]:
        """Check whether a (product_id, color_id, size_id) combination already exists."""
        stmt = select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.color_id.is_(None) if color_id is None else ProductVariant.color_id == color_id,
            ProductVariant.size_id.is_(None) if size_id is None else ProductVariant.size_id == size_id,
        )
        if exclude_variant_id is not None:
            stmt = stmt.where(ProductVariant.id != exclude_variant_id)
        res = await db.execute(stmt.limit(1))
        return res.scalars().first()

    @classmethod
    async def _generate_unique_qr_reference(cls, db: AsyncSession) -> str:
        """Generate a QR reference guaranteed not to collide with existing QR references or barcodes."""
        for _ in range(50):
            candidate = await generate_qr_reference(db)
            conflict = await cls._find_existing_variant_by_code(db, candidate)
            if conflict is None:
                return candidate
        raise CONFLICT_EXCEPTION("Unable to allocate a unique QR reference")

    @classmethod
    async def _create_variant_internal(
        cls,
        db: AsyncSession,
        product: Product,
        body: PRODUCT_VARIANT_CREATE_SCHEMA | PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA,
    ) -> ProductVariant:
        repo = ProductVariantRepository(db)

        dup_combo = await cls._find_existing_color_size_variant(
            db, product.id, body.color_id, body.size_id
        )
        if dup_combo is not None:
            raise CONFLICT_EXCEPTION(
                f"A variant with this color and size already exists for this product ({dup_combo.sku})"
            )

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

        raw_manual_sku = (getattr(body, "sku", None) or "").strip().upper()
        if raw_manual_sku:
            sku_conflict = await cls._find_existing_variant_by_code(db, raw_manual_sku)
            if sku_conflict is not None:
                raise CONFLICT_EXCEPTION(f"SKU '{raw_manual_sku}' is already in use ({sku_conflict.sku})")
            sku = raw_manual_sku
        else:
            base_sku = generate_sku(product.code, color_name, size_name, seq_num)
            candidate_sku = base_sku
            attempt = 1
            while True:
                existing_sku = await db.execute(
                    select(ProductVariant.id).where(func.lower(ProductVariant.sku) == candidate_sku.lower())
                )
                if existing_sku.scalar_one_or_none() is None:
                    sku = candidate_sku
                    break
                attempt += 1
                candidate_sku = f"{base_sku}-{attempt:02d}"

        qr_reference = await cls._generate_unique_qr_reference(db)

        raw_barcode = (body.barcode or "").strip()
        if raw_barcode:
            resolved_barcode = normalize_scanned_code(raw_barcode) or raw_barcode
            conflict = await cls._find_existing_variant_by_code(db, resolved_barcode)
            if conflict is not None:
                conflict_prod = conflict.product.name if getattr(conflict, "product", None) else "another product"
                raise CONFLICT_EXCEPTION(
                    f"Barcode or QR code '{resolved_barcode}' is already assigned to {conflict_prod} ({conflict.sku})"
                )
        else:
            b_seq = seq_num
            while True:
                candidate = generate_compact_barcode(product.code, b_seq)
                conflict = await cls._find_existing_variant_by_code(db, candidate)
                if conflict is None:
                    resolved_barcode = candidate
                    break
                b_seq += 1

        dump_data = body.model_dump(exclude={"initial_stock", "warehouse_id", "product_id", "barcode", "sku"})
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
    async def _sync_product_images(
        cls,
        db: AsyncSession,
        product: Product,
        images_input: List[PRODUCT_IMAGE_CREATE_SCHEMA],
    ) -> None:
        existing_imgs = list(
            (await db.execute(select(ProductImage).where(ProductImage.product_id == product.id))).scalars().all()
        )
        for img in existing_imgs:
            await db.delete(img)
        await db.flush()

        primary_url: Optional[str] = None
        for idx, item in enumerate(images_input):
            url = (item.image_url or "").strip()
            if not url:
                continue
            is_prim = bool(item.is_primary) or (idx == 0 and not any(i.is_primary for i in images_input))
            if is_prim and not primary_url:
                primary_url = url
            db.add(
                ProductImage(
                    product_id=product.id,
                    variant_id=item.variant_id,
                    image_url=url,
                    is_primary=is_prim,
                    sort_order=item.sort_order if item.sort_order else idx,
                    status_code="ACTIVE",
                )
            )
        if primary_url:
            product.image_url = primary_url
        elif not images_input:
            product.image_url = None
        await db.flush()

    @classmethod
    async def _sync_product_attributes(
        cls,
        db: AsyncSession,
        product_id: UUID,
        attribute_value_ids: List[UUID],
    ) -> None:
        existing_assigns = list(
            (await db.execute(
                select(ProductAttributeAssignment).where(ProductAttributeAssignment.product_id == product_id)
            )).scalars().all()
        )
        for assign in existing_assigns:
            await db.delete(assign)
        await db.flush()

        if not attribute_value_ids:
            return

        vals = list(
            (await db.execute(
                select(ProductAttributeValue).where(ProductAttributeValue.id.in_(attribute_value_ids))
            )).scalars().all()
        )
        seen_pairs: set[Tuple[UUID, UUID]] = set()
        for v in vals:
            pair = (v.attribute_id, v.id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            db.add(
                ProductAttributeAssignment(
                    product_id=product_id,
                    attribute_id=v.attribute_id,
                    attribute_value_id=v.id,
                    status_code="ACTIVE",
                )
            )
        await db.flush()

    @classmethod
    async def create_product(cls, db: AsyncSession, body: PRODUCT_CREATE_SCHEMA) -> Product:
        repo = ProductRepository(db)

        slug      = slugify(body.name) or "product"
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

        raw_code = (body.code or "").strip().upper()
        if raw_code:
            existing_code = await db.execute(
                select(Product.id).where(func.lower(Product.code) == raw_code.lower())
            )
            if existing_code.scalar_one_or_none() is not None:
                raise CONFLICT_EXCEPTION(f"Product code '{raw_code}' already exists")
            code = raw_code
        else:
            count_result = await db.execute(select(func.count()).select_from(Product))
            count        = count_result.scalar_one()
            seq_num      = count + 1
            while True:
                code = f"PROD-{seq_num:05d}"
                existing_code = await db.execute(
                    select(Product.id).where(func.lower(Product.code) == code.lower())
                )
                if existing_code.scalar_one_or_none() is None:
                    break
                seq_num += 1

        clean_tags = [t.strip() for t in (body.tags or []) if t and t.strip()]
        product_payload = body.model_dump(
            exclude={"code", "tags", "images", "attribute_value_ids", "initial_variant", "variants"}
        )
        product = await repo.create(
            code   = code,
            slug   = slug,
            tags   = clean_tags,
            **product_payload,
        )

        if body.images is not None:
            await cls._sync_product_images(db, product, body.images)
        elif product.image_url:
            db.add(
                ProductImage(
                    product_id=product.id,
                    image_url=product.image_url,
                    is_primary=True,
                    sort_order=0,
                    status_code="ACTIVE",
                )
            )
            await db.flush()

        if body.attribute_value_ids is not None:
            await cls._sync_product_attributes(db, product.id, body.attribute_value_ids)

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

        update_fields = body.model_dump(
            exclude_unset=True,
            exclude={"images", "attribute_value_ids"},
        )
        if "code" in update_fields:
            new_code = (update_fields["code"] or "").strip().upper()
            if new_code and new_code.lower() != product.code.lower():
                dup = await db.execute(
                    select(Product.id).where(
                        func.lower(Product.code) == new_code.lower(),
                        Product.id != product.id,
                    )
                )
                if dup.scalar_one_or_none() is not None:
                    raise CONFLICT_EXCEPTION(f"Product code '{new_code}' already exists")
                update_fields["code"] = new_code
            else:
                update_fields.pop("code", None)

        if "tags" in update_fields and update_fields["tags"] is not None:
            update_fields["tags"] = [t.strip() for t in update_fields["tags"] if t and t.strip()]

        # Remove None for non-nullable fields
        for non_null in ("name", "status_code", "tags"):
            if non_null in update_fields and update_fields[non_null] is None:
                update_fields.pop(non_null, None)

        if update_fields:
            product = await repo.update(product, **update_fields)

        if body.images is not None:
            await cls._sync_product_images(db, product, body.images)
        if body.attribute_value_ids is not None:
            await cls._sync_product_attributes(db, product.id, body.attribute_value_ids)

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
        """Archive product (set status_code='DISCONTINUED') to preserve dependent variants/sales/stock."""
        repo    = ProductRepository(db)
        product = await repo.get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")
        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            db,
            action="PRODUCT_ARCHIVED",
            entity_type="product",
            entity_id=product.id,
            old_data={"code": product.code, "name": product.name, "status": product.status_code},
            new_data={"status": "DISCONTINUED"},
        )
        await repo.update(product, status_code="DISCONTINUED")
        await cls.increment_catalog_version(db)
        await db.commit()

    @classmethod
    async def bulk_archive_products(cls, db: AsyncSession, product_ids: List[UUID]) -> int:
        if not product_ids:
            return 0
        stmt = (
            update(Product)
            .where(Product.id.in_(product_ids))
            .values(status_code="DISCONTINUED", updated_datetime=func.now())
        )
        res = await db.execute(stmt)
        await cls.increment_catalog_version(db)
        await db.commit()
        return int(res.rowcount or 0)

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
    async def create_variants_bulk(
        cls,
        db: AsyncSession,
        product_id: UUID,
        body: PRODUCT_VARIANT_BULK_CREATE_SCHEMA,
    ) -> Dict[str, Any]:
        """Create many color x size variants (with opening stock) atomically.

        Existing combinations (including duplicates within the request) are skipped and reported.
        """
        product_repo = ProductRepository(db)
        product = await product_repo.get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        existing = {
            (c, s)
            for c, s in (await db.execute(
                select(ProductVariant.color_id, ProductVariant.size_id)
                .where(ProductVariant.product_id == product_id)
            )).all()
        }

        created: List[ProductVariant] = []
        skipped: List[Dict[str, Any]] = []
        seen_barcodes: set[str] = set()
        seen_skus: set[str] = set()
        stock_repo = InventoryStockRepository(db)

        for item in body.items:
            key = (item.color_id, item.size_id)
            if key in existing:
                skipped.append({"color_id": item.color_id, "size_id": item.size_id, "reason": "Variant already exists"})
                continue

            selling = item.selling_price if item.selling_price is not None else body.default_selling_price
            if selling is None:
                skipped.append({"color_id": item.color_id, "size_id": item.size_id, "reason": "No selling price provided"})
                continue

            raw_sku = (item.sku or "").strip().upper() or None
            if raw_sku:
                if raw_sku.lower() in seen_skus:
                    skipped.append({
                        "color_id": item.color_id,
                        "size_id": item.size_id,
                        "reason": f"Duplicate SKU '{raw_sku}' in bulk request",
                    })
                    continue
                sku_conflict = await cls._find_existing_variant_by_code(db, raw_sku)
                if sku_conflict is not None:
                    skipped.append({
                        "color_id": item.color_id,
                        "size_id": item.size_id,
                        "reason": f"SKU '{raw_sku}' is already assigned to {sku_conflict.sku}",
                    })
                    continue

            raw_bc = (item.barcode or "").strip()
            norm_bc = (normalize_scanned_code(raw_bc) or raw_bc).strip() if raw_bc else None
            if norm_bc:
                if norm_bc.lower() in seen_barcodes:
                    skipped.append({
                        "color_id": item.color_id,
                        "size_id": item.size_id,
                        "reason": f"Duplicate barcode '{norm_bc}' in bulk request",
                    })
                    continue
                conflict = await cls._find_existing_variant_by_code(db, norm_bc)
                if conflict is not None:
                    skipped.append({
                        "color_id": item.color_id,
                        "size_id": item.size_id,
                        "reason": f"Barcode '{norm_bc}' is already assigned to {conflict.sku}",
                    })
                    continue

            cost = item.cost_price if item.cost_price is not None else body.default_cost_price
            wholesale = item.wholesale_price if item.wholesale_price is not None else body.default_wholesale_price
            item_status = (item.status_code or body.status_code or "ACTIVE").upper()

            variant_body = PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA(
                sku=raw_sku,
                color_id=item.color_id,
                size_id=item.size_id,
                cost_price=cost,
                selling_price=selling,
                wholesale_price=wholesale,
                barcode=norm_bc,
                image_url=item.image_url,
                status_code=item_status,
                initial_stock=item.initial_stock,
                warehouse_id=body.warehouse_id,
            )
            variant = await cls._create_variant_internal(db, product, variant_body)
            existing.add(key)
            if variant.barcode:
                seen_barcodes.add(variant.barcode.lower())
            if variant.sku:
                seen_skus.add(variant.sku.lower())
            created.append(variant)

            if item.reorder_level is not None:
                wh_id = body.warehouse_id
                if not wh_id:
                    wh_id = (await db.execute(
                        select(Warehouse.id).order_by(Warehouse.is_default.desc()).limit(1)
                    )).scalar_one_or_none()
                if wh_id:
                    stock = await stock_repo.get_or_create_stock(variant.id, wh_id, lock=True)
                    stock.reorder_level = item.reorder_level

        if created:
            await cls.increment_catalog_version(db)
            await cls.increment_inventory_version(db)
        await db.commit()

        repo = ProductVariantRepository(db)
        loaded = [await repo.get_by_id(v.id) or v for v in created]
        return {"created": loaded, "skipped": skipped}

    @classmethod
    async def get_stock_matrix(
        cls,
        db: AsyncSession,
        product_id: UUID,
        warehouse_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Stock for one product laid out by color x size (optionally for a single warehouse)."""
        product = await ProductRepository(db).get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        variants = list(
            (await db.execute(
                select(ProductVariant)
                .where(ProductVariant.product_id == product_id)
                .order_by(ProductVariant.created_at)
            )).scalars().all()
        )
        variant_ids = [v.id for v in variants]

        stock_rows = []
        if variant_ids:
            stmt = select(InventoryStock).where(InventoryStock.variant_id.in_(variant_ids))
            if warehouse_id:
                stmt = stmt.where(InventoryStock.warehouse_id == warehouse_id)
            stock_rows = list((await db.execute(stmt)).scalars().all())

        wh_stmt = select(Warehouse).order_by(Warehouse.is_default.desc(), Warehouse.name)
        if warehouse_id:
            wh_stmt = wh_stmt.where(Warehouse.id == warehouse_id)
        warehouses = list((await db.execute(wh_stmt)).scalars().all())

        by_variant: Dict[UUID, List[InventoryStock]] = {}
        for row in stock_rows:
            by_variant.setdefault(row.variant_id, []).append(row)

        colors: Dict[Optional[UUID], Dict[str, Any]] = {}
        sizes: Dict[Optional[UUID], Dict[str, Any]] = {}
        cells: List[Dict[str, Any]] = []
        total = low = out = 0
        for v in variants:
            colors.setdefault(v.color_id, {
                "id": v.color_id,
                "name": v.color.name if v.color else "Default",
                "hex_code": v.color.hex_code if v.color else None,
            })
            sizes.setdefault(v.size_id, {
                "id": v.size_id,
                "name": v.size.name if v.size else "Default",
                "hex_code": None,
                "_sort": getattr(v.size, "sort_order", None) if v.size else None,
            })
            rows = by_variant.get(v.id, [])
            qty = sum(r.quantity for r in rows)
            reorder = sum(r.reorder_level for r in rows)
            if qty <= 0:
                state = "OUT"
                out += 1
            elif reorder > 0 and qty <= reorder:
                state = "LOW"
                low += 1
            else:
                state = "IN"
            total += qty
            cells.append({
                "variant_id": v.id,
                "sku": v.sku,
                "barcode": v.barcode,
                "color_id": v.color_id,
                "size_id": v.size_id,
                "status_code": v.status_code,
                "quantity": qty,
                "reorder_level": reorder,
                "stock_status": state,
                "by_warehouse": {str(r.warehouse_id): r.quantity for r in rows},
            })

        size_list = sorted(
            sizes.values(),
            key=lambda s: (s["_sort"] is None, s["_sort"] if s["_sort"] is not None else 0, s["name"]),
        )
        for s in size_list:
            s.pop("_sort", None)

        return {
            "product_id": product_id,
            "colors": sorted(colors.values(), key=lambda c: c["name"]),
            "sizes": size_list,
            "warehouses": [{"id": w.id, "name": w.name} for w in warehouses],
            "cells": cells,
            "total_quantity": total,
            "low_count": low,
            "out_count": out,
        }

    @classmethod
    async def delete_variant(cls, db: AsyncSession, variant_id: UUID) -> bool:
        """Delete a variant. Returns True if removed, False if only deactivated.

        A variant that still holds stock or has any stock movement history is never removed
        (that would destroy stock and break the audit trail); it is set INACTIVE instead.
        """
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")

        on_hand = (await db.execute(
            select(func.coalesce(func.sum(InventoryStock.quantity), 0))
            .where(InventoryStock.variant_id == variant_id)
        )).scalar_one()
        moves = (await db.execute(
            select(func.count()).select_from(InventoryMovement)
            .where(InventoryMovement.variant_id == variant_id)
        )).scalar_one()

        if on_hand > 0 or moves > 0:
            await repo.update(variant, status_code="INACTIVE")
            await cls.increment_catalog_version(db)
            await db.commit()
            return False

        await repo.delete(variant)
        await cls.increment_catalog_version(db)
        await db.commit()
        return True

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

        update_data = body.model_dump(exclude_unset=True)
        # Do not overwrite non-nullable fields with None
        for non_null_key in ("cost_price", "selling_price", "status_code"):
            if non_null_key in update_data and update_data[non_null_key] is None:
                update_data.pop(non_null_key)

        if "sku" in update_data:
            raw_sku = (update_data.get("sku") or "").strip().upper()
            if raw_sku and raw_sku.lower() != variant.sku.lower():
                sku_conflict = await cls._find_existing_variant_by_code(
                    db, raw_sku, exclude_variant_id=variant.id
                )
                if sku_conflict is not None:
                    raise CONFLICT_EXCEPTION(f"SKU '{raw_sku}' is already in use ({sku_conflict.sku})")
                update_data["sku"] = raw_sku
            else:
                update_data.pop("sku", None)

        new_color_id = update_data.get("color_id", variant.color_id)
        new_size_id  = update_data.get("size_id", variant.size_id)
        if new_color_id != variant.color_id or new_size_id != variant.size_id:
            dup_combo = await cls._find_existing_color_size_variant(
                db, variant.product_id, new_color_id, new_size_id, exclude_variant_id=variant.id
            )
            if dup_combo is not None:
                raise CONFLICT_EXCEPTION(
                    f"A variant with this color and size already exists for this product ({dup_combo.sku})"
                )

        if "barcode" in update_data:
            raw_bc = (update_data.get("barcode") or "").strip()
            if raw_bc:
                resolved_bc = normalize_scanned_code(raw_bc) or raw_bc
                conflict = await cls._find_existing_variant_by_code(
                    db, resolved_bc, exclude_variant_id=variant.id
                )
                if conflict is not None:
                    conflict_prod = conflict.product.name if getattr(conflict, "product", None) else "another product"
                    raise CONFLICT_EXCEPTION(
                        f"Barcode or QR code '{resolved_bc}' is already assigned to {conflict_prod} ({conflict.sku})"
                    )
                update_data["barcode"] = resolved_bc
            elif not variant.barcode:
                prod_code = variant.product.code if variant.product else "PROD-00001"
                b_seq = 1
                while True:
                    candidate = generate_compact_barcode(prod_code, b_seq)
                    if await cls._find_existing_variant_by_code(db, candidate, exclude_variant_id=variant.id) is None:
                        update_data["barcode"] = candidate
                        break
                    b_seq += 1
            else:
                # Keep current barcode if user submitted empty barcode on edit
                update_data.pop("barcode", None)

        variant = await repo.update(variant, **update_data)
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant

    @classmethod
    async def patch_variant_status(cls, db: AsyncSession, variant_id: UUID, status_code: str) -> ProductVariant:
        repo = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        clean_status = (status_code or "ACTIVE").strip().upper()
        variant = await repo.update(variant, status_code=clean_status)
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant

    @classmethod
    async def bulk_update_variants(
        cls,
        db: AsyncSession,
        product_id: UUID,
        body: PRODUCT_VARIANT_BULK_UPDATE_SCHEMA,
    ) -> List[ProductVariant]:
        repo = ProductVariantRepository(db)
        updated_list: List[ProductVariant] = []
        for item in body.items:
            variant = await repo.get_by_id(item.id)
            if not variant or variant.product_id != product_id:
                continue
            fields: Dict[str, Any] = {}
            if item.cost_price is not None:
                fields["cost_price"] = item.cost_price
            if item.selling_price is not None:
                fields["selling_price"] = item.selling_price
            if item.wholesale_price is not None:
                fields["wholesale_price"] = item.wholesale_price
            if item.status_code is not None:
                fields["status_code"] = item.status_code.strip().upper()
            if item.image_url is not None:
                fields["image_url"] = item.image_url.strip() or None
            if fields:
                variant = await repo.update(variant, **fields)
            updated_list.append(variant)
        if updated_list:
            await cls.increment_catalog_version(db)
            await db.commit()
        return [await repo.get_by_id(v.id) or v for v in updated_list]

    @classmethod
    async def regenerate_variant_codes(cls, db: AsyncSession, variant_id: UUID) -> ProductVariant:
        repo    = ProductVariantRepository(db)
        variant = await repo.get_by_id(variant_id)
        if not variant:
            raise NOT_FOUND_EXCEPTION("Variant not found")
        old_qr = variant.qr_reference
        old_bc = variant.barcode
        new_qr = await cls._generate_unique_qr_reference(db)
        update_kwargs: Dict[str, Any] = {"qr_reference": new_qr}
        if not variant.barcode:
            prod_code = variant.product.code if variant.product else "PROD-00001"
            b_seq = 1
            while True:
                candidate = generate_compact_barcode(prod_code, b_seq)
                if await cls._find_existing_variant_by_code(db, candidate, exclude_variant_id=variant.id) is None:
                    update_kwargs["barcode"] = candidate
                    break
                b_seq += 1
        variant = await repo.update(variant, **update_kwargs)
        from app.services.audit_service import AUDIT_SERVICE
        await AUDIT_SERVICE.record(
            db,
            action="VARIANT_CODES_REGENERATED",
            entity_type="product_variant",
            entity_id=variant.id,
            old_data={"sku": variant.sku, "qr_reference": old_qr, "barcode": old_bc},
            new_data={"sku": variant.sku, "qr_reference": variant.qr_reference, "barcode": variant.barcode},
        )
        await cls.increment_catalog_version(db)
        await db.commit()
        updated = await repo.get_by_id(variant.id)
        return updated or variant

    # ── Configurable Product Attributes ───────────────────────────────────────
    @classmethod
    async def list_product_attributes(cls, db: AsyncSession) -> List[ProductAttribute]:
        res = await db.execute(
            select(ProductAttribute)
            .where(ProductAttribute.status_code == "ACTIVE")
            .options(selectinload(ProductAttribute.values))
            .order_by(ProductAttribute.sort_order, ProductAttribute.name)
        )
        return list(res.scalars().all())

    @classmethod
    async def create_product_attribute(
        cls,
        db: AsyncSession,
        body: PRODUCT_ATTRIBUTE_CREATE_SCHEMA,
    ) -> ProductAttribute:
        clean_code = slugify(body.code or body.name, separator="_").lower()
        existing = await db.execute(
            select(ProductAttribute.id).where(func.lower(ProductAttribute.code) == clean_code)
        )
        if existing.scalar_one_or_none() is not None:
            raise CONFLICT_EXCEPTION(f"Attribute code '{clean_code}' already exists")

        attr = ProductAttribute(
            code=clean_code,
            name=body.name.strip(),
            display_name=(body.display_name or body.name).strip(),
            attribute_type=(body.attribute_type or "SELECT").upper(),
            sort_order=body.sort_order,
            status_code=body.status_code or "ACTIVE",
        )
        db.add(attr)
        await db.flush()

        for idx, val_in in enumerate(body.values or []):
            clean_val = val_in.value.strip().upper()
            if not clean_val:
                continue
            db.add(
                ProductAttributeValue(
                    attribute_id=attr.id,
                    value=clean_val,
                    display_value=(val_in.display_value or val_in.value).strip(),
                    sort_order=val_in.sort_order if val_in.sort_order else idx + 1,
                    status_code=val_in.status_code or "ACTIVE",
                )
            )
        await db.commit()
        res = await db.execute(
            select(ProductAttribute)
            .where(ProductAttribute.id == attr.id)
            .options(selectinload(ProductAttribute.values))
        )
        return res.scalar_one()

    @classmethod
    async def update_product_attribute(
        cls,
        db: AsyncSession,
        attribute_id: UUID,
        body: PRODUCT_ATTRIBUTE_UPDATE_SCHEMA,
    ) -> ProductAttribute:
        res = await db.execute(
            select(ProductAttribute)
            .where(ProductAttribute.id == attribute_id)
            .options(selectinload(ProductAttribute.values))
        )
        attr = res.scalar_one_or_none()
        if not attr:
            raise NOT_FOUND_EXCEPTION("Product attribute not found")

        for k, v in body.model_dump(exclude_none=True).items():
            setattr(attr, k, v)
        await db.commit()
        await db.refresh(attr)
        return attr

    @classmethod
    async def add_product_attribute_value(
        cls,
        db: AsyncSession,
        attribute_id: UUID,
        body: PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA,
    ) -> ProductAttributeValue:
        res = await db.execute(select(ProductAttribute).where(ProductAttribute.id == attribute_id))
        attr = res.scalar_one_or_none()
        if not attr:
            raise NOT_FOUND_EXCEPTION("Product attribute not found")

        clean_val = body.value.strip().upper()
        dup = await db.execute(
            select(ProductAttributeValue.id).where(
                ProductAttributeValue.attribute_id == attribute_id,
                func.lower(ProductAttributeValue.value) == clean_val.lower(),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise CONFLICT_EXCEPTION(f"Attribute value '{clean_val}' already exists")

        val_obj = ProductAttributeValue(
            attribute_id=attribute_id,
            value=clean_val,
            display_value=(body.display_value or body.value).strip(),
            sort_order=body.sort_order,
            status_code=body.status_code or "ACTIVE",
        )
        db.add(val_obj)
        await db.commit()
        await db.refresh(val_obj)
        return val_obj

    # ── Product Images Management ─────────────────────────────────────────────
    @classmethod
    async def add_product_image(
        cls,
        db: AsyncSession,
        product_id: UUID,
        body: PRODUCT_IMAGE_CREATE_SCHEMA,
    ) -> ProductImage:
        product = await ProductRepository(db).get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        existing = list(
            (await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))).scalars().all()
        )
        is_primary = bool(body.is_primary) or len(existing) == 0
        if is_primary:
            for ex in existing:
                ex.is_primary = False

        img = ProductImage(
            product_id=product_id,
            variant_id=body.variant_id,
            image_url=body.image_url.strip(),
            is_primary=is_primary,
            sort_order=body.sort_order if body.sort_order else len(existing),
            status_code="ACTIVE",
        )
        db.add(img)
        if is_primary:
            product.image_url = img.image_url
        await cls.increment_catalog_version(db)
        await db.commit()
        await db.refresh(img)
        return img

    @classmethod
    async def update_product_image(
        cls,
        db: AsyncSession,
        product_id: UUID,
        image_id: UUID,
        body: PRODUCT_IMAGE_UPDATE_SCHEMA,
    ) -> ProductImage:
        product = await ProductRepository(db).get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        res = await db.execute(
            select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id)
        )
        img = res.scalar_one_or_none()
        if not img:
            raise NOT_FOUND_EXCEPTION("Product image not found")

        if body.is_primary is True:
            others = list(
                (await db.execute(select(ProductImage).where(ProductImage.product_id == product_id))).scalars().all()
            )
            for o in others:
                o.is_primary = (o.id == image_id)
            product.image_url = img.image_url

        if body.sort_order is not None:
            img.sort_order = body.sort_order
        if "variant_id" in body.model_fields_set:
            img.variant_id = body.variant_id

        await cls.increment_catalog_version(db)
        await db.commit()
        await db.refresh(img)
        return img

    @classmethod
    async def delete_product_image(
        cls,
        db: AsyncSession,
        product_id: UUID,
        image_id: UUID,
    ) -> None:
        product = await ProductRepository(db).get_by_id(product_id)
        if not product:
            raise NOT_FOUND_EXCEPTION("Product not found")

        res = await db.execute(
            select(ProductImage).where(ProductImage.id == image_id, ProductImage.product_id == product_id)
        )
        img = res.scalar_one_or_none()
        if not img:
            raise NOT_FOUND_EXCEPTION("Product image not found")

        was_primary = img.is_primary
        await db.delete(img)
        await db.flush()

        remaining = list(
            (await db.execute(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.sort_order)
            )).scalars().all()
        )
        if was_primary:
            if remaining:
                remaining[0].is_primary = True
                product.image_url = remaining[0].image_url
            else:
                product.image_url = None

        await cls.increment_catalog_version(db)
        await db.commit()

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
