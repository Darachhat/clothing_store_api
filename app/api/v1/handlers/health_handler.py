from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.api.deps.database import get_db
from app.core.config import settings
from app.core.enum.response_enum import RESPONSE_MESSAGE_REGISTRY
from app.schemas.base_schema import RESPONSE_CODE_ITEM_SCHEMA, RESPONSE_ENVELOPE

router = APIRouter(prefix="/health", tags=["Health & Diagnostic Probes"])


@router.get("", response_model=RESPONSE_ENVELOPE[dict])
def health_check():
    """
    Liveness probe returning application component status.
    """
    return RESPONSE_ENVELOPE.success(
        data        = {
            "status"        : "UP"
            , "component"   : settings.COMPONENT_NAME
            , "environment" : settings.ENV
            , "version"     : "1.0.0"
        }
        , message   = "System application is healthy."
    )


@router.get("/ready", response_model=RESPONSE_ENVELOPE[dict])
def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness probe verifying database connection.
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "HEALTHY"
    except Exception as e:
        db_status = f"UNHEALTHY: {str(e)}"

    return RESPONSE_ENVELOPE.success(
        data        = {
            "database"  : db_status
            , "status"  : "READY" if db_status == "HEALTHY" else "NOT_READY"
        }
        , message   = "Readiness check completed."
    )


@router.get("/response-codes", response_model=RESPONSE_ENVELOPE[List[RESPONSE_CODE_ITEM_SCHEMA]])
def list_response_codes():
    """
    Return the registry of standardized application response codes, HTTP statuses, and messages.
    """
    items = [RESPONSE_CODE_ITEM_SCHEMA(**item) for item in RESPONSE_MESSAGE_REGISTRY.list_all()]
    return RESPONSE_ENVELOPE.success(
        data      = items
        , message = "Response code registry retrieved successfully."
    )

