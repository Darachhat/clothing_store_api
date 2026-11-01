"""Inventory schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


class INVENTORY_STOCK_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    variant_id       : uuid.UUID
    warehouse_id     : uuid.UUID
    quantity         : int
    reorder_level    : int
    sku              : Optional[str]      = None
    variant          : Optional[Any]      = None
    warehouse        : Optional[Any]      = None
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

    @model_validator(mode="after")
    def populate_sku(self) -> "INVENTORY_STOCK_RESPONSE_SCHEMA":
        if self.variant is not None and not isinstance(self.variant, dict):
            v = self.variant
            self.variant = {
                "id": str(getattr(v, "id", "")),
                "product_id": str(getattr(v, "product_id", "")),
                "sku": getattr(v, "sku", None),
                "barcode": getattr(v, "barcode", None),
                "qr_reference": getattr(v, "qr_reference", None),
                "selling_price": float(getattr(v, "selling_price", 0) or 0),
                "cost_price": float(getattr(v, "cost_price", 0) or 0),
            }
        if self.warehouse is not None and not isinstance(self.warehouse, dict):
            w = self.warehouse
            self.warehouse = {
                "id": str(getattr(w, "id", "")),
                "name": getattr(w, "name", None),
                "branch_id": str(getattr(w, "branch_id", "")),
            }
        if not self.sku and isinstance(self.variant, dict):
            self.sku = self.variant.get("sku")
        return self


class INVENTORY_MOVEMENT_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    variant_id       : uuid.UUID
    warehouse_id     : uuid.UUID
    movement_type    : str
    quantity         : int
    before_quantity  : int
    after_quantity   : int
    reference_type   : Optional[str]       = None
    reference_id     : Optional[uuid.UUID] = None
    note             : Optional[str]       = None
    created_by       : Optional[Any]       = None
    status           : str                 = "ACTIVE"
    status_code      : str                 = "ACTIVE"
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


class STOCK_ADJUSTMENT_CREATE_SCHEMA(BaseModel):
    variant_id     : uuid.UUID
    warehouse_id   : uuid.UUID
    quantity_delta : Optional[int] = None  # positive = add, negative = remove
    new_quantity   : Optional[int] = None  # when setting absolute stock count
    movement_type  : str           = "ADJUSTMENT"  # ADJUSTMENT | DAMAGE | LOST | INITIAL_STOCK
    note           : Optional[str] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        adj_type = str(out.get("adjustment_type") or out.get("type") or "").upper()
        qty = out.get("quantity")
        if qty is not None and out.get("quantity_delta") is None and out.get("new_quantity") is None:
            qty_int = int(qty)
            if adj_type == "SET":
                out["new_quantity"] = qty_int
            elif adj_type in ("REMOVE", "OUT", "SUBTRACT", "DEDUCT"):
                out["quantity_delta"] = -abs(qty_int)
            else:
                out["quantity_delta"] = qty_int
        if out.get("note") is None and out.get("reason") is not None:
            out["note"] = str(out["reason"])
        return out


class STOCK_TRANSFER_ITEM_CREATE_SCHEMA(BaseModel):
    variant_id : uuid.UUID
    quantity   : int       = Field(gt=0)


class STOCK_TRANSFER_CREATE_SCHEMA(BaseModel):
    from_warehouse_id : uuid.UUID
    to_warehouse_id   : uuid.UUID
    items             : List[STOCK_TRANSFER_ITEM_CREATE_SCHEMA]
    notes             : Optional[str]                          = None


class STOCK_TRANSFER_ITEM_RESPONSE_SCHEMA(BaseModel):
    id                 : uuid.UUID
    transfer_id        : uuid.UUID
    variant_id         : uuid.UUID
    quantity_requested : int
    quantity_sent      : int
    quantity_received  : int
    notes              : Optional[str]      = None
    status             : str                = "ACTIVE"
    status_code        : str                = "ACTIVE"
    created_datetime   : Optional[datetime] = None
    updated_datetime   : Optional[datetime] = None
    created_at         : Optional[datetime] = None
    updated_at         : Optional[datetime] = None

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


class STOCK_TRANSFER_RESPONSE_SCHEMA(BaseModel):
    id                : uuid.UUID
    transfer_number   : str
    from_warehouse_id : uuid.UUID
    to_warehouse_id   : uuid.UUID
    status            : str                                        = "PENDING"
    status_code       : str                                        = "PENDING"
    notes             : Optional[str]                              = None
    created_by        : Optional[Any]                              = None
    approved_by       : Optional[Any]                              = None
    items             : List[STOCK_TRANSFER_ITEM_RESPONSE_SCHEMA]  = []
    created_datetime  : Optional[datetime]                         = None
    updated_datetime  : Optional[datetime]                         = None
    created_at        : Optional[datetime]                         = None
    updated_at        : Optional[datetime]                         = None

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


__all__ = [
    "INVENTORY_STOCK_RESPONSE_SCHEMA",
    "INVENTORY_MOVEMENT_RESPONSE_SCHEMA",
    "STOCK_ADJUSTMENT_CREATE_SCHEMA",
    "STOCK_TRANSFER_ITEM_CREATE_SCHEMA",
    "STOCK_TRANSFER_CREATE_SCHEMA",
    "STOCK_TRANSFER_ITEM_RESPONSE_SCHEMA",
    "STOCK_TRANSFER_RESPONSE_SCHEMA",
]

