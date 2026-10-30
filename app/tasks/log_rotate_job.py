import asyncio
from typing import Any, Dict

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logger import logger, rotate_logs
from app.services.telegram_service import TELEGRAM_SERVICE


@celery_app.task(name="app.tasks.log_rotate_job.rotate_daily_logs", bind=True, max_retries=2)
def rotate_daily_logs(self) -> Dict[str, Any]:
    """
    Daily scheduled task to archive past-date log lines into logs/archived/YYYY-MM-DD-{log_type}.log
    and optionally send a Telegram notification summary.
    """
    logger.info("[LOG_ROTATE_JOB] Starting daily log rotation...")
    summary = rotate_logs(retention_days=settings.LOG_RETENTION_DAYS)
    logger.info(f"[LOG_ROTATE_JOB] Log rotation finished: {summary}")

    if settings.ENABLE_TELEGRAM_ALERT and settings.TELEGRAM_ALERT_CHAT_CODE:
        try:
            asyncio.run(TELEGRAM_SERVICE.send_log_rotation_report(rotation_summary=summary))
        except Exception as exc:
            logger.warning(f"[LOG_ROTATE_JOB] Telegram report skipped/failed: {str(exc)}")

    return summary

