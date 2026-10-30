from typing import Any, Optional
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:
    AsyncIOScheduler = None  # type: ignore[assignment,misc]

from app.core.constants import DEFAULT_TIMEZONE
from app.core.logger import logger


class APP_SCHEDULER:
    _scheduler : Optional[Any] = None

    @classmethod
    def get_scheduler(cls) -> Optional[Any]:
        if AsyncIOScheduler is None:
            return None
        if cls._scheduler is None:
            cls._scheduler = AsyncIOScheduler(timezone=DEFAULT_TIMEZONE)
        return cls._scheduler

    @classmethod
    def start(cls) -> None:
        if AsyncIOScheduler is None:
            return
        try:
            cls._scheduler = AsyncIOScheduler(timezone=DEFAULT_TIMEZONE)
            cls._scheduler.start()
            logger.info("APScheduler initialized and started successfully.")
        except Exception as exc:
            logger.warning(f"APScheduler start skipped: {exc}")

    @classmethod
    def shutdown(cls) -> None:
        scheduler      = cls._scheduler
        cls._scheduler = None
        if scheduler is not None and getattr(scheduler, "running", False):
            try:
                scheduler.shutdown(wait=False)
                logger.info("APScheduler shut down successfully.")
            except Exception:
                pass
