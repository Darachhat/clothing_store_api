"""Shared Pydantic schema utilities and base classes."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.base_schema import (
    PAGINATED_DATA
    , RESPONSE_CODE_ITEM_SCHEMA
    , RESPONSE_ENVELOPE
    , STATS_SUMMARY_SCHEMA
)


class BASE_SCHEMA(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TIMESTAMP_SCHEMA(BASE_SCHEMA):
    created_at : datetime
    updated_at : datetime


class UUID_SCHEMA(TIMESTAMP_SCHEMA):
    id : UUID


class PAGINATED_RESPONSE_SCHEMA(BASE_SCHEMA):
    total : int
    skip  : int
    limit : int
    items : list


class MESSAGE_RESPONSE_SCHEMA(BASE_SCHEMA):
    message : str


# Backward-compatible aliases
BaseSchema        = BASE_SCHEMA
TimestampSchema   = TIMESTAMP_SCHEMA
UUIDSchema        = UUID_SCHEMA
PaginatedResponse = PAGINATED_RESPONSE_SCHEMA
MessageResponse   = MESSAGE_RESPONSE_SCHEMA

__all__ = [
    "BASE_SCHEMA"
    , "TIMESTAMP_SCHEMA"
    , "UUID_SCHEMA"
    , "PAGINATED_RESPONSE_SCHEMA"
    , "MESSAGE_RESPONSE_SCHEMA"
    , "RESPONSE_ENVELOPE"
    , "PAGINATED_DATA"
    , "STATS_SUMMARY_SCHEMA"
    , "RESPONSE_CODE_ITEM_SCHEMA"
    , "BaseSchema"
    , "TimestampSchema"
    , "UUIDSchema"
    , "PaginatedResponse"
    , "MessageResponse"
]
