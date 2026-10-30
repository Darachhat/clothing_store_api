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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.payment import PaymentTransaction
from app.models.user import User
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments/aba", tags=["ABA PayWay"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateKhqrRequest(BaseModel):
    sale_id: UUID


class CreatePurchaseFormRequest(BaseModel):
    sale_id: UUID
    payment_option: str = "cards"  # "cards" | "abapay_khqr" | ""


class PurchaseFormOut(BaseModel):
    action_url: str
    form_data: dict[str, str]
    payment_id: UUID
    tran_id: str
    amount: float
    currency: str


class PaymentTransactionOut(BaseModel):
    id: UUID
    tran_id: str
    sale_id: UUID | None
    status: str
    amount: float
    currency: str
    qr_string: str | None = None
    qr_image: str | None = None      # base64 data URL — only in create response
    checkout_url: str | None = None
    apv: str | None = None
    expires_at: str | None = None
    paid_at: str | None = None

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/purchase-form", response_model=PurchaseFormOut, status_code=status.HTTP_201_CREATED)
async def create_purchase_form(
    body: CreatePurchaseFormRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PurchaseFormOut:
    """Generate form payload and HMAC-SHA512 hash for PayWay Checkout modal (cards or all).

    Returns form input fields and target action URL for AbaPayway.checkout().
    """
    svc = PaymentService(db)
    action_url, form_data, tx = await svc.create_purchase_for_sale(
        sale_id=body.sale_id,
        payment_option=body.payment_option,
        created_by=current_user.id,
    )
    await db.commit()

    return PurchaseFormOut(
        action_url=action_url,
        form_data=form_data,
        payment_id=tx.id,
        tran_id=tx.tran_id,
        amount=float(tx.amount),
        currency=tx.currency,
    )


@router.post("/khqr", response_model=PaymentTransactionOut, status_code=status.HTTP_201_CREATED)
async def create_khqr(
    body: CreateKhqrRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionOut:
    """Generate an ABA KHQR QR code for a DRAFT sale.

    Returns the transaction record including a base64 PNG data URL
    (qr_image) ready to display in the POS.
    """
    svc = PaymentService(db)
    tx = await svc.create_khqr_for_sale(
        sale_id=body.sale_id,
        created_by=current_user.id,
    )
    await db.commit()

    out = PaymentTransactionOut(
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
    return out


@router.get("/{payment_id}/status", response_model=PaymentTransactionOut)
async def get_payment_status(
    payment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionOut:
    """Poll the current status of a payment transaction.

    If PENDING, re-checks with ABA (rate-limited: at most once every 3 s via Redis).
    On APPROVED, the sale will already have been completed server-side.
    """
    # Rate-limit: skip ABA call if we checked within the last 3 seconds
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

    svc = PaymentService(db)
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

    return PaymentTransactionOut(
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


@router.post("/{payment_id}/cancel", response_model=PaymentTransactionOut)
async def cancel_payment(
    payment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionOut:
    """Cancel a PENDING QR payment.

    Calls ABA Close Transaction and marks the transaction CANCELLED.
    The DRAFT sale is NOT automatically cancelled here — the POS should
    call the sale cancel endpoint separately if needed.
    """
    svc = PaymentService(db)
    tx = await svc.cancel(payment_id)
    await db.commit()

    return PaymentTransactionOut(
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
