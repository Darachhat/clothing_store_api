"""API Endpoints for attachment uploads and file storage."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.models import User
from app.services.minio_service import MINIO_SERVICE


router = APIRouter(prefix="/attachments", tags=["Attachments & Files"])
uploads_router = APIRouter(prefix="/uploads", tags=["Attachments & Files"])


class AttachmentResponse(BaseModel):
    id: str
    filename: str
    object_name: str
    url: str
    content_type: str
    size: int
    bucket: str
    created_at: str


class AttachmentListResponse(BaseModel):
    items: List[dict]
    total: int


@router.post(
    "/upload",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a single attachment",
)
@uploads_router.post(
    "/images",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image attachment",
)
async def upload_attachment(
    file: UploadFile = File(..., description="File to upload"),
    folder: str = Form("attachments", description="Folder/category (e.g. products, expenses, receipts, avatars)"),
    _: User = Depends(get_current_active_user),
):
    """Upload any file attachment (images, receipts, invoices, PDFs)."""
    try:
        result = MINIO_SERVICE.upload_file(file=file, folder=folder)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )


@router.post(
    "/upload-multiple",
    response_model=List[AttachmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple attachments",
)
async def upload_multiple_attachments(
    files: List[UploadFile] = File(..., description="Files to upload"),
    folder: str = Form("attachments", description="Folder/category"),
    _: User = Depends(get_current_active_user),
):
    """Upload multiple file attachments."""
    results = []
    for file in files:
        try:
            res = MINIO_SERVICE.upload_file(file=file, folder=folder)
            results.append(res)
        except Exception as e:
            logger.error(f"Error uploading {file.filename}: {e}")
    return results


@router.get(
    "",
    response_model=AttachmentListResponse,
    summary="List stored attachments",
)
async def list_attachments(
    folder: str = Query("", description="Filter by folder prefix (e.g. products, expenses)"),
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_active_user),
):
    """List stored attachments."""
    items = MINIO_SERVICE.list_files(prefix=folder, limit=limit)
    return {"items": items, "total": len(items)}


@router.get(
    "/{object_name:path}",
    summary="Get direct link to attachment",
)
async def get_attachment_link(object_name: str):
    """Redirect to the public URL of an attachment."""
    url = f"{settings.MINIO_PUBLIC_URL}/{settings.MINIO_BUCKET_NAME}/{object_name}"
    return RedirectResponse(url=url)


@router.delete(
    "/{object_name:path}",
    status_code=status.HTTP_200_OK,
    summary="Delete an attachment",
)
async def delete_attachment(
    object_name: str,
    _: User = Depends(get_current_active_user),
):
    """Delete an attachment."""
    success = MINIO_SERVICE.delete_file(object_name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File could not be deleted or not found",
        )
    return {"status": "success", "message": f"Deleted {object_name}"}
