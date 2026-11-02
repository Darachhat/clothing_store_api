from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic.main import BaseModel
from pydantic import Field


class TERMINAL_CREATE_SCHEMA(BaseModel):
    branch_id    : uuid.UUID
    warehouse_id : uuid.UUID
    code         : str = Field(..., min_length=1, max_length=50, description="Register code, e.g. POS-01")
    name         : str = Field(..., min_length=1, max_length=100, description="Register name, e.g. Front Counter Main")
    notes        : Optional[str] = None


class TERMINAL_UPDATE_SCHEMA(BaseModel):
    name         : Optional[str] = Field(None, min_length=1, max_length=100)
    warehouse_id : Optional[uuid.UUID] = None
    status_code  : Optional[str] = Field(None, pattern="^(ACTIVE|INACTIVE|MAINTENANCE)$")
    notes        : Optional[str] = None


class TERMINAL_RESPONSE_SCHEMA(BaseModel):
    id             : uuid.UUID
    branch_id      : uuid.UUID
    warehouse_id   : uuid.UUID
    code           : str
    name           : str
    status_code    : str
    notes          : Optional[str] = None
    last_active_at : Optional[datetime] = None
    created_at     : datetime
    branch_name    : Optional[str] = None
    warehouse_name : Optional[str] = None

    model_config = {"from_attributes": True}
