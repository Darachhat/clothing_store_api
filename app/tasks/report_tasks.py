"""Report background tasks."""
from datetime import UTC, datetime, timedelta

from loguru import logger

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.report_tasks.send_daily_sales_summary")
def send_daily_sales_summary() -> dict:
    """Generate and send daily sales summary report."""
    from sqlalchemy import and_, func, select

    from app.core.database import SyncSessionLocal
    from app.models import Sale
    from app.tasks.notification_tasks import _send_tg

    yesterday = datetime.now(UTC).date() - timedelta(days=1)
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
        msg = (
            f"*Daily Sales Summary ({yesterday})*\n"
            f"Total Orders: {row.count}\n"
            f"Total Revenue: ${float(row.revenue):.2f}"
        )
        summary["notified"] = _send_tg(msg)
        return summary
    finally:
        db.close()
