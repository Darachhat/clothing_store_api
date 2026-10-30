"""Inventory background tasks."""
from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.inventory_tasks.check_low_stock")
def check_low_stock() -> dict:
    """Check for low stock items and prepare notifications."""
    from app.core.database import SyncSessionLocal
    from app.models.inventory import InventoryStock

    db = SyncSessionLocal()
    try:
        from sqlalchemy import select
        result = db.execute(
            select(InventoryStock).where(
                InventoryStock.quantity <= InventoryStock.reorder_level
            )
        )
        low_stock = result.scalars().all()

        if low_stock:
            logger.warning(f"Low stock alert: {len(low_stock)} variants below reorder level")
            # TODO: Send notification (Telegram/email) when notification service is configured

        return {"low_stock_count": len(low_stock)}
    finally:
        db.close()
