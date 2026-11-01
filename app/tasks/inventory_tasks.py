"""Inventory background tasks."""
from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.inventory_tasks.check_low_stock")
def check_low_stock() -> dict:
    """Check for low stock items and dispatch Telegram notification when configured."""
    from sqlalchemy import select

    from app.core.database import SyncSessionLocal
    from app.models import InventoryStock
    from app.tasks.notification_tasks import _send_tg

    db = SyncSessionLocal()
    try:
        result = db.execute(
            select(InventoryStock).where(
                InventoryStock.quantity <= InventoryStock.reorder_level
            )
        )
        low_stock = result.scalars().all()

        notified = False
        if low_stock:
            logger.warning(f"Low stock alert: {len(low_stock)} variants below reorder level")
            msg = (
                f"*Low Stock Alert*\n"
                f"{len(low_stock)} inventory item(s) are at or below their reorder level."
            )
            notified = _send_tg(msg)

        return {"low_stock_count": len(low_stock), "notified": notified}
    finally:
        db.close()


@celery_app.task(name="app.tasks.inventory_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict:
    """Delete expired or revoked refresh tokens from public.refresh_tokens."""
    from datetime import UTC, datetime
    from sqlalchemy import delete, or_

    from app.core.database import SyncSessionLocal
    from app.models import RefreshToken

    db = SyncSessionLocal()
    try:
        now = datetime.now(UTC)
        res = db.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.revoked.is_(True),
                    RefreshToken.expires_at < now,
                )
            )
        )
        db.commit()
        deleted = int(res.rowcount or 0)
        logger.info(f"Cleaned up {deleted} expired/revoked refresh token(s)")
        return {"deleted_tokens": deleted}
    finally:
        db.close()
