"""Repositories for Expense, ExpenseCategory, and Promotion."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.misc import Expense, ExpenseCategory, Promotion
from app.repositories.base import BaseRepository


class ExpenseCategoryRepository(BaseRepository[ExpenseCategory]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(ExpenseCategory, db)

    async def get_by_code(self, code: str) -> ExpenseCategory | None:
        stmt = select(ExpenseCategory).where(ExpenseCategory.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class ExpenseRepository(BaseRepository[Expense]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Expense, db)

    async def get_by_id(self, id: UUID) -> Expense | None:
        stmt = (
            select(Expense)
            .where(Expense.id == id)
            .options(selectinload(Expense.category))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_expenses(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        branch_id: UUID | None = None,
        category_id: UUID | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Sequence[Expense]:
        stmt = (
            select(Expense)
            .options(selectinload(Expense.category))
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        )
        if branch_id:
            stmt = stmt.where(Expense.branch_id == branch_id)
        if category_id:
            stmt = stmt.where(Expense.category_id == category_id)
        if status:
            stmt = stmt.where(Expense.status == status)
        if from_date:
            stmt = stmt.where(Expense.expense_date >= from_date)
        if to_date:
            stmt = stmt.where(Expense.expense_date <= to_date)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_expenses(
        self,
        *,
        branch_id: UUID | None = None,
        category_id: UUID | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Expense)
        if branch_id:
            stmt = stmt.where(Expense.branch_id == branch_id)
        if category_id:
            stmt = stmt.where(Expense.category_id == category_id)
        if status:
            stmt = stmt.where(Expense.status == status)
        if from_date:
            stmt = stmt.where(Expense.expense_date >= from_date)
        if to_date:
            stmt = stmt.where(Expense.expense_date <= to_date)

        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def total_amount(
        self,
        *,
        branch_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str = "APPROVED",
    ) -> Decimal:
        stmt = select(func.coalesce(func.sum(Expense.amount), Decimal("0"))).where(
            Expense.status == status
        )
        if branch_id:
            stmt = stmt.where(Expense.branch_id == branch_id)
        if from_date:
            stmt = stmt.where(Expense.expense_date >= from_date)
        if to_date:
            stmt = stmt.where(Expense.expense_date <= to_date)

        result = await self.db.execute(stmt)
        return result.scalar_one()


class PromotionRepository(BaseRepository[Promotion]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Promotion, db)

    async def get_by_code(self, code: str) -> Promotion | None:
        stmt = select(Promotion).where(Promotion.code == code)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_promotions(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        active_only: bool = False,
    ) -> Sequence[Promotion]:
        stmt = select(Promotion).order_by(Promotion.created_at.desc())
        if status:
            stmt = stmt.where(Promotion.status == status)
        if active_only:
            now = datetime.now(UTC)
            stmt = stmt.where(
                Promotion.status == "ACTIVE",
                Promotion.start_datetime <= now,
                Promotion.end_datetime >= now,
            )

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_promotions(
        self,
        *,
        status: str | None = None,
        active_only: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(Promotion)
        if status:
            stmt = stmt.where(Promotion.status == status)
        if active_only:
            now = datetime.now(UTC)
            stmt = stmt.where(
                Promotion.status == "ACTIVE",
                Promotion.start_datetime <= now,
                Promotion.end_datetime >= now,
            )

        result = await self.db.execute(stmt)
        return result.scalar_one()
