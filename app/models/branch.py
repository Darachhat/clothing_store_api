"""Branch and Warehouse models."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.inventory import InventoryStock
    from app.models.user import User


class Branch(UUIDBase):
    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    warehouses: Mapped[list[Warehouse]] = relationship("Warehouse", back_populates="branch")
    users: Mapped[list[User]] = relationship("User", back_populates="branch")


class Warehouse(UUIDBase):
    __tablename__ = "warehouses"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)

    branch: Mapped[Branch] = relationship("Branch", back_populates="warehouses")
    inventory_stocks: Mapped[list[InventoryStock]] = relationship(
        "InventoryStock", back_populates="warehouse"
    )
