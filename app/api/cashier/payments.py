"""ABA PayWay payment endpoints for the Cashier POS lane.

Routes (all under /api/cashier/v1/payments/aba/):
    POST  /khqr              — create QR for a DRAFT sale
    GET   /{payment_id}/status — poll status (rate-limited via Redis)
    POST  /{payment_id}/cancel — cancel a PENDING QR
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models import PaymentTransaction, User
from app.schemas.payment_schema import (
    PAYMENT_KHQR_CREATE_REQUEST_SCHEMA
    , PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA
    , PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA
    , PAYMENT_TRANSACTION_RESPONSE_SCHEMA
)
from app.services.payment_service import PAYMENT_SERVICE, PAYMENT_SERVICE

router = APIRouter(prefix="/payments/aba", tags=["ABA PayWay"])

# Backward-compatible schema aliases
CreateKhqrRequest         = PAYMENT_KHQR_CREATE_REQUEST_SCHEMA
CreatePurchaseFormRequest = PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA
PurchaseFormOut           = PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA
PaymentTransactionOut     = PAYMENT_TRANSACTION_RESPONSE_SCHEMA


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/purchase-form", response_model=PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_purchase_form(
    body: PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA:
    """Generate form payload and HMAC-SHA512 hash for PayWay Checkout modal (cards or all).

    Returns form input fields and target action URL for AbaPayway.checkout().
    """
    svc = PAYMENT_SERVICE(db)
    action_url, form_data, tx = await svc.create_purchase_for_sale(
        sale_id=body.sale_id,
        payment_option=body.payment_option,
        created_by=current_user.id,
    )
    await db.commit()

    return PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA(
        action_url=action_url,
        form_data=form_data,
        payment_id=tx.id,
        tran_id=tx.tran_id,
        amount=float(tx.amount),
        currency=tx.currency,
    )


@router.post("/khqr", response_model=PAYMENT_TRANSACTION_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_khqr(
    body: PAYMENT_KHQR_CREATE_REQUEST_SCHEMA,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PAYMENT_TRANSACTION_RESPONSE_SCHEMA:
    """Generate an ABA KHQR QR code for a DRAFT sale.

    Returns the transaction record including a base64 PNG data URL
    (qr_image) ready to display in the POS.
    """
    svc = PAYMENT_SERVICE(db)
    tx = await svc.create_khqr_for_sale(
        sale_id=body.sale_id,
        created_by=current_user.id,
    )
    await db.commit()

    return PAYMENT_TRANSACTION_RESPONSE_SCHEMA(
        id=tx.id,
        tran_id=tx.tran_id,
        sale_id=tx.sale_id,
        status=tx.status,
        amount=float(tx.amount),
        currency=tx.currency,
        qr_string=tx.qr_string,
        qr_image=getattr(tx, "qr_image", None),
        checkout_url=tx.checkout_url,
        apv=tx.apv,
        expires_at=tx.expires_at.isoformat() if tx.expires_at else None,
        paid_at=tx.paid_at.isoformat() if tx.paid_at else None,
    )


@router.get("/{payment_id}/status", response_model=PAYMENT_TRANSACTION_RESPONSE_SCHEMA)
async def get_payment_status(
    payment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PAYMENT_TRANSACTION_RESPONSE_SCHEMA:
    """Poll the current status of a payment transaction.

    If PENDING, re-checks with ABA (rate-limited: at most once every 3 s via Redis).
    On APPROVED, the sale will already have been completed server-side.
    """
    should_recheck = True
    try:
        from app.core.redis import get_redis_client
        redis_client = get_redis_client()
        rk = f"payway:check:{payment_id}"
        if await redis_client.exists(rk):
            should_recheck = False
        else:
            await redis_client.setex(rk, 3, "1")
    except Exception:
        pass  # Redis down — still allow the check

    svc = PAYMENT_SERVICE(db)
    if should_recheck:
        tx = await svc.refresh_status(payment_id)
    else:
        result = await db.execute(
            select(PaymentTransaction).where(PaymentTransaction.id == payment_id)
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    await db.commit()

    return PAYMENT_TRANSACTION_RESPONSE_SCHEMA(
        id=tx.id,
        tran_id=tx.tran_id,
        sale_id=tx.sale_id,
        status=tx.status,
        amount=float(tx.amount),
        currency=tx.currency,
        qr_string=tx.qr_string,
        checkout_url=tx.checkout_url,
        apv=tx.apv,
        expires_at=tx.expires_at.isoformat() if tx.expires_at else None,
        paid_at=tx.paid_at.isoformat() if tx.paid_at else None,
    )


@router.post("/{payment_id}/cancel", response_model=PAYMENT_TRANSACTION_RESPONSE_SCHEMA)
async def cancel_payment(
    payment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PAYMENT_TRANSACTION_RESPONSE_SCHEMA:
    """Cancel a PENDING QR payment.

    Calls ABA Close Transaction and marks the transaction CANCELLED.
    The DRAFT sale is NOT automatically cancelled here — the POS should
    call the sale cancel endpoint separately if needed.
    """
    svc = PAYMENT_SERVICE(db)
    tx = await svc.cancel(payment_id)
    await db.commit()

    return PAYMENT_TRANSACTION_RESPONSE_SCHEMA(
        id=tx.id,
        tran_id=tx.tran_id,
        sale_id=tx.sale_id,
        status=tx.status,
        amount=float(tx.amount),
        currency=tx.currency,
        apv=tx.apv,
        expires_at=tx.expires_at.isoformat() if tx.expires_at else None,
        paid_at=tx.paid_at.isoformat() if tx.paid_at else None,
    )
