"""Customer and loyalty repository."""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Customer, LoyaltyAccount
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Customer, db)

    async def get_with_loyalty(self, customer_id: UUID) -> Customer | None:
        result = await self.db.execute(
            select(Customer)
            .where(Customer.id == customer_id)
            .options(
                selectinload(Customer.loyalty_account).selectinload(LoyaltyAccount.transactions)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer)
            .where(Customer.customer_code == code)
            .options(selectinload(Customer.loyalty_account))
        )
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> Customer | None:
        result = await self.db.execute(
            select(Customer)
            .where(Customer.phone == phone)
            .options(selectinload(Customer.loyalty_account))
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        q: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Customer], int]:
        stmt = select(Customer).options(selectinload(Customer.loyalty_account))
        count_stmt = select(func.count()).select_from(Customer)

        if q:
            term = f"%{q}%"
            criteria = or_(
                Customer.name.ilike(term),
                Customer.phone.ilike(term),
                Customer.customer_code.ilike(term),
                Customer.email.ilike(term),
            )
            stmt = stmt.where(criteria)
            count_stmt = count_stmt.where(criteria)

        if status:
            stmt = stmt.where(Customer.status == status)
            count_stmt = count_stmt.where(Customer.status == status)

        stmt = stmt.order_by(Customer.created_at.desc()).offset(skip).limit(limit)

        items_res = await self.db.execute(stmt)
        count_res = await self.db.execute(count_stmt)

        return items_res.scalars().all(), count_res.scalar_one()

    async def next_customer_code(self) -> str:
        from sqlalchemy import text
        res = await self.db.execute(text("SELECT nextval('customer_code_seq')"))
        seq = res.scalar_one()
        return f"CUST-{seq:05d}"
