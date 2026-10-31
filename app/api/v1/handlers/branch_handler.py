"""Branches and Warehouses endpoints."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.branch import Branch, Warehouse
from app.models.user import User
from app.schemas.base import UUIDSchema

router = APIRouter(prefix="/branches", tags=["Branches & Warehouses"])


class WarehouseOut(UUIDSchema):
    branch_id: UUID
    name: str
    address: str | None = None
    is_default: bool = False
    status: str = "ACTIVE"


class BranchOut(UUIDSchema):
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    status: str = "ACTIVE"
    warehouses: list[WarehouseOut] = []


@router.get("/", response_model=list[BranchOut])
async def list_branches(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Branch]:
    result = await db.execute(
        select(Branch)
        .options(selectinload(Branch.warehouses))
        .where(Branch.status == "ACTIVE")
        .order_by(Branch.name.asc())
    )
    return list(result.scalars().all())
