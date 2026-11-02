"""POS Terminals & Cash Registers endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import Branch, PosTerminal, User, Warehouse
from app.schemas.terminal_schema import (
    TERMINAL_CREATE_SCHEMA,
    TERMINAL_RESPONSE_SCHEMA,
    TERMINAL_UPDATE_SCHEMA,
)

router = APIRouter(prefix="/terminals", tags=["POS Terminals"])


def _terminal_eager_options():
    return (
        selectinload(PosTerminal.branch),
        selectinload(PosTerminal.warehouse),
    )


@router.get("", response_model=list[TERMINAL_RESPONSE_SCHEMA], include_in_schema=False)
@router.get("/", response_model=list[TERMINAL_RESPONSE_SCHEMA])
async def list_terminals(
    branch_id: UUID | None = Query(None, description="Filter by branch UUID"),
    status_code: str | None = Query(None, description="Filter by status (e.g. ACTIVE)"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[PosTerminal]:
    """List registered POS terminals/registers."""
    stmt = select(PosTerminal).options(*_terminal_eager_options())

    if branch_id:
        stmt = stmt.where(PosTerminal.branch_id == branch_id)
    if status_code:
        stmt = stmt.where(PosTerminal.status_code == status_code)

    stmt = stmt.order_by(PosTerminal.code.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=TERMINAL_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=TERMINAL_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_terminal(
    body: TERMINAL_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> PosTerminal:
    """Register a new POS terminal register (Admin only)."""
    # 1. Verify branch exists
    branch = await db.get(Branch, body.branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    # 2. Verify warehouse exists and belongs to branch
    warehouse = await db.get(Warehouse, body.warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    if warehouse.branch_id != body.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Warehouse does not belong to the selected branch",
        )

    # 3. Check duplicate code in this branch
    existing = await db.execute(
        select(PosTerminal).where(
            PosTerminal.branch_id == body.branch_id,
            PosTerminal.code == body.code.strip().upper(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Terminal code '{body.code}' already exists for this branch",
        )

    terminal = PosTerminal(
        branch_id=body.branch_id,
        warehouse_id=body.warehouse_id,
        code=body.code.strip().upper(),
        name=body.name.strip(),
        notes=body.notes,
        status_code="ACTIVE",
    )
    db.add(terminal)
    await db.commit()

    # Re-query with eager relationships
    result = await db.execute(
        select(PosTerminal).options(*_terminal_eager_options()).where(PosTerminal.id == terminal.id)
    )
    return result.scalar_one()


@router.get("/{id}", response_model=TERMINAL_RESPONSE_SCHEMA)
async def get_terminal(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PosTerminal:
    """Get single terminal details."""
    result = await db.execute(
        select(PosTerminal).options(*_terminal_eager_options()).where(PosTerminal.id == id)
    )
    terminal = result.scalar_one_or_none()
    if not terminal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")
    return terminal


@router.put("/{id}", response_model=TERMINAL_RESPONSE_SCHEMA)
async def update_terminal(
    id: UUID,
    body: TERMINAL_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> PosTerminal:
    """Update terminal configuration or status (Admin only)."""
    terminal = await db.get(PosTerminal, id)
    if not terminal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")

    if body.warehouse_id is not None:
        warehouse = await db.get(Warehouse, body.warehouse_id)
        if not warehouse or warehouse.branch_id != terminal.branch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Warehouse not found or belongs to a different branch",
            )
        terminal.warehouse_id = body.warehouse_id

    if body.name is not None:
        terminal.name = body.name.strip()
    if body.status_code is not None:
        terminal.status_code = body.status_code
    if body.notes is not None:
        terminal.notes = body.notes

    await db.commit()

    result = await db.execute(
        select(PosTerminal).options(*_terminal_eager_options()).where(PosTerminal.id == id)
    )
    return result.scalar_one()


@router.delete("/{id}", response_model=TERMINAL_RESPONSE_SCHEMA)
async def deactivate_terminal(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> PosTerminal:
    """Soft-deactivate a POS terminal."""
    terminal = await db.get(PosTerminal, id)
    if not terminal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")
    terminal.status_code = "INACTIVE"
    await db.commit()

    result = await db.execute(
        select(PosTerminal).options(*_terminal_eager_options()).where(PosTerminal.id == id)
    )
    return result.scalar_one()


@router.post("/{id}/heartbeat", status_code=status.HTTP_200_OK)
async def terminal_heartbeat(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Heartbeat ping from active cashier station."""
    terminal = await db.get(PosTerminal, id)
    if not terminal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")
    if terminal.status_code != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Terminal is currently {terminal.status_code}",
        )
    terminal.last_active_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "ok", "terminal_id": str(id), "last_active_at": terminal.last_active_at.isoformat()}

