import time
from app.core.celery_app import celery_app
from app.core.logger import logger


@celery_app.task(bind=True, max_retries=3)
def process_audit_log_task(self, request_id: str, action: str) -> bool:
    """
    Sample background Celery task for audit logging or notification dispatch.
    """
    logger.info(f"Processing background audit task: request_id={request_id}, action={action}")
    time.sleep(1)
    return True


async def process_in_memory_task(payload: dict) -> None:
    """
    Sample in-memory asyncio task executed via background tasks.
    """
    logger.info(f"Processing in-memory async task with payload: {payload}")

