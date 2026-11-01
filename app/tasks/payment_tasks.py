"""Payment background tasks.

Beat schedule (defined here, registered in celery_app.py):
- reconcile_pending_payments: every 60 seconds
  - re-checks every PENDING transaction with ABA through PaymentService.refresh_status,
    i.e. the exact same code path the POS poller uses (so a sale completed by the
    reconciler gets stock movements, payments etc. — never a half-completed sale)
  - marks overdue ones EXPIRED (only AFTER a final check with ABA, so a QR paid in the
    last seconds is never flagged expired) and closes them at ABA
  - sends Telegram alerts on expiry (approval alerts are sent by refresh_status)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.payment_tasks.reconcile_pending_payments")
def reconcile_pending_payments() -> dict:
    """Reconcile all PENDING payment transactions."""
    result = asyncio.run(_reconcile())
    logger.info(f"[PaymentTask] reconcile done: {result}")
    return result


async def _reconcile() -> dict:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models import PaymentTransaction
    from app.services.payment_service import PaymentService
    from app.services.payway import payway_client

    # asyncio.run() creates a fresh event loop on every task run, so the global
    # pooled async engine (bound to a previous loop) can't be reused here.
    engine = create_async_engine(settings.ASYNC_DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    approved = expired = failed = 0
    try:
        async with session_factory() as db:
            pending_ids = (
                await db.execute(
                    select(PaymentTransaction.id).where(PaymentTransaction.status == "PENDING")
                )
            ).scalars().all()

        for tx_id in pending_ids:
            async with session_factory() as db:
                try:
                    # Final check with ABA; completes the sale properly on APPROVED.
                    tx = await PaymentService(db).refresh_status(tx_id)
                    now = datetime.now(timezone.utc)

                    if tx.status == "APPROVED":
                        approved += 1
                        logger.info(f"[PaymentTask] tran_id={tx.tran_id} APPROVED (reconciler)")
                    else:
                        overdue = (
                            tx.status == "PENDING" and tx.expires_at and now > tx.expires_at
                        )
                        if overdue:
                            try:
                                await payway_client.close_transaction(tx.tran_id)
                            except Exception as exc:
                                logger.warning(f"[PaymentTask] close failed {tx.tran_id}: {exc}")
                            tx.status = "EXPIRED"

                        if tx.status == "EXPIRED":
                            expired += 1
                            logger.info(f"[PaymentTask] tran_id={tx.tran_id} EXPIRED")
                            try:
                                from app.tasks.notification_tasks import _send_tg

                                _send_tg(
                                    f"⏰ *ABA KHQR Expired*\n"
                                    f"Tran ID: `{tx.tran_id}`\n"
                                    f"Amount: `${float(tx.amount):.2f}`"
                                )
                            except Exception:
                                pass

                    await db.commit()
                except Exception as exc:
                    await db.rollback()
                    failed += 1
                    logger.warning(f"[PaymentTask] Reconcile failed for {tx_id}: {exc}")
    finally:
        await engine.dispose()

    return {"approved": approved, "expired": expired, "failed": failed}
