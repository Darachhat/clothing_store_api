"""Expense and Expense Category API endpoints."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models.misc import Expense, ExpenseCategory
from app.models.user import User
from app.repositories.misc_repository import ExpenseCategoryRepository, ExpenseRepository
from app.schemas.expense import (
    ExpenseCategoryCreate,
    ExpenseCategoryOut,
    ExpenseCategoryUpdate,
    ExpenseCreate,
    ExpenseOut,
    ExpenseUpdate,
)
from app.services.misc_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# ── Expense Categories ────────────────────────────────────────────────────────
@router.get("/categories", response_model=list[ExpenseCategoryOut])
async def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[ExpenseCategory]:
    repo = ExpenseCategoryRepository(db)
    items = await repo.get_all(skip=skip, limit=limit)
    return list(items)


@router.post("/categories", response_model=ExpenseCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: ExpenseCategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> ExpenseCategory:
    repo = ExpenseCategoryRepository(db)
    existing = await repo.get_by_code(payload.code.upper().strip())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category code already exists")
    cat = await repo.create(
        name=payload.name.strip(),
        code=payload.code.upper().strip(),
        description=payload.description,
        is_system=False,
    )
    await db.commit()
    return cat


@router.patch("/categories/{cat_id}", response_model=ExpenseCategoryOut)
@router.put("/categories/{cat_id}", response_model=ExpenseCategoryOut)
async def update_category(
    cat_id: UUID,
    payload: ExpenseCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> ExpenseCategory:
    repo = ExpenseCategoryRepository(db)
    cat = await repo.get_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    update_data = payload.model_dump(exclude_unset=True)
    cat = await repo.update(cat, **update_data)
    await db.commit()
    return cat


# ── Expenses ──────────────────────────────────────────────────────────────────
@router.get("", response_model=list[ExpenseOut])
async def list_expenses(
    branch_id: UUID | None = None,
    category_id: UUID | None = None,
    expense_status: str | None = Query(None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Expense]:
    repo = ExpenseRepository(db)
    expenses = await repo.list_expenses(
        skip=skip,
        limit=limit,
        branch_id=branch_id,
        category_id=category_id,
        status=expense_status,
        from_date=from_date,
        to_date=to_date,
    )
    return list(expenses)


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Expense:
    service = ExpenseService(db)
    is_privileged = any(r.name in ["ADMIN", "MANAGER"] for r in current_user.roles)
    expense = await service.create_expense(
        created_by=current_user.id,
        data=payload,
        auto_approve=is_privileged,
    )
    await db.commit()
    return expense


@router.get("/{expense_id}", response_model=ExpenseOut)
async def get_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Expense:
    repo = ExpenseRepository(db)
    expense = await repo.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


@router.patch("/{expense_id}", response_model=ExpenseOut)
@router.put("/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: UUID,
    payload: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Expense:
    service = ExpenseService(db)
    expense = await service.update_expense(expense_id=expense_id, data=payload)
    await db.commit()
    return expense


@router.post("/{expense_id}/approve", response_model=ExpenseOut)
async def approve_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> Expense:
    service = ExpenseService(db)
    expense = await service.approve_expense(expense_id=expense_id, approved_by=current_user.id)
    await db.commit()
    return expense


@router.post("/{expense_id}/reject", response_model=ExpenseOut)
async def reject_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> Expense:
    service = ExpenseService(db)
    expense = await service.reject_expense(expense_id=expense_id, rejected_by=current_user.id)
    await db.commit()
    return expense
