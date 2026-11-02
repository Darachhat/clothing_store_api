"""Asynchronous background tasks for checkout optimizations.

Offloads non-critical post-checkout side effects (audit logging, loyalty points,
cache version invalidation) from the cashier's critical path so the HTTP response
returns immediately.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def bg_record_sale_audit(
    user_id: Optional[UUID],
    sale_id: UUID,
    invoice_number: str,
    total: str,
    payment_status: str,
) -> None:
    """Record sale completion audit entry in the background."""
    try:
        async with AsyncSessionLocal() as db:
            from app.services.audit_service import AUDIT_SERVICE

            await AUDIT_SERVICE.record(
                db,
                action="SALE_COMPLETED",
                entity_type="sale",
                entity_id=sale_id,
                user_id=user_id,
                new_data={
                    "invoice_number": invoice_number,
                    "total": str(total),
                    "payment_status": payment_status,
                },
            )
            await db.commit()
            logger.debug(f"[BG_TASK] Audit recorded for sale {invoice_number}")
    except Exception as exc:
        logger.warning(f"[BG_TASK] Failed to record audit for sale {invoice_number}: {exc}")


async def bg_award_loyalty_points(
    customer_id: UUID,
    points: int,
    sale_id: UUID,
    invoice_number: str,
) -> None:
    """Calculate and write customer loyalty points in the background."""
    if points <= 0:
        return
    try:
        async with AsyncSessionLocal() as db:
            from app.services.customer_service import CUSTOMER_SERVICE

            cust_svc = CUSTOMER_SERVICE(db)
            await cust_svc.award_sale_points(
                customer_id=customer_id,
                points=points,
                sale_id=sale_id,
                invoice_number=invoice_number,
            )
            await db.commit()
            logger.info(f"[BG_TASK] Awarded {points} loyalty points to customer {customer_id} for sale {invoice_number}")
    except Exception as exc:
        logger.warning(f"[BG_TASK] Failed to award loyalty points for sale {invoice_number}: {exc}")


async def bg_increment_inventory_cache() -> None:
    """Increment Redis catalog inventory cache version in the background."""
    try:
        async with AsyncSessionLocal() as db:
            from app.services.product_service import PRODUCT_SERVICE

            new_v = await PRODUCT_SERVICE.increment_inventory_version(db)
            logger.debug(f"[BG_TASK] Inventory cache version incremented to {new_v}")
    except Exception as exc:
        logger.warning(f"[BG_TASK] Failed to increment inventory version: {exc}")

