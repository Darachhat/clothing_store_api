from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

from app.core.enum.response_enum import RESPONSE_CODE_ENUM

T = TypeVar("T")


class RESPONSE_ENVELOPE(BaseModel, Generic[T]):
    """
    Standardized JSON response envelope across all API endpoints.
    """
    code        : RESPONSE_CODE_ENUM  = Field(default=RESPONSE_CODE_ENUM.SUCCESS, description="Application response status code")
    message     : str                 = Field(default="Operation completed successfully.", description="Human readable message")
    data        : Optional[T]         = Field(default=None, description="Response payload")
    errors      : Optional[List[str]] = Field(default=None, description="List of error messages if operation failed")
    request_id  : Optional[str]       = Field(default=None, description="Unique trace request ID")

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


class STATS_SUMMARY_SCHEMA(BaseModel):
    total       : int = 0
    active      : int = 0
    inactive    : int = 0


class RESPONSE_CODE_ITEM_SCHEMA(BaseModel):
    code        : str
    http_status : int
    message     : str

