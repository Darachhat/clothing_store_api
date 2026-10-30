"""Product catalog schemas."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema, UUIDSchema


# ── Color ─────────────────────────────────────────────────────────────────────
class ColorCreate(BaseSchema):
    name: str
    hex_code: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    status: str = "ACTIVE"


class ColorUpdate(BaseSchema):
    name: str | None = None
    hex_code: str | None = None
    status: str | None = None


class ColorOut(UUIDSchema):
    name: str
    hex_code: str | None
    status: str


# ── Size ──────────────────────────────────────────────────────────────────────
class SizeCreate(BaseSchema):
    name: str
    type: str = "LETTER"
    sort_order: int = 0
    status: str = "ACTIVE"


class SizeUpdate(BaseSchema):
    name: str | None = None
    type: str | None = None
    sort_order: int | None = None
    status: str | None = None


class SizeOut(UUIDSchema):
    name: str
    type: str
    sort_order: int
    status: str


# ── Category ─────────────────────────────────────────────────────────────────
class CategoryCreate(BaseSchema):
    name: str
    slug: str | None = None
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseSchema):
    name: str | None = None
    slug: str | None = None
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int | None = None
    status: str | None = None


class CategoryOut(UUIDSchema):
    name: str
    slug: str
    parent_id: UUID | None
    description: str | None
    status: str
    sort_order: int


# ── Brand ─────────────────────────────────────────────────────────────────────
class BrandCreate(BaseSchema):
    name: str
    slug: str | None = None
    description: str | None = None
    logo_url: str | None = None


class BrandUpdate(BaseSchema):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    logo_url: str | None = None
    status: str | None = None


class BrandOut(UUIDSchema):
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    status: str


# ── Supplier ──────────────────────────────────────────────────────────────────
class SupplierCreate(BaseSchema):
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    contact_person: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseSchema):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    contact_person: str | None = None
    notes: str | None = None
    status: str | None = None


class SupplierOut(UUIDSchema):
    code: str
    name: str
    phone: str | None
    email: str | None
    address: str | None
    contact_person: str | None
    status: str


# ── Product ───────────────────────────────────────────────────────────────────
class ProductCreate(BaseSchema):
    name: str
    description: str | None = None
    category_id: UUID | None = None
    brand_id: UUID | None = None
    supplier_id: UUID | None = None
    status: str = "ACTIVE"
    image_url: str | None = None


class ProductUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    brand_id: UUID | None = None
    supplier_id: UUID | None = None
    status: str | None = None
    image_url: str | None = None


class ProductOut(UUIDSchema):
    code: str
    name: str
    slug: str
    description: str | None
    category_id: UUID | None
    brand_id: UUID | None
    supplier_id: UUID | None
    status: str
    image_url: str | None
    category: CategoryOut | None = None
    brand: BrandOut | None = None
    total_stock: int | None = None


class PaginationMetadata(BaseSchema):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool = False
    has_previous: bool = False


class ProductPaginationResponse(BaseSchema):
    items: list[ProductOut]
    pagination: PaginationMetadata


class ProductWithVariants(ProductOut):
    brand: BrandOut | None = None
    variants: list["ProductVariantOut"] = []


class ProductPaginationWithVariantsResponse(BaseSchema):
    """Paginated product list that includes product variants (used by POS)."""
    items: list[ProductWithVariants]
    pagination: PaginationMetadata



# ── Product Variant ────────────────────────────────────────────────────────────
class ProductVariantCreate(BaseSchema):
    product_id: UUID
    color_id: UUID | None = None
    size_id: UUID | None = None
    cost_price: Decimal = Field(gt=0)
    selling_price: Decimal = Field(gt=0)
    wholesale_price: Decimal | None = None
    barcode: str | None = None
    weight_grams: int | None = None
    image_url: str | None = None
    status: str = "ACTIVE"


class ProductVariantUpdate(BaseSchema):
    cost_price: Decimal | None = None
    selling_price: Decimal | None = None
    wholesale_price: Decimal | None = None
    barcode: str | None = None
    weight_grams: int | None = None
    image_url: str | None = None
    status: str | None = None


class ProductVariantOut(UUIDSchema):
    product_id: UUID
    sku: str
    barcode: str | None
    qr_reference: str
    color_id: UUID | None
    size_id: UUID | None
    color: ColorOut | None = None
    size: SizeOut | None = None
    cost_price: Decimal
    selling_price: Decimal
    wholesale_price: Decimal | None
    weight_grams: int | None
    status: str
    image_url: str | None
    product: ProductOut | None = None
