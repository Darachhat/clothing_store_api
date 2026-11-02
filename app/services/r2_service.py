"""Cloudflare R2 Object Storage Service (S3-compatible API).

Replaces legacy MinIO storage with zero-egress Cloudflare R2 object storage.
Supports automated fallback to local disk storage when R2 credentials are not yet configured.
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None  # type: ignore[assignment]
    Config = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment, misc]
    BOTO3_AVAILABLE = False

from fastapi import HTTPException, UploadFile, status
from loguru import logger

from app.core.config import settings


class R2_STORAGE_SERVICE:
    """Enterprise Cloudflare R2 / S3 Object Storage Service."""

    _instance: Optional[R2_STORAGE_SERVICE] = None

    ALLOWED_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg",
        ".pdf", ".csv", ".txt", ".xlsx", ".xls", ".doc", ".docx",
    }
    BLOCKED_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".sh", ".ps1", ".php", ".jsp", ".py", ".rb", ".pl", ".dll", ".so", ".msi",
    }

    def __init__(self) -> None:
        self.account_id   = settings.R2_ACCOUNT_ID
        self.endpoint_url = (
            settings.R2_ENDPOINT_URL.rstrip("/")
            if settings.R2_ENDPOINT_URL
            else f"https://{self.account_id}.r2.cloudflarestorage.com"
        )
        self.access_key_id     = settings.R2_ACCESS_KEY_ID
        self.secret_access_key = settings.R2_SECRET_ACCESS_KEY
        self.bucket_name       = settings.R2_BUCKET_NAME or "clothing-store"
        self.public_url        = settings.R2_PUBLIC_URL.rstrip("/")
        self._client: Optional[Any] = None
        self._logged_no_cred = False

    @classmethod
    def get_instance(cls) -> R2_STORAGE_SERVICE:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def _is_configured(self) -> bool:
        return bool(BOTO3_AVAILABLE and self.access_key_id and self.secret_access_key)

    @classmethod
    def is_configured(cls) -> bool:
        return cls.get_instance()._is_configured

    @classmethod
    def get_client(cls) -> Optional[Any]:
        return cls.get_instance().client

    @property
    def client(self) -> Optional[Any]:
        if not BOTO3_AVAILABLE:
            if not self._logged_no_cred:
                logger.warning("boto3 is not installed in the current environment. Running storage in local disk fallback mode.")
                self._logged_no_cred = True
            return None

        if not self._is_configured:
            if not self._logged_no_cred:
                logger.info("Cloudflare R2 credentials (R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY) not provided. Running in local fallback mode.")
                self._logged_no_cred = True
            return None

        if self._client is None:
            try:
                self._client = boto3.client(
                    service_name          = "s3",
                    endpoint_url          = self.endpoint_url,
                    aws_access_key_id     = self.access_key_id,
                    aws_secret_access_key = self.secret_access_key,
                    region_name           = "auto",
                    config                = Config(
                        signature_version = "s3v4",
                        s3                = {"addressing_style": "path"},
                        retries           = {"max_attempts": 3, "mode": "standard"},
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to initialize Cloudflare R2 client: {e}")
                self._client = None
        return self._client

    def _ensure_bucket_exists(self) -> None:
        """Verify R2 bucket connectivity or auto-create bucket if permitted."""
        if not self._is_configured:
            logger.info("R2 bucket check skipped: R2 credentials not configured.")
            return

        c = self.client
        if not c:
            return

        try:
            c.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Cloudflare R2 bucket '{self.bucket_name}' verified successfully.")
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("404", "NoSuchBucket"):
                try:
                    c.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created Cloudflare R2 bucket: '{self.bucket_name}'")
                except Exception as create_err:
                    logger.warning(f"Notice: R2 bucket '{self.bucket_name}' could not be auto-created: {create_err}")
            else:
                logger.warning(f"Notice: Cloudflare R2 bucket check: {e}")
        except Exception as e:
            logger.warning(f"Notice: Cloudflare R2 connectivity notice: {e}")

    @classmethod
    def ensure_bucket_exists(cls) -> None:
        cls.get_instance()._ensure_bucket_exists()

    def _build_public_url(self, object_name: str) -> str:
        clean_name = object_name.lstrip("/")
        return f"{self.public_url}/{clean_name}"

    def _upload_file(
        self
        , file        : UploadFile
        , folder      : str = "attachments"
        , max_size_mb : int = settings.MAX_UPLOAD_SIZE_MB
    ) -> Dict[str, Any]:
        """Upload a FastAPI UploadFile object to Cloudflare R2 or local disk fallback."""
        folder        = folder.strip("/ ") or "attachments"
        original_name = os.path.basename(file.filename or "attachment")
        ext           = os.path.splitext(original_name)[1].lower()
        if ext in self.BLOCKED_EXTENSIONS or (ext and ext not in self.ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail      = f"File extension '{ext}' is not allowed",
            )

        unique_id   = str(uuid.uuid4())
        safe_name   = f"{unique_id[:8]}_{original_name.replace(' ', '_')}"
        now         = datetime.now(timezone.utc)
        object_name = f"{folder}/{now.strftime('%Y/%m')}/{safe_name}"

        try:
            content = file.file.read()
            size    = len(content)
        except Exception as e:
            logger.error(f"Failed to read file content: {e}")
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail      = f"Could not read upload file: {e}",
            )

        max_bytes = max_size_mb * 1024 * 1024
        if size > max_bytes:
            raise HTTPException(
                status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail      = f"File exceeds maximum allowed size of {max_size_mb}MB",
            )

        content_type = file.content_type or "application/octet-stream"

        if self._is_configured and self.client:
            try:
                self.client.put_object(
                    Bucket      = self.bucket_name,
                    Key         = object_name,
                    Body        = content,
                    ContentType = content_type,
                )
                logger.info(f"Successfully uploaded {object_name} ({size} bytes) to Cloudflare R2")
            except Exception as e:
                logger.error(f"Cloudflare R2 upload error: {e}")
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail      = f"R2 storage service error: {e}",
                )
        else:
            # Fallback to local disk storage
            local_target = os.path.join(settings.UPLOAD_DIR, object_name)
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            with open(local_target, "wb") as f:
                f.write(content)
            logger.info(f"Saved {object_name} ({size} bytes) to local disk fallback: {local_target}")

        file_url = self._build_public_url(object_name)
        return {
            "id"          : unique_id,
            "filename"    : original_name,
            "object_name" : object_name,
            "url"         : file_url,
            "content_type": content_type,
            "size"        : size,
            "bucket"      : self.bucket_name,
            "created_at"  : now.isoformat(),
        }

    @classmethod
    def upload_file(
        cls
        , file        : UploadFile
        , folder      : str = "attachments"
        , max_size_mb : int = settings.MAX_UPLOAD_SIZE_MB
    ) -> Dict[str, Any]:
        return cls.get_instance()._upload_file(file=file, folder=folder, max_size_mb=max_size_mb)

    def _upload_bytes(
        self
        , data         : bytes
        , filename     : str
        , content_type : str = "application/octet-stream"
        , folder       : str = "attachments"
    ) -> Dict[str, Any]:
        """Upload raw bytes to Cloudflare R2 or local disk fallback."""
        folder      = folder.strip("/ ") or "attachments"
        unique_id   = str(uuid.uuid4())
        safe_name   = f"{unique_id[:8]}_{filename.replace(' ', '_')}"
        now         = datetime.now(timezone.utc)
        object_name = f"{folder}/{now.strftime('%Y/%m')}/{safe_name}"
        size        = len(data)

        if self._is_configured and self.client:
            try:
                self.client.put_object(
                    Bucket      = self.bucket_name,
                    Key         = object_name,
                    Body        = data,
                    ContentType = content_type,
                )
            except Exception as e:
                logger.error(f"Cloudflare R2 upload_bytes error: {e}")
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail      = f"Storage error: {e}",
                )
        else:
            local_target = os.path.join(settings.UPLOAD_DIR, object_name)
            os.makedirs(os.path.dirname(local_target), exist_ok=True)
            with open(local_target, "wb") as f:
                f.write(data)

        file_url = self._build_public_url(object_name)
        return {
            "id"          : unique_id,
            "filename"    : filename,
            "object_name" : object_name,
            "url"         : file_url,
            "content_type": content_type,
            "size"        : size,
            "bucket"      : self.bucket_name,
            "created_at"  : now.isoformat(),
        }

    @classmethod
    def upload_bytes(
        cls
        , data         : bytes
        , filename     : str
        , content_type : str = "application/octet-stream"
        , folder       : str = "attachments"
    ) -> Dict[str, Any]:
        return cls.get_instance()._upload_bytes(data=data, filename=filename, content_type=content_type, folder=folder)

    def _delete_file(self, object_name: str) -> bool:
        """Delete an object from Cloudflare R2 or local disk."""
        if self._is_configured and self.client:
            try:
                self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
                logger.info(f"Deleted {object_name} from Cloudflare R2")
                return True
            except Exception as e:
                logger.warning(f"R2 delete error for {object_name}: {e}")
                return False
        else:
            local_target = os.path.join(settings.UPLOAD_DIR, object_name)
            if os.path.exists(local_target):
                try:
                    os.remove(local_target)
                    return True
                except Exception as e:
                    logger.warning(f"Local file delete error for {local_target}: {e}")
            return False

    @classmethod
    def delete_file(cls, object_name: str) -> bool:
        return cls.get_instance()._delete_file(object_name)

    def _get_presigned_url(self, object_name: str, expires_hours: int = 24) -> str:
        """Generate a presigned GET URL for secure access."""
        if self._is_configured and self.client:
            try:
                return self.client.generate_presigned_url(
                    ClientMethod = "get_object",
                    Params       = {"Bucket": self.bucket_name, "Key": object_name},
                    ExpiresIn    = expires_hours * 3600,
                )
            except Exception as e:
                logger.error(f"Failed to generate presigned URL: {e}")
        return self._build_public_url(object_name)

    @classmethod
    def get_presigned_url(cls, object_name: str, expires_hours: int = 24) -> str:
        return cls.get_instance()._get_presigned_url(object_name, expires_hours)

    def _list_files(self, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """List objects in the bucket with optional prefix."""
        results: List[Dict[str, Any]] = []
        if self._is_configured and self.client:
            try:
                resp = self.client.list_objects_v2(
                    Bucket  = self.bucket_name,
                    Prefix  = prefix,
                    MaxKeys = limit,
                )
                for item in resp.get("Contents", []):
                    results.append({
                        "object_name"   : item["Key"],
                        "size"          : item["Size"],
                        "last_modified" : item["LastModified"].isoformat() if item.get("LastModified") else None,
                        "url"           : self._build_public_url(item["Key"]),
                        "etag"          : item.get("ETag", "").strip('"'),
                    })
            except Exception as e:
                logger.error(f"Failed to list objects in Cloudflare R2: {e}")
        else:
            base_dir = os.path.join(settings.UPLOAD_DIR, prefix)
            if os.path.exists(base_dir):
                for root, _, files in os.walk(base_dir):
                    for file in files:
                        if len(results) >= limit:
                            break
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, settings.UPLOAD_DIR).replace("\\", "/")
                        stat = os.stat(full_path)
                        results.append({
                            "object_name"   : rel_path,
                            "size"          : stat.st_size,
                            "last_modified" : datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                            "url"           : self._build_public_url(rel_path),
                            "etag"          : "",
                        })
        return results

    @classmethod
    def list_files(cls, prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        return cls.get_instance()._list_files(prefix=prefix, limit=limit)


# ── Aliases ───────────────────────────────────────────────────────────────────
R2_SERVICE = R2_STORAGE_SERVICE
MINIO_SERVICE = R2_STORAGE_SERVICE
