"""Expense and Expense Category API endpoints."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import Expense, ExpenseCategory
from app.models import User
from app.repositories.misc_repository import ExpenseCategoryRepository, ExpenseRepository
from app.schemas.expense_schema import (
    EXPENSE_CATEGORY_CREATE_SCHEMA,
    EXPENSE_CATEGORY_RESPONSE_SCHEMA,
    EXPENSE_CATEGORY_UPDATE_SCHEMA,
    EXPENSE_CREATE_SCHEMA,
    EXPENSE_RESPONSE_SCHEMA,
    EXPENSE_UPDATE_SCHEMA,
)
from app.services.misc_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# ── Expense Categories ────────────────────────────────────────────────────────
@router.get("/categories", response_model=list[EXPENSE_CATEGORY_RESPONSE_SCHEMA])
async def list_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[ExpenseCategory]:
    repo = ExpenseCategoryRepository(db)
    items = await repo.get_all(skip=skip, limit=limit)
    return list(items)


@router.post("/categories", response_model=EXPENSE_CATEGORY_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: EXPENSE_CATEGORY_CREATE_SCHEMA,
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


@router.patch("/categories/{cat_id}", response_model=EXPENSE_CATEGORY_RESPONSE_SCHEMA)
@router.put("/categories/{cat_id}", response_model=EXPENSE_CATEGORY_RESPONSE_SCHEMA)
async def update_category(
    cat_id: UUID,
    payload: EXPENSE_CATEGORY_UPDATE_SCHEMA,
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


@router.delete("/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_category(
    cat_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Response:
    repo = ExpenseCategoryRepository(db)
    cat = await repo.get_by_id(cat_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if cat.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete system expense category")
    await repo.delete(cat)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Expenses ──────────────────────────────────────────────────────────────────
@router.get("", response_model=list[EXPENSE_RESPONSE_SCHEMA])
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


@router.post("", response_model=EXPENSE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: EXPENSE_CREATE_SCHEMA,
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


@router.get("/{expense_id}", response_model=EXPENSE_RESPONSE_SCHEMA)
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


@router.patch("/{expense_id}", response_model=EXPENSE_RESPONSE_SCHEMA)
@router.put("/{expense_id}", response_model=EXPENSE_RESPONSE_SCHEMA)
async def update_expense(
    expense_id: UUID,
    payload: EXPENSE_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Expense:
    repo = ExpenseRepository(db)
    expense = await repo.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    is_privileged = any(r.name in ["ADMIN", "MANAGER"] for r in current_user.roles)
    if not is_privileged:
        if expense.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot edit an expense created by another user",
            )
        if expense.status != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot edit an expense that has already been approved or rejected",
            )

    service = ExpenseService(db)
    expense = await service.update_expense(expense_id=expense_id, data=payload)
    await db.commit()
    return expense


@router.post("/{expense_id}/approve", response_model=EXPENSE_RESPONSE_SCHEMA)
async def approve_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> Expense:
    service = ExpenseService(db)
    expense = await service.approve_expense(expense_id=expense_id, approved_by=current_user.id)
    await db.commit()
    return expense


@router.post("/{expense_id}/reject", response_model=EXPENSE_RESPONSE_SCHEMA)
async def reject_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> Expense:
    service = ExpenseService(db)
    expense = await service.reject_expense(expense_id=expense_id, rejected_by=current_user.id)
    await db.commit()
    return expense


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_expense(
    expense_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Response:
    repo = ExpenseRepository(db)
    expense = await repo.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    await repo.delete(expense)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
