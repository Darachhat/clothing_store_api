"""Translation API Endpoints.

Serves cached multi-lingual UI text directly from Redis / TRANSLATE_MODEL.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.translation_cache import TRANSLATION_CACHE
from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User

router = APIRouter(prefix="/translations", tags=["Translations"])


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any], include_in_schema=False)
async def get_translations(
    lang: Optional[str] = Query(None, description="Language code: en, km, cn, jp, kr"),
    schema_name: Optional[str] = Query("admin_front", description="UI schema name (e.g. admin_front, pos, web)"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve UI translations served directly from Redis cache."""
    return await TRANSLATION_CACHE.get_translations(
        db=db,
        lang=lang,
        schema_name=schema_name,
    )


@router.post("/seed", status_code=status.HTTP_200_OK)
async def reseed_translations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Dict[str, Any]:
    """Re-seed standard translation keys into base_data.translate and warm cache."""
    count = await TRANSLATION_CACHE.seed_translations(db=db)
    return {"status": "success", "seeded_count": count}

