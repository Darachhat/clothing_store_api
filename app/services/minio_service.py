"""MinIO Object Storage Service for attachments, product images, and documents."""
from __future__ import annotations

import io
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import BinaryIO, Optional

from fastapi import HTTPException, UploadFile, status
from loguru import logger
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class MinioService:
    def __init__(self) -> None:
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.public_url = settings.MINIO_PUBLIC_URL.rstrip("/")
        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
            self._client = Minio(
                endpoint=endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_USE_SSL,
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
        """Create bucket if not exists and set public download policy."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created MinIO bucket: '{self.bucket_name}'")

            # Set public-read policy so browser can load attachment images directly
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}"],
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"],
                    },
                ],
            }
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            logger.info(f"Public read policy set on MinIO bucket: '{self.bucket_name}'")
        except Exception as e:
            logger.warning(f"MinIO bucket initialization notice: {e}")

    ALLOWED_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
        ".pdf", ".csv", ".txt", ".xlsx", ".xls", ".doc", ".docx",
    }
    BLOCKED_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".sh", ".ps1", ".php", ".jsp", ".py", ".rb", ".pl", ".dll", ".so", ".msi",
    }

    def upload_file(
        self,
        file: UploadFile,
        folder: str = "attachments",
        max_size_mb: int = settings.MAX_UPLOAD_SIZE_MB,
    ) -> dict:
        """Upload a FastAPI UploadFile object to MinIO."""
        self.ensure_bucket_exists()

        # Sanitize folder and filename
        folder = folder.strip("/ ") or "attachments"
        original_name = os.path.basename(file.filename or "attachment")
        ext = os.path.splitext(original_name)[1].lower()
        if ext in self.BLOCKED_EXTENSIONS or (ext and ext not in self.ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{ext}' is not allowed",
            )
        unique_id = str(uuid.uuid4())
        safe_name = f"{unique_id[:8]}_{original_name.replace(' ', '_')}"
        now = datetime.utcnow()
        object_name = f"{folder}/{now.strftime('%Y/%m')}/{safe_name}"

        # Read content
        try:
            content = file.file.read()
            size = len(content)
        except Exception as e:
            logger.error(f"Failed to read file content: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not read upload file: {e}",
            )

        # Validate size
        max_bytes = max_size_mb * 1024 * 1024
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {max_size_mb}MB",
            )

        content_type = file.content_type or "application/octet-stream"

        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=io.BytesIO(content),
                length=size,
                content_type=content_type,
            )
            logger.info(f"Successfully uploaded {object_name} ({size} bytes) to MinIO")
        except S3Error as e:
            logger.error(f"MinIO upload error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage service error: {e}",
            )

        file_url = f"{self.public_url}/{self.bucket_name}/{object_name}"

        return {
            "id": unique_id,
            "filename": original_name,
            "object_name": object_name,
            "url": file_url,
            "content_type": content_type,
            "size": size,
            "bucket": self.bucket_name,
            "created_at": now.isoformat(),
        }

    def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        folder: str = "attachments",
    ) -> dict:
        """Upload raw bytes to MinIO."""
        self.ensure_bucket_exists()
        folder = folder.strip("/ ") or "attachments"
        unique_id = str(uuid.uuid4())
        safe_name = f"{unique_id[:8]}_{filename.replace(' ', '_')}"
        now = datetime.utcnow()
        object_name = f"{folder}/{now.strftime('%Y/%m')}/{safe_name}"
        size = len(data)

        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=io.BytesIO(data),
                length=size,
                content_type=content_type,
            )
        except S3Error as e:
            logger.error(f"MinIO upload_bytes error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage error: {e}",
            )

        file_url = f"{self.public_url}/{self.bucket_name}/{object_name}"
        return {
            "id": unique_id,
            "filename": filename,
            "object_name": object_name,
            "url": file_url,
            "content_type": content_type,
            "size": size,
            "bucket": self.bucket_name,
            "created_at": now.isoformat(),
        }

    def delete_file(self, object_name: str) -> bool:
        """Delete an object from MinIO."""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Deleted {object_name} from MinIO")
            return True
        except S3Error as e:
            logger.warning(f"MinIO delete error for {object_name}: {e}")
            return False

    def get_presigned_url(self, object_name: str, expires_hours: int = 24) -> str:
        """Generate a presigned GET URL for secure access."""
        try:
            return self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(hours=expires_hours),
            )
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            return f"{self.public_url}/{self.bucket_name}/{object_name}"

    def list_files(self, prefix: str = "", limit: int = 100) -> list[dict]:
        """List objects in the bucket with optional prefix."""
        self.ensure_bucket_exists()
        results = []
        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            for i, obj in enumerate(objects):
                if i >= limit:
                    break
                results.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "url": f"{self.public_url}/{self.bucket_name}/{obj.object_name}",
                    "etag": obj.etag,
                })
        except Exception as e:
            logger.error(f"Failed to list objects in MinIO: {e}")
        return results


# Global singleton instance
minio_service = MinioService()
