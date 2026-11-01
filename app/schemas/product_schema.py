"""Product catalog schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, Field


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


class COLOR_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    hex_code         : Optional[str]      = None
    status           : str                = "ACTIVE"
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


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


class SIZE_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    type             : str
    sort_order       : int
    status           : str                = "ACTIVE"
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


# ── Category ─────────────────────────────────────────────────────────────────

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


class CATEGORY_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    slug             : str
    parent_id        : Optional[uuid.UUID] = None
    description      : Optional[str]       = None
    status           : str                 = "ACTIVE"
    status_code      : str                 = "ACTIVE"
    sort_order       : int                 = 0
    created_datetime : Optional[datetime]  = None
    updated_datetime : Optional[datetime]  = None
    created_at       : Optional[datetime]  = None
    updated_at       : Optional[datetime]  = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


# ── Brand ─────────────────────────────────────────────────────────────────────

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


class BRAND_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    slug             : str
    description      : Optional[str]      = None
    logo_url         : Optional[str]      = None
    status           : str                = "ACTIVE"
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


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


class SUPPLIER_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    code             : str
    name             : str
    phone            : Optional[str]      = None
    email            : Optional[str]      = None
    address          : Optional[str]      = None
    contact_person   : Optional[str]      = None
    status           : str                = "ACTIVE"
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


# ── Product ───────────────────────────────────────────────────────────────────

class PRODUCT_CREATE_SCHEMA(BaseModel):
    name        : str
    description : Optional[str]       = None
    category_id : Optional[uuid.UUID] = None
    brand_id    : Optional[uuid.UUID] = None
    supplier_id : Optional[uuid.UUID] = None
    status_code : str                 = "ACTIVE"
    image_url   : Optional[str]       = None

    model_config = {"from_attributes": True}


class PRODUCT_UPDATE_SCHEMA(BaseModel):
    name        : Optional[str]       = None
    description : Optional[str]       = None
    category_id : Optional[uuid.UUID] = None
    brand_id    : Optional[uuid.UUID] = None
    supplier_id : Optional[uuid.UUID] = None
    status_code : Optional[str]       = None
    image_url   : Optional[str]       = None

    model_config = {"from_attributes": True}


class PRODUCT_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    code             : str
    name             : str
    slug             : str
    description      : Optional[str]                      = None
    category_id      : Optional[uuid.UUID]                = None
    brand_id         : Optional[uuid.UUID]                = None
    supplier_id      : Optional[uuid.UUID]                = None
    status           : str                                = "ACTIVE"
    status_code      : str                                = "ACTIVE"
    image_url        : Optional[str]                      = None
    category         : Optional[CATEGORY_RESPONSE_SCHEMA] = None
    brand            : Optional[BRAND_RESPONSE_SCHEMA]    = None
    total_stock      : Optional[int]                      = None
    created_datetime : Optional[datetime]                 = None
    updated_datetime : Optional[datetime]                 = None
    created_at       : Optional[datetime]                 = None
    updated_at       : Optional[datetime]                 = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


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
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Decimal             = Field(gt=0)
    selling_price   : Decimal             = Field(gt=0)
    wholesale_price : Optional[Decimal]   = None
    barcode         : Optional[str]       = None
    weight_grams    : Optional[int]       = None
    image_url       : Optional[str]       = None
    status_code     : str                 = "ACTIVE"

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA(BaseModel):
    product_id      : Optional[uuid.UUID] = None
    color_id        : Optional[uuid.UUID] = None
    size_id         : Optional[uuid.UUID] = None
    cost_price      : Decimal             = Field(gt=0)
    selling_price   : Decimal             = Field(gt=0)
    wholesale_price : Optional[Decimal]   = None
    barcode         : Optional[str]       = None
    weight_grams    : Optional[int]       = None
    image_url       : Optional[str]       = None
    status_code     : str                 = "ACTIVE"

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_UPDATE_SCHEMA(BaseModel):
    cost_price      : Optional[Decimal] = None
    selling_price   : Optional[Decimal] = None
    wholesale_price : Optional[Decimal] = None
    barcode         : Optional[str]     = None
    weight_grams    : Optional[int]     = None
    image_url       : Optional[str]     = None
    status_code     : Optional[str]     = None

    model_config = {"from_attributes": True}


class PRODUCT_VARIANT_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    product_id       : uuid.UUID
    sku              : str
    barcode          : Optional[str]                     = None
    qr_reference     : str
    color_id         : Optional[uuid.UUID]               = None
    size_id          : Optional[uuid.UUID]               = None
    color            : Optional[COLOR_RESPONSE_SCHEMA]   = None
    size             : Optional[SIZE_RESPONSE_SCHEMA]    = None
    cost_price       : Decimal
    selling_price    : Decimal
    wholesale_price  : Optional[Decimal]                 = None
    weight_grams     : Optional[int]                     = None
    status           : str                               = "ACTIVE"
    status_code      : str                               = "ACTIVE"
    image_url        : Optional[str]                     = None
    product          : Optional[PRODUCT_RESPONSE_SCHEMA] = None
    created_datetime : Optional[datetime]                = None
    updated_datetime : Optional[datetime]                = None
    created_at       : Optional[datetime]                = None
    updated_at       : Optional[datetime]                = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class PRODUCT_WITH_VARIANTS_SCHEMA(PRODUCT_RESPONSE_SCHEMA):
    brand    : Optional[BRAND_RESPONSE_SCHEMA]           = None
    variants : List[PRODUCT_VARIANT_RESPONSE_SCHEMA]     = []


class PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA(BaseModel):
    """Paginated product list that includes product variants (used by POS)."""
    items      : List[PRODUCT_WITH_VARIANTS_SCHEMA]
    pagination : PAGINATION_METADATA_SCHEMA


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
    "PRODUCT_CREATE_SCHEMA",
    "PRODUCT_UPDATE_SCHEMA",
    "PRODUCT_RESPONSE_SCHEMA",
    "PAGINATION_METADATA_SCHEMA",
    "PRODUCT_PAGINATION_RESPONSE_SCHEMA",
    "PRODUCT_WITH_VARIANTS_SCHEMA",
    "PRODUCT_PAGINATION_WITH_VARIANTS_RESPONSE_SCHEMA",
    "PRODUCT_VARIANT_CREATE_SCHEMA",
    "PRODUCT_VARIANT_CREATE_FOR_PRODUCT_SCHEMA",
    "PRODUCT_VARIANT_UPDATE_SCHEMA",
    "PRODUCT_VARIANT_RESPONSE_SCHEMA",
]

