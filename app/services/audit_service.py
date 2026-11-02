"""Append-only domain audit logging service (data.audit_logs)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import AuditLog
from app.schemas.audit_schema import (
    AUDIT_LOG_CREATE_REQUEST_SCHEMA
    , AUDIT_LOG_LIST_OUT_SCHEMA
    , AUDIT_LOG_RESPONSE_SCHEMA
)

logger = get_logger(__name__)

# Backward-compatible schema alias
AUDIT_LOG_OUT_SCHEMA = AUDIT_LOG_RESPONSE_SCHEMA


class AUDIT_SERVICE:
    """Service for recording and querying append-only domain audit logs."""

    @staticmethod
    async def record(
        db            : AsyncSession
        , action      : str
        , entity_type : Optional[str]            = None
        , entity_id   : Optional[UUID]           = None
        , user_id     : Optional[UUID]           = None
        , old_data    : Optional[Dict[str, Any]] = None
        , new_data    : Optional[Dict[str, Any]] = None
        , ip_address  : Optional[str]            = None
        , user_agent  : Optional[str]            = None
    ) -> AuditLog:
        entry = AuditLog(
            user_id       = user_id
            , action      = action
            , entity_type = entity_type
            , entity_id   = entity_id
            , old_data    = old_data
            , new_data    = new_data
            , ip_address  = ip_address
            , user_agent  = user_agent
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def record_payload(
        db        : AsyncSession
        , payload : AUDIT_LOG_CREATE_REQUEST_SCHEMA
    ) -> AuditLog:
        """Create audit log record using structured REQUEST_PAYLOAD_SCHEMA."""
        return await AUDIT_SERVICE.record(
            db            = db
            , action      = payload.action
            , entity_type = payload.entity_type
            , entity_id   = payload.entity_id
            , user_id     = payload.user_id
            , old_data    = payload.old_data
            , new_data    = payload.new_data
            , ip_address  = payload.ip_address
            , user_agent  = payload.user_agent
        )

    @staticmethod
    async def list_logs(
        db            : AsyncSession
        , action      : Optional[str]  = None
        , entity_type : Optional[str]  = None
        , user_id     : Optional[UUID] = None
        , skip        : int            = 0
        , limit       : int            = 100
    ) -> List[AuditLog]:
        stmt = select(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        res  = await db.execute(stmt)
        return list(res.scalars().all())



AuditService = AUDIT_SERVICE
AuditLogOut  = AUDIT_LOG_OUT_SCHEMA