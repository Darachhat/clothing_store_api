"""Translation CMS Schemas.

Pydantic schemas for managing TRANSLATE_MODEL (base_data.translate) entries.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base_schema import BASE_SCHEMA, BASE_TIMESTAMP_RESPONSE_SCHEMA


class TRANSLATION_ITEM_BASE_SCHEMA(BASE_SCHEMA):
    schema_name: str = Field(default="admin_front", max_length=100)
    table_name: str = Field(..., min_length=1, max_length=100)
    column_name: str = Field(..., min_length=1, max_length=100)
    en: Optional[str] = None
    km: Optional[str] = None
    cn: Optional[str] = None
    jp: Optional[str] = None
    kr: Optional[str] = None
    note: Optional[str] = None


class TRANSLATION_ITEM_CREATE_SCHEMA(TRANSLATION_ITEM_BASE_SCHEMA):
    ref_id: Optional[uuid.UUID] = None
    status_code: str = Field(default="ACTIVE", max_length=10)


class TRANSLATION_ITEM_UPDATE_SCHEMA(BASE_SCHEMA):
    schema_name: Optional[str] = Field(None, max_length=100)
    table_name: Optional[str] = Field(None, max_length=100)
    column_name: Optional[str] = Field(None, max_length=100)
    en: Optional[str] = None
    km: Optional[str] = None
    cn: Optional[str] = None
    jp: Optional[str] = None
    kr: Optional[str] = None
    note: Optional[str] = None
    status_code: Optional[str] = Field(None, max_length=10)


class TRANSLATION_ITEM_RESPONSE_SCHEMA(BASE_TIMESTAMP_RESPONSE_SCHEMA):
    id: uuid.UUID
    ref_id: uuid.UUID
    schema_name: str
    table_name: str
    column_name: str
    en: Optional[str] = None
    km: Optional[str] = None
    cn: Optional[str] = None
    jp: Optional[str] = None
    kr: Optional[str] = None
    note: Optional[str] = None
    status_code: str = "ACTIVE"
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TRANSLATION_PAGINATED_RESPONSE_SCHEMA(BASE_SCHEMA):
    items: List[TRANSLATION_ITEM_RESPONSE_SCHEMA]
    total: int
    page: int
    page_size: int
    total_pages: int


class TRANSLATION_PURGE_RESPONSE_SCHEMA(BASE_SCHEMA):
    status: str
    message: str

