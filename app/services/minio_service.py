"""Legacy MinIO Service Adapter.

Redirects all operations to Cloudflare R2 Object Storage Service (app.services.r2_service).
"""
from app.services.r2_service import (
    R2_SERVICE,
    R2_STORAGE_SERVICE,
    MINIO_SERVICE,
)

__all__ = ["MINIO_SERVICE", "R2_SERVICE", "R2_STORAGE_SERVICE"]
