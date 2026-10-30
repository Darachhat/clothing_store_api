"""Report background tasks."""
from datetime import date, timedelta

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.report_tasks.send_daily_sales_summary")
def send_daily_sales_summary() -> dict:
    """Generate and send daily sales summary report."""
    from sqlalchemy import and_, func, select

    from app.core.database import SyncSessionLocal
    from app.models.sale import Sale

    yesterday = date.today() - timedelta(days=1)
    db = SyncSessionLocal()
    try:
        result = db.execute(
            select(
                func.count(Sale.id).label("count"),
                func.coalesce(func.sum(Sale.total), 0).label("revenue"),
            ).where(
                and_(
                    Sale.sale_status == "COMPLETED",
                    func.date(Sale.created_at) == yesterday,
                )
            )
        )
        row = result.one()
        summary = {
            "date": str(yesterday),
            "total_sales": row.count,
            "total_revenue": float(row.revenue),
        }
        logger.info(f"Daily summary: {summary}")
        # TODO: Send via Telegram/email
        return summary
    finally:
        db.close()
