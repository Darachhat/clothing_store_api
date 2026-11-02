"""Public ABA PayWay pushback (callback) endpoint.

ABA POSTs to this URL when a transaction status changes.
We NEVER trust the pushback body as proof of payment.
We only use it as a trigger to call Check Transaction ourselves.

Route: POST /api/payments/aba/pushback
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import PaymentTransaction
from app.services.payment_service import PAYMENT_SERVICE

router = APIRouter(prefix="/api/payments/aba", tags=["ABA PayWay Callback"])


class PushbackBody(BaseModel):
    """ABA pushback payload (fields we care about; rest are ignored)."""
    tran_id: str | None = None
    apv: str | None = None
    status: str | None = None
    return_params: str | None = None

    model_config = {"extra": "allow"}


@router.post("/pushback")
async def aba_pushback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive ABA PayWay payment notification.

    ABA may POST as JSON or form-encoded. We parse both.
    Then we look up the transaction by tran_id and call refresh_status()
    which verifies the payment directly with ABA.
    """
    # Parse body — ABA may send multipart or JSON
    try:
        body_dict = await request.json()
    except Exception:
        try:
            body_dict = dict(await request.form())
        except Exception:
            body_dict = {}

    tran_id = body_dict.get("tran_id", "")
    logger.info(f"[Pushback] Received ABA callback tran_id={tran_id} body={body_dict}")

    if not tran_id:
        # ABA still expects 200
        return {"status": "ok"}

    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.tran_id == tran_id)
    )
    tx = result.scalar_one_or_none()

    if tx:
        svc = PAYMENT_SERVICE(db)
        await svc.refresh_status(tx.id)
        await db.commit()
    else:
        logger.warning(f"[Pushback] No transaction found for tran_id={tran_id}")

    # ABA requires a 200 response — always return ok
    return {"status": "ok"}
