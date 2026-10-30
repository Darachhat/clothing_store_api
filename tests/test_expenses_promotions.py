"""Expenses and Promotions unit tests."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.branch import Branch
from app.models.misc import ExpenseCategory, Promotion
from app.models.user import Role, User
from app.schemas.expense import ExpenseCreate
from app.services.misc_service import ExpenseService, PromotionService


@pytest.mark.asyncio
async def test_expense_lifecycle(db: AsyncSession):
    branch = Branch(code="EXP-BR", name="Expense Branch")
    db.add(branch)
    category = ExpenseCategory(code="RENT", name="Office Rent")
    db.add(category)
    role = Role(name="MANAGER", is_system=True)
    db.add(role)
    await db.flush()

    user = User(
        username="manager_exp",
        email="manager_exp@example.com",
        full_name="Exp Manager",
        hashed_password=hash_password("pw123"),
        branch_id=branch.id,
        roles=[role],
    )
    db.add(user)
    await db.flush()

    service = ExpenseService(db)
    exp_in = ExpenseCreate(
        category_id=category.id,
        branch_id=branch.id,
        amount=Decimal("150.00"),
        payment_method="CASH",
        expense_date=date.today(),
        description="Monthly office rent contribution",
    )
    expense = await service.create_expense(created_by=user.id, data=exp_in, auto_approve=True)
    assert expense.status == "APPROVED"
    assert expense.amount == Decimal("150.00")
    assert expense.expense_number.startswith("EXP-")

    # Reject / update test
    expense = await service.reject_expense(expense.id, rejected_by=user.id)
    assert expense.status == "REJECTED"


@pytest.mark.asyncio
async def test_promotion_and_coupon_validation(db: AsyncSession):
    promo = Promotion(
        name="Welcome 10% Off",
        type="PERCENTAGE",
        value=Decimal("10.00"),
        code="SAVE10",
        min_purchase_amount=Decimal("50.00"),
        max_discount_amount=Decimal("20.00"),
        usage_limit=10,
        usage_count=0,
        applies_to="ALL",
        start_datetime=datetime.now(UTC) - timedelta(days=1),
        end_datetime=datetime.now(UTC) + timedelta(days=1),
        status="ACTIVE",
    )
    db.add(promo)
    await db.flush()

    service = PromotionService(db)

    # Below minimum cart
    res_low = await service.validate_coupon("SAVE10", cart_total=Decimal("30.00"))
    assert not res_low.valid
    assert "Minimum purchase" in res_low.message

    # Valid coupon
    res_valid = await service.validate_coupon("SAVE10", cart_total=Decimal("100.00"))
    assert res_valid.valid
    assert res_valid.discount_amount == Decimal("10.00")

    # Cap discount
    res_capped = await service.validate_coupon("SAVE10", cart_total=Decimal("300.00"))
    assert res_capped.valid
    assert res_capped.discount_amount == Decimal("20.00")

    # Record usage
    await service.record_usage(promo.id)
    assert promo.usage_count == 1
