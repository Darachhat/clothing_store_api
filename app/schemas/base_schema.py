"""Shared Pydantic schema utilities and base response envelopes."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.core.enum.response_enum import RESPONSE_CODE_ENUM

T = TypeVar("T")


class BASE_SCHEMA(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TIMESTAMP_SCHEMA(BASE_SCHEMA):
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None
    created_at       : Optional[datetime] = None
    updated_at       : Optional[datetime] = None

    def model_post_init(self, __context: Any) -> None:
        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class UUID_SCHEMA(TIMESTAMP_SCHEMA):
    id : uuid.UUID


class PAGINATED_RESPONSE_SCHEMA(BASE_SCHEMA):
    total : int
    skip  : int  = 0
    limit : int  = 50
    items : list = []


class MESSAGE_RESPONSE_SCHEMA(BASE_SCHEMA):
    message : str


class STATS_SUMMARY_SCHEMA(BaseModel):
    total    : int = 0
    active   : int = 0
    inactive : int = 0


class RESPONSE_CODE_ITEM_SCHEMA(BaseModel):
    code        : str
    http_status : int
    message     : str


class RESPONSE_ENVELOPE(BaseModel, Generic[T]):
    """Standardized JSON response envelope across all API endpoints."""
    code       : RESPONSE_CODE_ENUM  = Field(default=RESPONSE_CODE_ENUM.SUCCESS, description="Application response status code")
    message    : str                 = Field(default="Operation completed successfully.", description="Human readable message")
    data       : Optional[T]         = Field(default=None, description="Response payload")
    errors     : Optional[List[str]] = Field(default=None, description="List of error messages if operation failed")
    request_id : Optional[str]       = Field(default=None, description="Unique trace request ID")

    @classmethod
    def success(
        cls
        , data       : Optional[T]   = None
        , message    : str           = "Operation completed successfully."
        , request_id : Optional[str] = None
    ) -> "RESPONSE_ENVELOPE[T]":
        return cls(
            code         = RESPONSE_CODE_ENUM.SUCCESS
            , message    = message
            , data       = data
            , errors     = None
            , request_id = request_id
        )

    @classmethod
    def created(
        cls
        , data       : Optional[T]   = None
        , message    : str           = "Resource created successfully."
        , request_id : Optional[str] = None
    ) -> "RESPONSE_ENVELOPE[T]":
        return cls(
            code         = RESPONSE_CODE_ENUM.CREATED
            , message    = message
            , data       = data
            , errors     = None
            , request_id = request_id
        )

    @classmethod
    def error(
        cls
        , code       : RESPONSE_CODE_ENUM
        , message    : str
        , errors     : Optional[List[str]] = None
        , request_id : Optional[str]       = None
    ) -> "RESPONSE_ENVELOPE[T]":
        return cls(
            code         = code
            , message    = message
            , data       = None
            , errors     = errors or []
            , request_id = request_id
        )


class PAGINATED_DATA(BaseModel, Generic[T]):
    items       : List[T]
    total       : int
    page        : int
    page_size   : int
    total_pages : int


__all__ = [
    "BASE_SCHEMA",
    "TIMESTAMP_SCHEMA",
    "UUID_SCHEMA",
    "PAGINATED_RESPONSE_SCHEMA",
    "MESSAGE_RESPONSE_SCHEMA",
    "STATS_SUMMARY_SCHEMA",
    "RESPONSE_CODE_ITEM_SCHEMA",
    "RESPONSE_ENVELOPE",
    "PAGINATED_DATA",
]
