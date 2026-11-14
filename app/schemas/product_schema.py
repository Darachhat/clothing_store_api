"""Product catalog schemas."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic.main import BaseModel
from pydantic import Field

from app.schemas.base_schema import BASE_AUDIT_RESPONSE_SCHEMA


# ── Color ─────────────────────────────────────────────────────────────────────

class COLOR_CREATE_SCHEMA(BaseModel):
    name        : str
    hex_code    : Optional[str] = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    status_code : str           = "ACTIVE"

    model_config = {"from_attributes": True}


class COLOR_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str] = None
    hex_code    : Optional[str] = None
    status_code : Optional[str] = None

    model_config = {"from_attributes": True}


class COLOR_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    name     : str
    hex_code : Optional[str] = None


# ── Size ──────────────────────────────────────────────────────────────────────

class SIZE_CREATE_SCHEMA(BaseModel):
    name        : str
    type        : str = "LETTER"
    sort_order  : int = 0
    status_code : str = "ACTIVE"

    model_config = {"from_attributes": True}


class SIZE_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str] = None
    type        : Optional[str] = None
    sort_order  : Optional[int] = None
    status_code : Optional[str] = None

    model_config = {"from_attributes": True}


class SIZE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    name       : str
    type       : str
    sort_order : int


# ── CATEGORY_MODEL ─────────────────────────────────────────────────────────────────

class CATEGORY_CREATE_SCHEMA(BaseModel):
    name        : str
    slug        : Optional[str]       = None
    parent_id   : Optional[uuid.UUID] = None
    description : Optional[str]       = None
    sort_order  : int                 = 0
    status_code : str                 = "ACTIVE"

    model_config = {"from_attributes": True}


class CATEGORY_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str]       = None
    slug        : Optional[str]       = None
    parent_id   : Optional[uuid.UUID] = None
    description : Optional[str]       = None
    sort_order  : Optional[int]       = None
    status_code : Optional[str]       = None

    model_config = {"from_attributes": True}


class CATEGORY_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    name        : str
    slug        : str
    parent_id   : Optional[uuid.UUID] = None
    description : Optional[str]       = None
    sort_order  : int                 = 0


# ── BRAND_MODEL ─────────────────────────────────────────────────────────────────────

class BRAND_CREATE_SCHEMA(BaseModel):
    name        : str
    slug        : Optional[str] = None
    description : Optional[str] = None
    logo_url    : Optional[str] = None
    status_code : str           = "ACTIVE"

    model_config = {"from_attributes": True}


class BRAND_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str] = None
    slug        : Optional[str] = None
    description : Optional[str] = None
    logo_url    : Optional[str] = None
    status_code : Optional[str] = None

    model_config = {"from_attributes": True}


class BRAND_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    name        : str
    slug        : str
    description : Optional[str] = None
    logo_url    : Optional[str] = None


# ── Supplier ──────────────────────────────────────────────────────────────────

class SUPPLIER_CREATE_SCHEMA(BaseModel):
    name           : str
    phone          : Optional[str] = None
    email          : Optional[str] = None
    address        : Optional[str] = None
    contact_person : Optional[str] = None
    notes          : Optional[str] = None
    status_code    : str           = "ACTIVE"

    model_config = {"from_attributes": True}


class SUPPLIER_UPDATE_SCHEMA(BaseModel):
    name           : Optional[str] = None
    phone          : Optional[str] = None
    email          : Optional[str] = None
    address        : Optional[str] = None
    contact_person : Optional[str] = None
    notes          : Optional[str] = None
    status_code    : Optional[str] = None

    model_config = {"from_attributes": True}


class SUPPLIER_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    code           : str
    name           : str
    phone          : Optional[str] = None
    email          : Optional[str] = None
    address        : Optional[str] = None
    contact_person : Optional[str] = None


# ── Product Attributes & Images ───────────────────────────────────────────────

class PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA(BaseModel):
    value         : str
    display_value : Optional[str] = None
    sort_order    : int           = 0
    status_code   : str           = "ACTIVE"

    model_config = {"from_attributes": True}


class PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    attribute_id  : uuid.UUID
    value         : str
    display_value : str
    sort_order    : int = 0


class PRODUCT_ATTRIBUTE_CREATE_SCHEMA(BaseModel):
    code           : Optional[str]                                       = None
    name           : str
    display_name   : Optional[str]                                       = None
    attribute_type : str                                                 = "SELECT"
    sort_order     : int                                                 = 0
    status_code    : str                                                 = "ACTIVE"
    values         : Optional[List[PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA]] = None

    model_config = {"from_attributes": True}


class PRODUCT_ATTRIBUTE_UPDATE_SCHEMA(BaseModel):
    name           : Optional[str] = None
    display_name   : Optional[str] = None
    attribute_type : Optional[str] = None
    sort_order     : Optional[int] = None
    status_code    : Optional[str] = None

    model_config = {"from_attributes": True}


class PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    code           : str
    name           : str
    display_name   : str
    attribute_type : str                                           = "SELECT"
    sort_order     : int                                           = 0
    values         : List[PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA] = []


class PRODUCT_ATTRIBUTE_ASSIGNMENT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    product_id             : uuid.UUID
    attribute_id           : uuid.UUID
    attribute_value_id     : uuid.UUID
    attribute_name         : Optional[str]                               = None
    attribute_display_name : Optional[str]                               = None
    value                  : Optional[str]                               = None
    display_value          : Optional[str]                               = None
    attribute              : Optional[PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA]       = None
    attribute_value        : Optional[PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA] = None


class PRODUCT_IMAGE_CREATE_SCHEMA(BaseModel):
    image_url  : str
    variant_id : Optional[uuid.UUID] = None
    is_primary : bool                = False
    sort_order : int                 = 0

    model_config = {"from_attributes": True}


class PRODUCT_IMAGE_UPDATE_SCHEMA(BaseModel):
    variant_id : Optional[uuid.UUID] = None
    is_primary : Optional[bool]      = None
    sort_order : Optional[int]       = None

    model_config = {"from_attributes": True}


class PRODUCT_IMAGE_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    product_id : uuid.UUID
    variant_id : Optional[uuid.UUID] = None
    image_url  : str
    is_primary : bool                = False
    sort_order : int                 = 0


# ── Product ───────────────────────────────────────────────────────────────────

class PRODUCT_CREATE_SCHEMA(BaseModel):
    name                : str
    code                : Optional[str]                                       = None
    description         : Optional[str]                                       = None
    category_id         : Optional[uuid.UUID]                                 = None
    brand_id            : Optional[uuid.UUID]                                 = None
    supplier_id         : Optional[uuid.UUID]                                 = None
    status_code         : str                                                 = "ACTIVE"
    image_url           : Optional[str]                                       = None
    tags                : Optional[List[str]]                                 = None
    images              : Optional[List[PRODUCT_IMAGE_CREATE_SCHEMA]]         = None
    attribute_value_ids : Optional[List[uuid.UUID]]                           = None
    initial_variant     : Optional[PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA] = None
    variants            : Optional[List[PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA]] = None

    model_config = {"from_attributes": True}


class PRODUCT_UPDATE_SCHEMA(BaseModel):
    name                : Optional[str]                               = None
    code                : Optional[str]                               = None
    description         : Optional[str]                               = None
    category_id         : Optional[uuid.UUID]                         = None
    brand_id            : Optional[uuid.UUID]                         = None
    supplier_id         : Optional[uuid.UUID]                         = None
    status_code         : Optional[str]                               = None
    image_url           : Optional[str]                               = None
    tags                : Optional[List[str]]                         = None
    images              : Optional[List[PRODUCT_IMAGE_CREATE_SCHEMA]] = None
    attribute_value_ids : Optional[List[uuid.UUID]]                   = None

    model_config = {"from_attributes": True}


class PRODUCT_BULK_ARCHIVE_SCHEMA(BaseModel):
    product_ids : List[uuid.UUID] = Field(min_length=1, max_length=200)


class PRODUCT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    code                  : str
    name                  : str
    slug                  : str
    description           : Optional[str]                                      = None
    category_id           : Optional[uuid.UUID]                                = None
    brand_id              : Optional[uuid.UUID]                                = None
    supplier_id           : Optional[uuid.UUID]                                = None
    image_url             : Optional[str]                                      = None
    tags                  : List[str]                                          = []
    category              : Optional[CATEGORY_RESPONSE_SCHEMA]                 = None
    brand                 : Optional[BRAND_RESPONSE_SCHEMA]                    = None
    images                : List[PRODUCT_IMAGE_RESPONSE_SCHEMA]                = []
    attribute_assignments : List[PRODUCT_ATTRIBUTE_ASSIGNMENT_RESPONSE_SCHEMA] = []
    total_stock           : Optional[int]                                      = None
    variant_count         : Optional[int]                                      = None
    min_price             : Optional[Decimal]                                  = None
    max_price             : Optional[Decimal]                                  = None


class PAGINATION_METADATA_SCHEMA(BaseModel):
    page         : int
    page_size    : int
    total        : int
    total_pages  : int
    has_next     : bool = False
    has_previous : bool = False


class PRODUCT_PAGINATION_RESPONSE_SCHEMA(BaseModel):
    items      : List[PRODUCT_RESPONSE_SCHEMA]
    pagination : PAGINATION_METADATA_SCHEMA


# ── Product Variant ────────────────────────────────────────────────────────────

class PRODUCT_VARIANT_CREATE_SCHEMA(BaseModel):
    product_id      : uuid.UUID
    sku             : Optional[str]       = None
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Decimal             = Field(default=Decimal("0.00"), ge=0)
    selling_price   : Decimal             = Field(gt=0)
    wholesale_price : Optional[Decimal]   = None
    barcode         : Optional[str]       = None
    weight_grams    : Optional[int]       = None
    image_url       : Optional[str]       = None
    status_code     : str                 = "ACTIVE"
    initial_stock   : int                 = Field(default=0, ge=0)
    warehouse_id    : Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA(BaseModel):
    product_id      : Optional[uuid.UUID] = None
    sku             : Optional[str]       = None
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Decimal             = Field(default=Decimal("0.00"), ge=0)
    selling_price   : Decimal             = Field(gt=0)
    wholesale_price : Optional[Decimal]   = None
    barcode         : Optional[str]       = None
    weight_grams    : Optional[int]       = None
    image_url       : Optional[str]       = None
    status_code     : str                 = "ACTIVE"
    initial_stock   : int                 = Field(default=0, ge=0)
    warehouse_id    : Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_UPDATE_SCHEMA(BaseModel):
    sku             : Optional[str]       = None
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Optional[Decimal]   = None
    selling_price   : Optional[Decimal]   = None
    wholesale_price : Optional[Decimal]   = None
    barcode         : Optional[str]       = None
    weight_grams    : Optional[int]       = None
    image_url       : Optional[str]       = None
    status_code     : Optional[str]       = None

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_STATUS_PATCH_SCHEMA(BaseModel):
    status_code : str


class PRODUCT_VARIANT_RESPONSE_SCHEMA(BASE_AUDIT_RESPONSE_SCHEMA):
    product_id      : uuid.UUID
    sku             : str
    barcode         : Optional[str]                     = None
    qr_reference    : str
    color_id        : Optional[uuid.UUID]               = None
    size_id         : Optional[uuid.UUID]               = None
    color           : Optional[COLOR_RESPONSE_SCHEMA]   = None
    size            : Optional[SIZE_RESPONSE_SCHEMA]    = None
    cost_price      : Decimal
    selling_price   : Decimal
    wholesale_price : Optional[Decimal]                 = None
    weight_grams    : Optional[int]                     = None
    image_url       : Optional[str]                     = None
    product         : Optional[PRODUCT_RESPONSE_SCHEMA] = None


class PRODUCT_VARIANT_BULK_ITEM_SCHEMA(BaseModel):
    sku             : Optional[str]       = None
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Optional[Decimal]   = Field(default=None, ge=0)
    selling_price   : Optional[Decimal]   = Field(default=None, gt=0)
    wholesale_price : Optional[Decimal]   = Field(default=None, ge=0)
    barcode         : Optional[str]       = None
    image_url       : Optional[str]       = None
    status_code     : Optional[str]       = None
    initial_stock   : int                 = Field(default=0, ge=0, le=1_000_000)
    reorder_level   : Optional[int]       = Field(default=None, ge=0, le=1_000_000)


class PRODUCT_VARIANT_BULK_CREATE_SCHEMA(BaseModel):
    """Create many color x size variants (and their opening stock) in one transaction.

    Item-level prices fall back to the defaults here. Combinations that already exist are skipped.
    """
    items                   : List[PRODUCT_VARIANT_BULK_ITEM_SCHEMA] = Field(min_length=1, max_length=300)
    default_cost_price      : Decimal             = Field(default=Decimal("0.00"), ge=0)
    default_selling_price   : Optional[Decimal]   = Field(default=None, gt=0)
    default_wholesale_price : Optional[Decimal]   = Field(default=None, ge=0)
    warehouse_id            : Optional[uuid.UUID] = None
    status_code             : str                 = "ACTIVE"


class PRODUCT_VARIANT_BULK_SKIPPED_SCHEMA(BaseModel):
    color_id : Optional[uuid.UUID] = None
    size_id  : Optional[uuid.UUID] = None
    reason   : str


class PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA(BaseModel):
    created : List[PRODUCT_VARIANT_RESPONSE_SCHEMA]
    skipped : List[PRODUCT_VARIANT_BULK_SKIPPED_SCHEMA] = []


class PRODUCT_VARIANT_BULK_UPDATE_ITEM_SCHEMA(BaseModel):
    id              : uuid.UUID
    cost_price      : Optional[Decimal] = Field(default=None, ge=0)
    selling_price   : Optional[Decimal] = Field(default=None, gt=0)
    wholesale_price : Optional[Decimal] = Field(default=None, ge=0)
    status_code     : Optional[str]     = None
    image_url       : Optional[str]     = None


class PRODUCT_VARIANT_BULK_UPDATE_SCHEMA(BaseModel):
    items           : Optional[List[PRODUCT_VARIANT_BULK_UPDATE_ITEM_SCHEMA]] = None
    variant_ids     : Optional[List[uuid.UUID]]                               = None
    cost_price      : Optional[Decimal]                                       = Field(default=None, ge=0)
    selling_price   : Optional[Decimal]                                       = Field(default=None, gt=0)
    wholesale_price : Optional[Decimal]                                       = Field(default=None, ge=0)
    status_code     : Optional[str]                                           = None


class PRODUCT_WITH_VARIANTS_SCHEMA(PRODUCT_RESPONSE_SCHEMA):
    brand    : Optional[BRAND_RESPONSE_SCHEMA]           = None
    variants : List[PRODUCT_VARIANT_RESPONSE_SCHEMA]     = []


class PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA(BaseModel):
    """Paginated product list that includes product variants (used by POS)."""
    items      : List[PRODUCT_WITH_VARIANTS_SCHEMA]
    pagination : PAGINATION_METADATA_SCHEMA


class VARIANT_SCAN_RESPONSE_SCHEMA(BaseModel):
    """Unified scan lookup response for 1D Barcode, 2D QR Code, SKU, or Product Code."""
    match_type      : str  # "variant" | "product"
    normalized_code : str
    variant         : Optional[PRODUCT_VARIANT_RESPONSE_SCHEMA] = None
    product         : Optional[PRODUCT_WITH_VARIANTS_SCHEMA]    = None
    variants        : List[PRODUCT_VARIANT_RESPONSE_SCHEMA]     = []
    total_stock     : int                                       = 0

    model_config = {"from_attributes": True}


__all__ = [
    "COLOR_CREATE_SCHEMA",
    "COLOR_UPDATE_SCHEMA",
    "COLOR_RESPONSE_SCHEMA",
    "SIZE_CREATE_SCHEMA",
    "SIZE_UPDATE_SCHEMA",
    "SIZE_RESPONSE_SCHEMA",
    "CATEGORY_CREATE_SCHEMA",
    "CATEGORY_UPDATE_SCHEMA",
    "CATEGORY_RESPONSE_SCHEMA",
    "BRAND_CREATE_SCHEMA",
    "BRAND_UPDATE_SCHEMA",
    "BRAND_RESPONSE_SCHEMA",
    "SUPPLIER_CREATE_SCHEMA",
    "SUPPLIER_UPDATE_SCHEMA",
    "SUPPLIER_RESPONSE_SCHEMA",
    "PRODUCT_ATTRIBUTE_VALUE_CREATE_SCHEMA",
    "PRODUCT_ATTRIBUTE_VALUE_RESPONSE_SCHEMA",
    "PRODUCT_ATTRIBUTE_CREATE_SCHEMA",
    "PRODUCT_ATTRIBUTE_UPDATE_SCHEMA",
    "PRODUCT_ATTRIBUTE_RESPONSE_SCHEMA",
    "PRODUCT_ATTRIBUTE_ASSIGNMENT_RESPONSE_SCHEMA",
    "PRODUCT_IMAGE_CREATE_SCHEMA",
    "PRODUCT_IMAGE_UPDATE_SCHEMA",
    "PRODUCT_IMAGE_RESPONSE_SCHEMA",
    "PRODUCT_CREATE_SCHEMA",
    "PRODUCT_UPDATE_SCHEMA",
    "PRODUCT_BULK_ARCHIVE_SCHEMA",
    "PRODUCT_RESPONSE_SCHEMA",
    "PAGINATION_METADATA_SCHEMA",
    "PRODUCT_PAGINATION_RESPONSE_SCHEMA",
    "PRODUCT_WITH_VARIANTS_SCHEMA",
    "PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA",
    "PRODUCT_VARIANT_CREATE_SCHEMA",
    "PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA",
    "PRODUCT_VARIANT_UPDATE_SCHEMA",
    "PRODUCT_VARIANT_STATUS_PATCH_SCHEMA",
    "PRODUCT_VARIANT_RESPONSE_SCHEMA",
    "PRODUCT_VARIANT_BULK_ITEM_SCHEMA",
    "PRODUCT_VARIANT_BULK_CREATE_SCHEMA",
    "PRODUCT_VARIANT_BULK_SKIPPED_SCHEMA",
    "PRODUCT_VARIANT_BULK_RESPONSE_SCHEMA",
    "PRODUCT_VARIANT_BULK_UPDATE_ITEM_SCHEMA",
    "PRODUCT_VARIANT_BULK_UPDATE_SCHEMA",
    "VARIANT_SCAN_RESPONSE_SCHEMA",
]
