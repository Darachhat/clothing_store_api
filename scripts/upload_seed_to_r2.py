"""Upload local seed images and attachments to Cloudflare R2 bucket.

Usage:
    python scripts/upload_seed_to_r2.py
"""
import mimetypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.r2_service import R2_SERVICE


def main() -> None:
    print("=" * 60)
    print(" Cloudflare R2 Seed Assets Migration")
    print("=" * 60)
    print(f"Account ID   : {settings.R2_ACCOUNT_ID}")
    print(f"Endpoint URL : {settings.R2_ENDPOINT_URL}")
    print(f"Bucket Name  : {settings.R2_BUCKET_NAME}")
    print(f"Configured   : {R2_SERVICE.is_configured()}")

    if not R2_SERVICE.is_configured():
        print("\n[ERROR] R2 credentials not configured!")
        print("Please set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY in backend/.env")
        print("You can generate these in Cloudflare Dashboard -> R2 -> Manage R2 API Tokens.")
        sys.exit(1)

    print("\nEnsuring bucket exists in Cloudflare R2...")
    R2_SERVICE.ensure_bucket_exists()

    uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    if not os.path.exists(uploads_dir):
        print(f"[ERROR] Uploads directory not found: {uploads_dir}")
        sys.exit(1)

    client = R2_SERVICE.get_client()
    if not client:
        print("[ERROR] R2 client could not be initialized. Please verify credentials.")
        sys.exit(1)
    uploaded_count = 0

    for root, _, files in os.walk(uploads_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, uploads_dir).replace("\\", "/")
            # object_name in bucket: "uploads/products/xyz.jpg" or "products/xyz.jpg"
            # We support "uploads/{rel_path}" and "{rel_path}"
            object_name = f"uploads/{rel_path}"

            mime_type, _ = mimetypes.guess_type(full_path)
            content_type = mime_type or "application/octet-stream"

            size = os.path.getsize(full_path)
            print(f"Uploading {rel_path} ({size} bytes, {content_type}) -> R2 '{object_name}'...")

            try:
                with open(full_path, "rb") as f:
                    client.put_object(
                        Bucket      = settings.R2_BUCKET_NAME,
                        Key         = object_name,
                        Body        = f.read(),
                        ContentType = content_type,
                    )
                # Also upload without "uploads/" prefix for convenience
                with open(full_path, "rb") as f:
                    client.put_object(
                        Bucket      = settings.R2_BUCKET_NAME,
                        Key         = rel_path,
                        Body        = f.read(),
                        ContentType = content_type,
                    )
                uploaded_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to upload {rel_path}: {e}")

    print("=" * 60)
    print(f" Migration finished. Successfully uploaded {uploaded_count} files to R2!")
    print("=" * 60)


if __name__ == "__main__":
    main()
