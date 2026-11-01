"""Branches and Warehouses endpoints."""
from __future__ import annotations

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import Branch, Warehouse
from app.models import User
from app.schemas.base_schema import BASE_SCHEMA, UUID_SCHEMA

router = APIRouter(prefix="/branches", tags=["Branches & Warehouses"])
warehouses_router = APIRouter(prefix="/warehouses", tags=["Branches & Warehouses"])


class WarehouseCreate(BASE_SCHEMA):
    branch_id: UUID
    name: str
    address: str | None = None
    is_default: bool = False
    status: str = "ACTIVE"


class WarehouseUpdate(BASE_SCHEMA):
    branch_id: UUID | None = None
    name: str | None = None
    address: str | None = None
    is_default: bool | None = None
    status: str | None = None


class WarehouseOut(UUID_SCHEMA):
    branch_id: UUID
    name: str
    address: str | None = None
    is_default: bool = False
    status: str = "ACTIVE"


class BranchCreate(BASE_SCHEMA):
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    status: str = "ACTIVE"


class BranchUpdate(BASE_SCHEMA):
    code: str | None = None
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    status: str | None = None


class BranchOut(UUID_SCHEMA):
    code: str
    name: str
    address: str | None = None
    phone: str | None = None
    status: str = "ACTIVE"
    warehouses: list[WarehouseOut] = []


@router.get("", response_model=list[BranchOut], include_in_schema=False)
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


@router.post("", response_model=BranchOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(
    body: BranchCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Branch:
    existing = await db.execute(select(Branch).where(Branch.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Branch code already exists")
    branch = Branch(**body.model_dump())
    db.add(branch)
    await db.commit()
    result = await db.execute(
        select(Branch).options(selectinload(Branch.warehouses)).where(Branch.id == branch.id)
    )
    return result.scalar_one()


@router.get("/{id}", response_model=BranchOut)
async def get_branch(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Branch:
    result = await db.execute(
        select(Branch).options(selectinload(Branch.warehouses)).where(Branch.id == id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.put("/{id}", response_model=BranchOut)
@router.patch("/{id}", response_model=BranchOut)
async def update_branch(
    id: UUID,
    body: BranchUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Branch:
    result = await db.execute(
        select(Branch).options(selectinload(Branch.warehouses)).where(Branch.id == id)
    )
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(branch, k, v)
    await db.commit()
    await db.refresh(branch)
    return branch


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_branch(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Response:
    result = await db.execute(select(Branch).where(Branch.id == id))
    branch = result.scalar_one_or_none()
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    branch.status = "INACTIVE"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ─── Warehouses ───────────────────────────────────────────────────────────────
@warehouses_router.get("", response_model=list[WarehouseOut], include_in_schema=False)
@warehouses_router.get("/", response_model=list[WarehouseOut])
async def list_warehouses(
    branch_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Warehouse]:
    stmt = select(Warehouse).where(Warehouse.status == "ACTIVE").order_by(Warehouse.is_default.desc(), Warehouse.name.asc())
    if branch_id:
        stmt = stmt.where(Warehouse.branch_id == branch_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@warehouses_router.post("", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@warehouses_router.post("/", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjust")),
) -> Warehouse:
    wh = Warehouse(**body.model_dump())
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh


@warehouses_router.put("/{id}", response_model=WarehouseOut)
@warehouses_router.patch("/{id}", response_model=WarehouseOut)
async def update_warehouse(
    id: UUID,
    body: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjust")),
) -> Warehouse:
    result = await db.execute(select(Warehouse).where(Warehouse.id == id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(wh, k, v)
    await db.commit()
    await db.refresh(wh)
    return wh


@warehouses_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_warehouse(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.adjust")),
) -> Response:
    result = await db.execute(select(Warehouse).where(Warehouse.id == id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    wh.status = "INACTIVE"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
