"""Translation API & CMS Management Endpoints.

Serves cached multi-lingual UI text directly from Redis / TRANSLATE_MODEL,
and provides full CMS CRUD operations for managing content keys.
"""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.translation_cache import TRANSLATION_CACHE
from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models.base_data_schema_model import TRANSLATE_MODEL
from app.models import User
from app.schemas.translation_schema import (
    TRANSLATION_ITEM_CREATE_SCHEMA,
    TRANSLATION_ITEM_RESPONSE_SCHEMA,
    TRANSLATION_ITEM_UPDATE_SCHEMA,
    TRANSLATION_PAGINATED_RESPONSE_SCHEMA,
    TRANSLATION_PURGE_RESPONSE_SCHEMA,
)

router = APIRouter(prefix="/translations", tags=["Translations CMS"])


# ─── Fast Public Cache Serving ───────────────────────────────────────────────

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


# ─── CMS Content Management Endpoints ────────────────────────────────────────

@router.get("/items", response_model=TRANSLATION_PAGINATED_RESPONSE_SCHEMA)
async def list_translation_items(
    q: Optional[str] = Query(None, description="Search keyword across keys and translated strings"),
    schema_name: Optional[str] = Query(None, description="Filter by schema name"),
    table_name: Optional[str] = Query(None, description="Filter by table/section name"),
    status_code: Optional[str] = Query(None, description="Filter by status (ACTIVE/INACTIVE)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Dict[str, Any]:
    """Paginated CMS search & list of all translation keys in base_data.translate."""
    base_where = [TRANSLATE_MODEL.deleted_datetime.is_(None)]

    if schema_name:
        base_where.append(TRANSLATE_MODEL.schema_name == schema_name)
    if table_name:
        base_where.append(TRANSLATE_MODEL.table_name == table_name)
    if status_code:
        base_where.append(TRANSLATE_MODEL.status_code == status_code)

    if q and q.strip():
        term = f"%{q.strip()}%"
        base_where.append(
            or_(
                TRANSLATE_MODEL.column_name.ilike(term),
                TRANSLATE_MODEL.table_name.ilike(term),
                TRANSLATE_MODEL.en.ilike(term),
                TRANSLATE_MODEL.km.ilike(term),
                TRANSLATE_MODEL.cn.ilike(term),
                TRANSLATE_MODEL.jp.ilike(term),
                TRANSLATE_MODEL.kr.ilike(term),
                TRANSLATE_MODEL.note.ilike(term),
            )
        )

    # Count total
    count_stmt = select(func.count(TRANSLATE_MODEL.id)).where(*base_where)
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Query page
    stmt = (
        select(TRANSLATE_MODEL)
        .where(*base_where)
        .order_by(TRANSLATE_MODEL.schema_name.asc(), TRANSLATE_MODEL.table_name.asc(), TRANSLATE_MODEL.column_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    total_pages = max(1, math.ceil(total_count / page_size))

    return {
        "items": records,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("/items", response_model=TRANSLATION_ITEM_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_translation_item(
    payload: TRANSLATION_ITEM_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> TRANSLATE_MODEL:
    """Create a new translation entry in base_data.translate and invalidate cache."""
    # Check if duplicate (schema_name, table_name, column_name)
    stmt = select(TRANSLATE_MODEL).where(
        TRANSLATE_MODEL.schema_name == payload.schema_name,
        TRANSLATE_MODEL.table_name == payload.table_name,
        TRANSLATE_MODEL.column_name == payload.column_name,
        TRANSLATE_MODEL.deleted_datetime.is_(None),
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Translation key '{payload.table_name}.{payload.column_name}' already exists in schema '{payload.schema_name}'.",
        )

    new_id = uuid.uuid4()
    record = TRANSLATE_MODEL(
        id=new_id,
        ref_id=payload.ref_id or uuid.uuid4(),
        schema_name=payload.schema_name,
        table_name=payload.table_name,
        column_name=payload.column_name,
        en=payload.en,
        km=payload.km,
        cn=payload.cn,
        jp=payload.jp,
        kr=payload.kr,
        note=payload.note,
        status_code=payload.status_code or "ACTIVE",
        created_by=str(current_user.id) if getattr(current_user, "id", None) else "admin",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Invalidate cache so frontend immediately picks up new content
    await TRANSLATION_CACHE.invalidate_cache()
    return record


@router.get("/items/{item_id}", response_model=TRANSLATION_ITEM_RESPONSE_SCHEMA)
async def get_translation_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> TRANSLATE_MODEL:
    """Retrieve details of a single translation key."""
    stmt = select(TRANSLATE_MODEL).where(
        TRANSLATE_MODEL.id == item_id,
        TRANSLATE_MODEL.deleted_datetime.is_(None),
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation key not found")
    return item


@router.put("/items/{item_id}", response_model=TRANSLATION_ITEM_RESPONSE_SCHEMA)
async def update_translation_item(
    item_id: uuid.UUID,
    payload: TRANSLATION_ITEM_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> TRANSLATE_MODEL:
    """Update localized strings or metadata for a translation key and flush cache."""
    stmt = select(TRANSLATE_MODEL).where(
        TRANSLATE_MODEL.id == item_id,
        TRANSLATE_MODEL.deleted_datetime.is_(None),
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation key not found")

    if payload.schema_name is not None:
        item.schema_name = payload.schema_name
    if payload.table_name is not None:
        item.table_name = payload.table_name
    if payload.column_name is not None:
        item.column_name = payload.column_name
    if payload.en is not None:
        item.en = payload.en
    if payload.km is not None:
        item.km = payload.km
    if payload.cn is not None:
        item.cn = payload.cn
    if payload.jp is not None:
        item.jp = payload.jp
    if payload.kr is not None:
        item.kr = payload.kr
    if payload.note is not None:
        item.note = payload.note
    if payload.status_code is not None:
        item.status_code = payload.status_code

    item.updated_by = str(current_user.id) if getattr(current_user, "id", None) else "admin"

    await db.commit()
    await db.refresh(item)

    # Invalidate cache so frontend displays the updated translations immediately
    await TRANSLATION_CACHE.invalidate_cache()
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_translation_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings.manage")),
) -> Response:
    """Soft-delete a translation key and invalidate cache."""
    stmt = select(TRANSLATE_MODEL).where(
        TRANSLATE_MODEL.id == item_id,
        TRANSLATE_MODEL.deleted_datetime.is_(None),
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Translation key not found")

    item.status_code = "INACTIVE"
    item.deleted_by = str(current_user.id) if getattr(current_user, "id", None) else "admin"
    item.deleted_datetime = func.now()

    await db.commit()
    await TRANSLATION_CACHE.invalidate_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cache/purge", response_model=TRANSLATION_PURGE_RESPONSE_SCHEMA)
async def purge_translation_cache(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Dict[str, str]:
    """Force flush Redis translation cache and warm up baseline keys."""
    await TRANSLATION_CACHE.invalidate_cache()
    # Warm up cache
    await TRANSLATION_CACHE.get_translations(db=db, schema_name="admin_front")
    return {"status": "success", "message": "Translation Redis cache purged and warmed successfully."}


@router.post("/seed", status_code=status.HTTP_200_OK)
async def reseed_translations(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("settings.manage")),
) -> Dict[str, Any]:
    """Re-seed standard translation keys into base_data.translate and warm cache."""
    count = await TRANSLATION_CACHE.seed_translations(db=db)
    return {"status": "success", "seeded_count": count}
