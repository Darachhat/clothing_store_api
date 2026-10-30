"""Product catalog models: Category, Brand, Color, Size, Supplier, Product, ProductVariant."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.inventory import InventoryStock


class Category(UUIDBase):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    parent: Mapped[Category | None] = relationship("Category", remote_side="Category.id", back_populates="children")
    products: Mapped[list[Product]] = relationship("Product", back_populates="category")


class Brand(UUIDBase):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    products: Mapped[list[Product]] = relationship("Product", back_populates="brand")


class Color(UUIDBase):
    __tablename__ = "colors"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hex_code: Mapped[str | None] = mapped_column(String(7))  # #RRGGBB
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    variants: Mapped[list[ProductVariant]] = relationship("ProductVariant", back_populates="color")


class Size(UUIDBase):
    __tablename__ = "sizes"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="LETTER", nullable=False)
    # LETTER (S/M/L), NUMERIC (28/30/32), CUSTOM
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    variants: Mapped[list[ProductVariant]] = relationship("ProductVariant", back_populates="size")


class Supplier(UUIDBase):
    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    contact_person: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    products: Mapped[list[Product]] = relationship("Product", back_populates="supplier")


class Product(UUIDBase):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL")
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    # ACTIVE | INACTIVE | DISCONTINUED
    image_url: Mapped[str | None] = mapped_column(String(500))

    category: Mapped[Category | None] = relationship("Category", back_populates="products")
    brand: Mapped[Brand | None] = relationship("Brand", back_populates="products")
    supplier: Mapped[Supplier | None] = relationship("Supplier", back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )


class ProductVariant(UUIDBase):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "color_id", "size_id", name="uq_variant_product_color_size"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(200), unique=True, index=True)
    qr_reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    color_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("colors.id", ondelete="SET NULL")
    )
    size_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sizes.id", ondelete="SET NULL")
    )
    cost_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    wholesale_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    product: Mapped[Product] = relationship("Product", back_populates="variants")
    color: Mapped[Color | None] = relationship("Color", back_populates="variants")
    size: Mapped[Size | None] = relationship("Size", back_populates="variants")
    inventory_stocks: Mapped[list[InventoryStock]] = relationship(
        "InventoryStock", back_populates="variant"
    )


class CatalogVersion(Base):
    """
    Monotonically increasing version counter for the product catalog.
    PostgreSQL is the source of truth for version tracking and logical cache invalidation.
    """
    __tablename__ = "catalog_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    inventory_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def product_version(self) -> int:
        return self.version

    @product_version.setter
    def product_version(self, val: int) -> None:
        self.version = val

