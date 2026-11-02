"""Audit logging schemas following system_log_schema.py template."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class AUDIT_LOG_CREATE_REQUEST_SCHEMA(BaseModel):
    action      : str                      = Field(..., max_length=100)
    entity_type : Optional[str]            = Field(default=None, max_length=100)
    entity_id   : Optional[uuid.UUID]      = None
    user_id     : Optional[uuid.UUID]      = None
    old_data    : Optional[Dict[str, Any]] = None
    new_data    : Optional[Dict[str, Any]] = None
    ip_address  : Optional[str]            = Field(default=None, max_length=50)
    user_agent  : Optional[str]            = Field(default=None, max_length=500)

    model_config = {"from_attributes": True}


class AUDIT_LOG_RESPONSE_SCHEMA(BaseModel):
    id          : uuid.UUID
    action      : str
    entity_type : Optional[str]            = None
    entity_id   : Optional[uuid.UUID]      = None
    user_id     : Optional[uuid.UUID]      = None
    old_data    : Optional[Dict[str, Any]] = None
    new_data    : Optional[Dict[str, Any]] = None
    ip_address  : Optional[str]            = None
    user_agent  : Optional[str]            = None
    created_at  : Optional[datetime]       = None
    created_datetime : Optional[datetime]  = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at


class AUDIT_LOG_LIST_OUT_SCHEMA(BaseModel):
    items : List[AUDIT_LOG_RESPONSE_SCHEMA]
    total : int
    skip  : Optional[int]                 = 0
    limit : Optional[int]                 = 100


__all__ = [
    "AUDIT_LOG_CREATE_REQUEST_SCHEMA",
    "AUDIT_LOG_RESPONSE_SCHEMA",
    "AUDIT_LOG_LIST_OUT_SCHEMA",
]

