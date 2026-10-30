"""Services for Expense and Promotion business logic."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.misc import Expense
from app.repositories.misc_repository import (
    ExpenseCategoryRepository,
    ExpenseRepository,
    PromotionRepository,
)
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.promotion import CouponValidationResponse
from app.utils.generators import generate_expense_number


class ExpenseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.expense_repo = ExpenseRepository(db)
        self.category_repo = ExpenseCategoryRepository(db)

    async def create_expense(
        self,
        created_by: UUID,
        data: ExpenseCreate,
        auto_approve: bool = False,
    ) -> Expense:
        category = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense category {data.category_id} not found",
            )

        expense_number = await generate_expense_number(self.db)
        status_val = "APPROVED" if auto_approve else "PENDING"

        expense = Expense(
            expense_number=expense_number,
            category_id=data.category_id,
            branch_id=data.branch_id,
            amount=data.amount,
            payment_method=data.payment_method,
            expense_date=data.expense_date,
            description=data.description,
            receipt_url=data.receipt_url,
            notes=data.notes,
            created_by=created_by,
            approved_by=created_by if auto_approve else None,
            status=status_val,
        )

        self.db.add(expense)
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def update_expense(
        self,
        expense_id: UUID,
        data: ExpenseUpdate,
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense {expense_id} not found",
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(expense, key, value)

        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def approve_expense(
        self,
        expense_id: UUID,
        approved_by: UUID,
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense {expense_id} not found",
            )

        expense.status = "APPROVED"
        expense.approved_by = approved_by
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def reject_expense(
        self,
        expense_id: UUID,
        rejected_by: UUID,
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Expense {expense_id} not found",
            )

        expense.status = "REJECTED"
        expense.approved_by = rejected_by
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)


class PromotionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.promo_repo = PromotionRepository(db)

    async def validate_coupon(
        self,
        code: str,
        cart_total: Decimal,
    ) -> CouponValidationResponse:
        promo = await self.promo_repo.get_by_code(code.upper().strip())
        if not promo:
            return CouponValidationResponse(
                valid=False,
                discount_amount=Decimal("0"),
                message="Invalid coupon code",
            )

        now = datetime.now(UTC)
        if promo.status != "ACTIVE":
            return CouponValidationResponse(
                valid=False,
                discount_amount=Decimal("0"),
                message="Promotion is no longer active",
            )

        if promo.start_datetime > now or promo.end_datetime < now:
            return CouponValidationResponse(
                valid=False,
                discount_amount=Decimal("0"),
                message="Coupon is not valid at this time",
            )

        if promo.usage_limit is not None and promo.usage_count >= promo.usage_limit:
            return CouponValidationResponse(
                valid=False,
                discount_amount=Decimal("0"),
                message="Coupon usage limit reached",
            )

        if cart_total < promo.min_purchase_amount:
            return CouponValidationResponse(
                valid=False,
                discount_amount=Decimal("0"),
                message=f"Minimum purchase amount of ${promo.min_purchase_amount} required",
            )

        # Calculate discount
        if promo.type == "PERCENTAGE":
            discount = (cart_total * promo.value) / Decimal("100")
        else:  # FIXED or COUPON flat discount
            discount = promo.value

        if promo.max_discount_amount and discount > promo.max_discount_amount:
            discount = promo.max_discount_amount

        # Cannot exceed total
        if discount > cart_total:
            discount = cart_total

        return CouponValidationResponse(
            valid=True,
            discount_amount=discount.quantize(Decimal("0.01")),
            message=f"Coupon applied: ${discount:.2f} off",
            promotion=promo,
        )

    async def record_usage(self, promo_id: UUID) -> None:
        promo = await self.promo_repo.get_by_id(promo_id)
        if promo:
            promo.usage_count += 1
            if promo.usage_limit and promo.usage_count >= promo.usage_limit:
                promo.status = "EXPIRED"
            await self.db.flush()
