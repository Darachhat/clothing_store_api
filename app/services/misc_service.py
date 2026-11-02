"""Services for Expense and Promotion business logic."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enum.common_enum import (
    COMMON_STATUS_ENUM
    , PROMOTION_TYPE_ENUM
)
from app.core.exceptions import NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import Branch, Expense
from app.repositories.misc_repository import (
    ExpenseCategoryRepository
    , ExpenseRepository
    , PromotionRepository
)
from app.schemas.expense_schema import EXPENSE_CREATE_SCHEMA, EXPENSE_UPDATE_SCHEMA
from app.schemas.promotion_schema import (
    COUPON_VALIDATION_REQUEST_SCHEMA
    , COUPON_VALIDATION_RESPONSE_SCHEMA
)
from app.utils.generators import generate_expense_number

logger = get_logger(__name__)


class EXPENSE_SERVICE:
    """Service managing business operation expenses, category allocations, and approval states."""

    def __init__(self, db: AsyncSession) -> None:
        self.db            = db
        self.expense_repo  = ExpenseRepository(db)
        self.category_repo = ExpenseCategoryRepository(db)

    async def create_expense(
        self
        , created_by   : UUID
        , data         : EXPENSE_CREATE_SCHEMA
        , auto_approve : bool = False
    ) -> Expense:
        category = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise NOT_FOUND_EXCEPTION(f"Expense category {data.category_id} not found")

        branch_id = data.branch_id
        nil_uuid  = UUID("00000000-0000-0000-0000-000000000000")
        if not branch_id or branch_id == nil_uuid:
            branch = (
                await self.db.execute(
                    select(Branch)
                    .where(Branch.status == COMMON_STATUS_ENUM.ACTIVE.value)
                    .order_by(Branch.created_at.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not branch:
                branch = (await self.db.execute(select(Branch).limit(1))).scalar_one_or_none()
            if branch:
                branch_id = branch.id

        expense_number = await generate_expense_number(self.db)
        status_val     = COMMON_STATUS_ENUM.APPROVED.value if auto_approve else COMMON_STATUS_ENUM.PENDING.value

        expense = Expense(
            expense_number   = expense_number
            , category_id     = data.category_id
            , branch_id       = branch_id
            , amount          = data.amount
            , payment_method  = data.payment_method
            , expense_date    = data.expense_date
            , description     = data.description
            , receipt_url     = data.receipt_url
            , notes           = data.notes
            , created_by      = created_by
            , approved_by     = created_by if auto_approve else None
            , status          = status_val
        )

        self.db.add(expense)
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def update_expense(
        self
        , expense_id : UUID
        , data       : EXPENSE_UPDATE_SCHEMA
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise NOT_FOUND_EXCEPTION(f"Expense {expense_id} not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(expense, key, value)

        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def approve_expense(
        self
        , expense_id  : UUID
        , approved_by : UUID
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise NOT_FOUND_EXCEPTION(f"Expense {expense_id} not found")

        expense.status      = COMMON_STATUS_ENUM.APPROVED.value
        expense.approved_by = approved_by
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)

    async def reject_expense(
        self
        , expense_id  : UUID
        , rejected_by : UUID
    ) -> Expense:
        expense = await self.expense_repo.get_by_id(expense_id)
        if not expense:
            raise NOT_FOUND_EXCEPTION(f"Expense {expense_id} not found")

        expense.status = COMMON_STATUS_ENUM.REJECTED.value
        note           = f"Rejected by user {rejected_by}"
        expense.notes  = f"{expense.notes}\n{note}" if expense.notes else note
        await self.db.flush()
        return await self.expense_repo.get_by_id(expense.id)


class PROMOTION_SERVICE:
    """Service validating active promotion discounts, vouchers, and tracking consumption counts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self.promo_repo = PromotionRepository(db)

    async def validate_coupon(
        self
        , code       : str
        , cart_total : Decimal
    ) -> COUPON_VALIDATION_RESPONSE_SCHEMA:
        promo = await self.promo_repo.get_by_code(code.upper().strip())
        if not promo:
            return COUPON_VALIDATION_RESPONSE_SCHEMA(
                valid           = False
                , discount_amount = Decimal("0")
                , message         = "Invalid coupon code"
            )

        now = datetime.now(UTC)
        if promo.status != COMMON_STATUS_ENUM.ACTIVE.value:
            return COUPON_VALIDATION_RESPONSE_SCHEMA(
                valid           = False
                , discount_amount = Decimal("0")
                , message         = "Promotion is no longer active"
            )

        if promo.start_datetime > now or promo.end_datetime < now:
            return COUPON_VALIDATION_RESPONSE_SCHEMA(
                valid           = False
                , discount_amount = Decimal("0")
                , message         = "Coupon is not valid at this time"
            )

        if promo.usage_limit is not None and promo.usage_count >= promo.usage_limit:
            return COUPON_VALIDATION_RESPONSE_SCHEMA(
                valid           = False
                , discount_amount = Decimal("0")
                , message         = "Coupon usage limit reached"
            )

        if cart_total < promo.min_purchase_amount:
            return COUPON_VALIDATION_RESPONSE_SCHEMA(
                valid           = False
                , discount_amount = Decimal("0")
                , message         = f"Minimum purchase amount of ${promo.min_purchase_amount} required"
            )

        if promo.type == PROMOTION_TYPE_ENUM.PERCENTAGE.value:
            discount = (cart_total * promo.value) / Decimal("100")
        else:
            discount = promo.value

        if promo.max_discount_amount and discount > promo.max_discount_amount:
            discount = promo.max_discount_amount

        if discount > cart_total:
            discount = cart_total

        return COUPON_VALIDATION_RESPONSE_SCHEMA(
            valid           = True
            , discount_amount = discount.quantize(Decimal("0.01"))
            , message         = f"Coupon applied: ${discount:.2f} off"
            , promotion       = promo
        )

    async def validate_coupon_payload(
        self
        , payload : COUPON_VALIDATION_REQUEST_SCHEMA
    ) -> COUPON_VALIDATION_RESPONSE_SCHEMA:
        """Validate coupon using structured COUPON_VALIDATION_REQUEST_SCHEMA."""
        return await self.validate_coupon(
            code       = payload.code
            , cart_total = payload.cart_total
        )

    async def record_usage(self, promo_id: UUID) -> None:
        promo = await self.promo_repo.get_by_id(promo_id)
        if promo:
            promo.usage_count += 1
            if promo.usage_limit and promo.usage_count >= promo.usage_limit:
                promo.status = COMMON_STATUS_ENUM.EXPIRED.value
            await self.db.flush()



ExpenseService   = EXPENSE_SERVICE
PromotionService = PROMOTION_SERVICE