"""Product and variant repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.models import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db) -> None:
        super().__init__(Product, db)

    async def get_by_code(self, code: str) -> Product | None:
        result = await self.db.execute(select(Product).where(Product.code == code))
        return result.scalar_one_or_none()

    async def get_with_variants(self, id: UUID) -> Product | None:
        result = await self.db.execute(
            select(Product)
            .where(Product.id == id)
            .options(
                selectinload(Product.variants).selectinload(ProductVariant.color),
                selectinload(Product.variants).selectinload(ProductVariant.size),
                selectinload(Product.category),
                selectinload(Product.brand),
                selectinload(Product.supplier),
            )
        )
        return result.scalar_one_or_none()

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
                        Category.slug.ilike(cat_clean),
                        Category.name.ilike(cat_clean),
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
                        Brand.slug.ilike(brand_clean),
                        Brand.name.ilike(brand_clean),
                    )
                )

        need_variant_join = False
        if search:
            s_clean = search.strip()
            need_variant_join = True
            conditions.append(
                or_(
                    Product.name.ilike(f"%{s_clean}%"),
                    Product.code.ilike(f"%{s_clean}%"),
                    Product.description.ilike(f"%{s_clean}%"),
                    ProductVariant.sku.ilike(f"%{s_clean}%"),
                    ProductVariant.barcode.ilike(f"%{s_clean}%"),
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

        if include_stock or include_variants:
            var_options = [
                selectinload(Product.variants).selectinload(ProductVariant.color),
                selectinload(Product.variants).selectinload(ProductVariant.size),
            ]
            if include_stock:
                var_options.append(
                    selectinload(Product.variants).selectinload(ProductVariant.inventory_stocks)
                )
            stmt = stmt.options(*var_options)

        result = await self.db.execute(stmt)
        products = list(result.scalars().all())

        if include_stock:
            for p in products:
                stock_sum = 0
                for v in getattr(p, "variants", []):
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
        result = await self.db.execute(
            select(ProductVariant)
            .where(ProductVariant.sku == sku)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_barcode(self, barcode: str) -> ProductVariant | None:
        result = await self.db.execute(
            select(ProductVariant)
            .where(ProductVariant.barcode == barcode)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_qr_reference(self, qr_reference: str) -> ProductVariant | None:
        result = await self.db.execute(
            select(ProductVariant)
            .where(ProductVariant.qr_reference == qr_reference)
            .options(
                selectinload(ProductVariant.product).selectinload(Product.category),
                selectinload(ProductVariant.product).selectinload(Product.brand),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            )
        )
        return result.scalar_one_or_none()


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
            stmt = stmt.join(ProductVariant.product).where(
                or_(
                    ProductVariant.sku.ilike(f"%{q}%"),
                    ProductVariant.barcode.ilike(f"%{q}%"),
                    ProductVariant.qr_reference.ilike(f"%{q}%"),
                    Product.name.ilike(f"%{q}%"),
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


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db) -> None:
        super().__init__(Category, db)


class ColorRepository(BaseRepository[Color]):
    def __init__(self, db) -> None:
        super().__init__(Color, db)


class SizeRepository(BaseRepository[Size]):
    def __init__(self, db) -> None:
        super().__init__(Size, db)


class BrandRepository(BaseRepository[Brand]):
    def __init__(self, db) -> None:
        super().__init__(Brand, db)


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, db) -> None:
        super().__init__(Supplier, db)

    async def next_supplier_code(self) -> str:
        from sqlalchemy import text
        res = await self.db.execute(text("SELECT nextval('supplier_code_seq')"))
        seq = res.scalar_one()
        return f"SUP-{seq:05d}"
