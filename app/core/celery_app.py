import asyncio
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.config import settings
from app.core.constants import DEFAULT_TIMEZONE
from app.core.utils.http_client import (
    close_global_httpx_client
    , create_httpx_client
    , set_global_httpx_client
)

celery_app = Celery(
    "clothing_store"
    , broker  = settings.REDIS_URL
    , backend = settings.REDIS_URL
    , include = [
        "app.tasks.inventory_tasks"
        , "app.tasks.report_tasks"
        , "app.tasks.notification_tasks"
        , "app.tasks.payment_tasks"
        , "app.tasks.log_rotate_job"
        , "app.tasks.sample_task"
    ]
)

celery_app.conf.update(
    task_serializer       = "json"
    , accept_content      = ["json"]
    , result_serializer   = "json"
    , timezone            = DEFAULT_TIMEZONE
    , enable_utc          = True
    , task_track_started  = True
    , task_time_limit     = 3600
    , beat_schedule       = {
        "rotate-daily-logs": {
            "task"      : "app.tasks.log_rotate_job.rotate_daily_logs"
            , "schedule" : crontab(hour=0, minute=0)
        }
        , "daily-sales-summary": {
            "task"      : "app.tasks.report_tasks.send_daily_sales_summary"
            , "schedule" : 60 * 60 * 24
        }
        , "low-stock-check": {
            "task"      : "app.tasks.inventory_tasks.check_low_stock"
            , "schedule" : 60 * 60
        }
        , "reconcile-pending-payments": {
            "task"      : "app.tasks.payment_tasks.reconcile_pending_payments"
            , "schedule" : 60
        }
        , "cleanup-expired-tokens": {
            "task"      : "app.tasks.inventory_tasks.cleanup_expired_tokens"
            , "schedule" : 60 * 60 * 6
        }
    }
)


@worker_process_init.connect
def init_worker_httpx_client(**kwargs) -> None:
    set_global_httpx_client(create_httpx_client())


@worker_process_shutdown.connect
def shutdown_worker_httpx_client(**kwargs) -> None:
    try:
        asyncio.run(close_global_httpx_client())
    except Exception:
        set_global_httpx_client(None)


celery_app.autodiscover_tasks(["app.tasks"])

