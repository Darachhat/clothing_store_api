"""Cashier Shift Sessions & Cash Drawer Float Management."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models import Branch, PosShift, PosTerminal, Sale, SalePayment, User
from app.schemas.shift_schema import (
    SHIFT_CLOSE_SCHEMA,
    SHIFT_OPEN_SCHEMA,
    SHIFT_RESPONSE_SCHEMA,
    SHIFT_SUMMARY_SCHEMA,
)

router = APIRouter(prefix="/shifts", tags=["Cashier Shifts"])


def _shift_eager_options():
    return (
        selectinload(PosShift.terminal),
        selectinload(PosShift.branch),
        selectinload(PosShift.cashier),
    )


@router.get("/active", response_model=SHIFT_RESPONSE_SCHEMA)
async def get_active_shift(
    terminal_id: Optional[UUID] = Query(None, description="POS Terminal UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PosShift:
    """Get currently open shift for a specific terminal or current cashier."""
    stmt = select(PosShift).options(*_shift_eager_options()).where(PosShift.status_code == "OPEN")

    if terminal_id:
        stmt = stmt.where(PosShift.terminal_id == terminal_id)
    else:
        stmt = stmt.where(PosShift.cashier_id == current_user.id)

    stmt = stmt.order_by(PosShift.opened_at.desc()).limit(1)
    result = await db.execute(stmt)
    shift = result.scalar_one_or_none()

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active open shift found for this terminal/cashier",
        )
    return shift


@router.post("/open", response_model=SHIFT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def open_shift(
    body: SHIFT_OPEN_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PosShift:
    """Start a new cashier shift with an opening cash float."""
    terminal = await db.get(PosTerminal, body.terminal_id)
    if not terminal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Terminal not found")
    if terminal.status_code != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Terminal '{terminal.name}' is currently {terminal.status_code}",
        )

    # Prevent concurrent duplicate open shifts on the same terminal
    existing = await db.execute(
        select(PosShift).where(
            PosShift.terminal_id == body.terminal_id,
            PosShift.status_code == "OPEN",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Terminal '{terminal.code}' already has an active open shift. Please close it first.",
        )

    shift = PosShift(
        terminal_id=body.terminal_id,
        branch_id=terminal.branch_id,
        cashier_id=current_user.id,
        opened_at=datetime.now(timezone.utc),
        opening_float_usd=body.opening_float_usd,
        opening_float_khr=body.opening_float_khr,
        status_code="OPEN",
        notes=body.notes,
    )
    terminal.last_active_at = datetime.now(timezone.utc)

    db.add(shift)
    await db.commit()

    result = await db.execute(
        select(PosShift).options(*_shift_eager_options()).where(PosShift.id == shift.id)
    )
    return result.scalar_one()


@router.get("/{id}/summary", response_model=SHIFT_SUMMARY_SCHEMA)
async def get_shift_summary(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> dict:
    """Calculate and return sales and drawer cash breakdown for a shift."""
    shift_res = await db.execute(
        select(PosShift).options(*_shift_eager_options()).where(PosShift.id == id)
    )
    shift = shift_res.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")

    # Fetch all completed/non-cancelled sales attributed to this shift
    sales_res = await db.execute(
        select(Sale)
        .options(selectinload(Sale.payments))
        .where(Sale.shift_id == shift.id, Sale.sale_status != "CANCELLED")
    )
    sales = list(sales_res.scalars().all())

    total_sales_count = len(sales)
    total_sales_amount = Decimal("0.00")
    cash_sales_amount = Decimal("0.00")
    cash_payments_count = 0
    aba_sales_amount = Decimal("0.00")
    aba_payments_count = 0
    card_sales_amount = Decimal("0.00")
    card_payments_count = 0
    bank_sales_amount = Decimal("0.00")

    for s in sales:
        total_sales_amount += Decimal(str(s.total))
        for p in s.payments:
            amt = Decimal(str(p.amount))
            method = (p.payment_method or "").upper()
            if method == "CASH":
                cash_sales_amount += amt
                cash_payments_count += 1
            elif "ABA" in method or "KHQR" in method:
                aba_sales_amount += amt
                aba_payments_count += 1
            elif "CARD" in method:
                card_sales_amount += amt
                card_payments_count += 1
            elif "BANK" in method:
                bank_sales_amount += amt

    expected_cash_usd = (shift.opening_float_usd or Decimal("0.00")) + cash_sales_amount
    expected_cash_khr = shift.opening_float_khr or Decimal("0.00")

    closing_cash_usd = shift.closing_cash_usd
    closing_cash_khr = shift.closing_cash_khr
    discrepancy_usd = (closing_cash_usd - expected_cash_usd) if closing_cash_usd is not None else None
    discrepancy_khr = (closing_cash_khr - expected_cash_khr) if closing_cash_khr is not None else None

    return {
        "shift_id": shift.id,
        "terminal_id": shift.terminal_id,
        "terminal_code": shift.terminal_code,
        "branch_id": shift.branch_id,
        "branch_name": shift.branch_name,
        "cashier_id": shift.cashier_id,
        "cashier_name": shift.cashier_name,
        "opened_at": shift.opened_at,
        "closed_at": shift.closed_at,
        "status_code": shift.status_code,
        "opening_float_usd": shift.opening_float_usd,
        "opening_float_khr": shift.opening_float_khr,
        "total_sales_count": total_sales_count,
        "total_sales_amount": total_sales_amount,
        "cash_sales_amount": cash_sales_amount,
        "cash_payments_count": cash_payments_count,
        "aba_sales_amount": aba_sales_amount,
        "aba_payments_count": aba_payments_count,
        "card_sales_amount": card_sales_amount,
        "card_payments_count": card_payments_count,
        "bank_sales_amount": bank_sales_amount,
        "expected_cash_usd": expected_cash_usd,
        "expected_cash_khr": expected_cash_khr,
        "closing_cash_usd": closing_cash_usd,
        "closing_cash_khr": closing_cash_khr,
        "discrepancy_usd": discrepancy_usd,
        "discrepancy_khr": discrepancy_khr,
        "notes": shift.notes,
    }


@router.post("/{id}/close", response_model=SHIFT_SUMMARY_SCHEMA)
async def close_shift(
    id: UUID,
    body: SHIFT_CLOSE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Close an active shift, recording actual drawer cash count and reconciliation."""
    shift_res = await db.execute(
        select(PosShift).options(*_shift_eager_options()).where(PosShift.id == id)
    )
    shift = shift_res.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    if shift.status_code != "OPEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Shift is already {shift.status_code}",
        )

    # Calculate expected cash from sales
    sales_res = await db.execute(
        select(Sale)
        .options(selectinload(Sale.payments))
        .where(Sale.shift_id == shift.id, Sale.sale_status != "CANCELLED")
    )
    sales = list(sales_res.scalars().all())

    cash_sales_amount = Decimal("0.00")
    for s in sales:
        for p in s.payments:
            if (p.payment_method or "").upper() == "CASH":
                cash_sales_amount += Decimal(str(p.amount))

    expected_cash_usd = (shift.opening_float_usd or Decimal("0.00")) + cash_sales_amount
    expected_cash_khr = shift.opening_float_khr or Decimal("0.00")

    shift.closed_at = datetime.now(timezone.utc)
    shift.status_code = "CLOSED"
    shift.closing_cash_usd = body.closing_cash_usd
    shift.closing_cash_khr = body.closing_cash_khr
    shift.expected_cash_usd = expected_cash_usd
    shift.expected_cash_khr = expected_cash_khr
    if body.notes:
        shift.notes = f"{shift.notes}\n{body.notes}" if shift.notes else body.notes

    await db.commit()

    return await get_shift_summary(id=id, db=db, _=current_user)


@router.get("", response_model=list[SHIFT_RESPONSE_SCHEMA], include_in_schema=False)
@router.get("/", response_model=list[SHIFT_RESPONSE_SCHEMA])
async def list_shifts(
    terminal_id: Optional[UUID] = Query(None, description="Filter by terminal UUID"),
    cashier_id: Optional[UUID] = Query(None, description="Filter by cashier UUID"),
    status_code: Optional[str] = Query(None, description="Filter by status (OPEN/CLOSED)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[PosShift]:
    """List recent shifts with optional terminal/cashier/status filters."""
    stmt = select(PosShift).options(*_shift_eager_options())

    if terminal_id:
        stmt = stmt.where(PosShift.terminal_id == terminal_id)
    if cashier_id:
        stmt = stmt.where(PosShift.cashier_id == cashier_id)
    if status_code:
        stmt = stmt.where(PosShift.status_code == status_code)

    stmt = stmt.order_by(PosShift.opened_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{id}", response_model=SHIFT_RESPONSE_SCHEMA)
async def get_shift(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> PosShift:
    """Get single shift details."""
    result = await db.execute(
        select(PosShift).options(*_shift_eager_options()).where(PosShift.id == id)
    )
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    return shift

