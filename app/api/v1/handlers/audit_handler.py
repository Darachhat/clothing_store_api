"""Audit logs API endpoint (/audit-logs)."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.services.audit_service import AuditLogOut, AuditService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogOut])
@router.get("/", response_model=list[AuditLogOut], include_in_schema=False)
async def list_audit_logs(
    action: str | None = Query(None),
    entity_type: str | None = Query(None),
    user_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> list[AuditLogOut]:
    logs = await AuditService.list_logs(
        db=db,
        action=action,
        entity_type=entity_type,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    return [AuditLogOut.model_validate(item) for item in logs]

