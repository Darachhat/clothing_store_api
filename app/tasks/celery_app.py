"""Celery application re-export from app.core.celery_app for backward compatibility."""
from app.core.celery_app import celery_app

__all__ = ["celery_app"]
