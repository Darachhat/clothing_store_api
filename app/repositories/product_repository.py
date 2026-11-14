"""Product and variant repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models import (
    BRAND_MODEL,
    CATEGORY_MODEL,
    Color,
    Product,
    ProductAttributeAssignment,
    ProductVariant,
    Size,
    Supplier,
)
from app.repositories.base import BaseRepository
from app.utils.codes import normalize_scanned_code


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db) -> None:
        super().__init__(Product, db)

    async def get_by_code(self, code: str) -> Product | None:
        clean = normalize_scanned_code(code)
        if not clean:
            return None
        result = await self.db.execute(
            select(Product)
            .where(func.lower(Product.code) == clean.lower())
            .options(
                selectinload(Product.variants).selectinload(ProductVariant.color),
                selectinload(Product.variants).selectinload(ProductVariant.size),
                selectinload(Product.variants).selectinload(ProductVariant.inventory_stocks),
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.supplier),
            )
        )
        return result.scalar_one_or_none()

    async def get_with_variants(self, id: UUID) -> Product | None:
        result = await self.db.execute(
            select(Product)
            .where(Product.id == id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(Product.variants).selectinload(ProductVariant.color),
                selectinload(Product.variants).selectinload(ProductVariant.size),
                selectinload(Product.images),
                selectinload(Product.attribute_assignments).selectinload(ProductAttributeAssignment.attribute),
                selectinload(Product.attribute_assignments).selectinload(ProductAttributeAssignment.attribute_value),
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.supplier),
            )
        )
        p = result.scalar_one_or_none()
        if p is not None:
            v_list = getattr(p, "variants", []) or []
            p.variant_count = len(v_list)
            prices = [v.selling_price for v in v_list if getattr(v, "selling_price", None) is not None]
            p.min_price = min(prices) if prices else None
            p.max_price = max(prices) if prices else None
        return p

    async def search(
        self,
        q: str | None = None,
        category_id: UUID | None = None,
        brand_id: UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Product]:
        stmt = select(Product)
        if q:
            stmt = stmt.where(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Product.code.ilike(f"%{q}%"),
                )
            )
        if category_id:
            stmt = stmt.where(Product.category_id == category_id)
        if brand_id:
            stmt = stmt.where(Product.brand_id == brand_id)
        if status:
            stmt = stmt.where(Product.status == status)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_paginated(
        self,
        page: int = 1,
        page_size: int = 24,
        search: str | None = None,
        category: str | None = None,
        category_id: UUID | None = None,
        brand: str | None = None,
        brand_id: UUID | None = None,
        status: str | None = "ACTIVE",
        sort: str = "created_at",
        sort_direction: str = "desc",
        branch_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        include_stock: bool = False,
        include_variants: bool = False,
    ) -> tuple[list[Product], int]:
        """Paginated product search with rich filtering, stock rollup, and optional variant loading."""
        from sqlalchemy import asc, desc, distinct, func

        conditions = []

        if status and status.upper() != "ALL":
            conditions.append(Product.status == status.upper())

        need_category_join = False
        if category_id:
            conditions.append(Product.category_id == category_id)
        elif category:
            cat_clean = category.strip()
            try:
                cat_uuid = UUID(cat_clean)
                conditions.append(Product.category_id == cat_uuid)
            except ValueError:
                need_category_join = True
                conditions.append(
                    or_(
                        CATEGORY_MODEL.slug.ilike(cat_clean),
                        CATEGORY_MODEL.name.ilike(cat_clean),
                    )
                )

        need_brand_join = False
        if brand_id:
            conditions.append(Product.brand_id == brand_id)
        elif brand:
            brand_clean = brand.strip()
            try:
                brand_uuid = UUID(brand_clean)
                conditions.append(Product.brand_id == brand_uuid)
            except ValueError:
                need_brand_join = True
                conditions.append(
                    or_(
                        BRAND_MODEL.slug.ilike(brand_clean),
                        BRAND_MODEL.name.ilike(brand_clean),
                    )
                )

        need_variant_join = False
        if search:
            s_raw = search.strip()
            s_norm = normalize_scanned_code(s_raw)
            s_clean = s_norm or s_raw
            need_variant_join = True
            conditions.append(
                or_(
                    Product.name.ilike(f"%{s_clean}%"),
                    Product.code.ilike(f"%{s_clean}%"),
                    Product.description.ilike(f"%{s_clean}%"),
                    ProductVariant.sku.ilike(f"%{s_clean}%"),
                    ProductVariant.barcode.ilike(f"%{s_clean}%"),
                    ProductVariant.qr_reference.ilike(f"%{s_clean}%"),
                )
            )

        # Count Query
        count_stmt = select(func.count(distinct(Product.id))).select_from(Product)
        if need_category_join:
            count_stmt = count_stmt.join(Product.category)
        if need_brand_join:
            count_stmt = count_stmt.join(Product.brand)
        if need_variant_join:
            count_stmt = count_stmt.outerjoin(Product.variants)
        if conditions:
            count_stmt = count_stmt.where(*conditions)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one()

        # Data Query
        stmt = (
            select(Product)
            .distinct()
            .options(
                selectinload(Product.category),
                selectinload(Product.brand),
            )
        )
        if need_category_join:
            stmt = stmt.join(Product.category)
        if need_brand_join:
            stmt = stmt.join(Product.brand)
        if need_variant_join:
            stmt = stmt.outerjoin(Product.variants)
        if conditions:
            stmt = stmt.where(*conditions)

        # Sort order
        direction = desc if sort_direction.lower() == "desc" else asc
        if sort == "name":
            sort_col = Product.name
        elif sort == "code":
            sort_col = Product.code
        elif sort == "status":
            sort_col = Product.status
        else:
            sort_col = Product.created_at

        stmt = stmt.order_by(direction(sort_col), Product.id)

        offset = max(0, (page - 1) * page_size)
        stmt = stmt.offset(offset).limit(page_size)

        var_options = [
            selectinload(Product.variants).selectinload(ProductVariant.color),
            selectinload(Product.variants).selectinload(ProductVariant.size),
            selectinload(Product.images),
            selectinload(Product.attribute_assignments),
        ]
        if include_stock:
            var_options.append(
                selectinload(Product.variants).selectinload(ProductVariant.inventory_stocks)
            )
        stmt = stmt.options(*var_options)

        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        for p in products:
            v_list = getattr(p, "variants", []) or []
            p.variant_count = len(v_list)
            prices = [v.selling_price for v in v_list if getattr(v, "selling_price", None) is not None]
            p.min_price = min(prices) if prices else None
            p.max_price = max(prices) if prices else None
            if include_stock:
                stock_sum = 0
                for v in v_list:
                    for st in getattr(v, "inventory_stocks", []):
                        if warehouse_id and st.warehouse_id != warehouse_id:
                            continue
                        stock_sum += st.quantity
                p.total_stock = stock_sum

        return products, total


class ProductVariantRepository(BaseRepository[ProductVariant]):
    def __init__(self, db) -> None:
        super().__init__(ProductVariant, db)

    async def get_by_id(self, id: UUID) -> ProductVariant | None:
        result = await self.db.execute(
            select(ProductVariant)
            .where(ProductVariant.id == id)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> ProductVariant | None:
        clean = normalize_scanned_code(sku)
        if not clean:
            return None
        result = await self.db.execute(
            select(ProductVariant)
            .where(func.lower(ProductVariant.sku) == clean.lower())
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
                selectinload(ProductVariant.inventory_stocks),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_barcode(self, barcode: str) -> ProductVariant | None:
        clean = normalize_scanned_code(barcode)
        if not clean:
            return None
        result = await self.db.execute(
            select(ProductVariant)
            .where(func.lower(ProductVariant.barcode) == clean.lower())
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
                selectinload(ProductVariant.inventory_stocks),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_qr_reference(self, qr_reference: str) -> ProductVariant | None:
        clean = normalize_scanned_code(qr_reference)
        if not clean:
            return None
        result = await self.db.execute(
            select(ProductVariant)
            .where(func.lower(ProductVariant.qr_reference) == clean.lower())
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
                selectinload(ProductVariant.inventory_stocks),
            )
        )
        return result.scalar_one_or_none()

    async def lookup_by_any_code(self, code: str) -> ProductVariant | None:
        """
        Single-roundtrip lookup matching barcode, SKU, or QR reference (case-insensitive)
        after canonical URL/scanner normalization.
        """
        clean = normalize_scanned_code(code)
        if not clean:
            return None
        clean_lower = clean.lower()
        result = await self.db.execute(
            select(ProductVariant)
            .where(
                or_(
                    func.lower(ProductVariant.barcode) == clean_lower,
                    func.lower(ProductVariant.sku) == clean_lower,
                    func.lower(ProductVariant.qr_reference) == clean_lower,
                )
            )
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
                selectinload(ProductVariant.inventory_stocks),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def search(
        self,
        q: str | None = None,
        product_id: UUID | None = None,
        color_id: UUID | None = None,
        size_id: UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ProductVariant]:
        stmt = select(ProductVariant).options(
            selectinload(ProductVariant.product).selectinload(Product.category),
            selectinload(ProductVariant.product).selectinload(Product.brand),
            selectinload(ProductVariant.color),
            selectinload(ProductVariant.size),
        )
        if q:
            q_clean = normalize_scanned_code(q) or q.strip()
            stmt = stmt.join(ProductVariant.product).where(
                or_(
                    ProductVariant.sku.ilike(f"%{q_clean}%"),
                    ProductVariant.barcode.ilike(f"%{q_clean}%"),
                    ProductVariant.qr_reference.ilike(f"%{q_clean}%"),
                    Product.name.ilike(f"%{q_clean}%"),
                    Product.code.ilike(f"%{q_clean}%"),
                )
            )
        if product_id:
            stmt = stmt.where(ProductVariant.product_id == product_id)
        if color_id:
            stmt = stmt.where(ProductVariant.color_id == color_id)
        if size_id:
            stmt = stmt.where(ProductVariant.size_id == size_id)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class CategoryRepository(BaseRepository[CATEGORY_MODEL]):
    def __init__(self, db) -> None:
        super().__init__(CATEGORY_MODEL, db)


class ColorRepository(BaseRepository[Color]):
    def __init__(self, db) -> None:
        super().__init__(Color, db)


class SizeRepository(BaseRepository[Size]):
    def __init__(self, db) -> None:
        super().__init__(Size, db)


class BrandRepository(BaseRepository[BRAND_MODEL]):
    def __init__(self, db) -> None:
        super().__init__(BRAND_MODEL, db)


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, db) -> None:
        super().__init__(Supplier, db)

    async def next_supplier_code(self) -> str:
        from sqlalchemy import text
        res = await self.db.execute(text("SELECT nextval('supplier_code_seq')"))
        seq = res.scalar_one()
        return f"SUP-{seq:05d}"
