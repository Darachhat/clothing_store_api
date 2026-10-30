"""
Shared base models with UUID primary key, timestamps, and enterprise audit columns.
All models import from here.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TIMESTAMP_MIXIN:
    created_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
        , server_default = func.now()
        , nullable       = False
    )
    updated_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
        , server_default = func.now()
        , onupdate       = func.now()
        , nullable       = False
    )


class UUID_BASE_MODEL(Base, TIMESTAMP_MIXIN):
    """Abstract base with UUID PK and created_at / updated_at timestamps."""

    __abstract__ = True

    id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True)
        , primary_key = True
        , default     = uuid.uuid4
    )


class TEMPLATE_BASE_MODEL(Base):
    """Abstract base for enterprise template models (auth, base_data, track schemas)."""

    __abstract__ = True

    created_datetime : Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow)
    updated_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow)
    deleted_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    updated_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    deleted_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)


# Backward-compatible aliases
TimestampMixin = TIMESTAMP_MIXIN
UUIDBase       = UUID_BASE_MODEL

__all__ = [
    "Base"
    , "TIMESTAMP_MIXIN"
    , "UUID_BASE_MODEL"
    , "TEMPLATE_BASE_MODEL"
    , "TimestampMixin"
    , "UUIDBase"
]
