"""Promotions and Coupons API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_active_user, require_permission
from app.models import Promotion
from app.models import User
from app.repositories.misc_repository import PromotionRepository
from app.schemas.promotion_schema import (
    COUPON_VALIDATION_REQUEST_SCHEMA,
    COUPON_VALIDATION_RESPONSE_SCHEMA,
    PROMOTION_CREATE_SCHEMA,
    PROMOTION_RESPONSE_SCHEMA,
    PROMOTION_UPDATE_SCHEMA,
)
from app.services.misc_service import PROMOTION_SERVICE

router = APIRouter(prefix="/promotions", tags=["Promotions & Discounts"])


@router.get("", response_model=list[PROMOTION_RESPONSE_SCHEMA])
async def list_promotions(
    active_only: bool = False,
    promo_status: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> list[Promotion]:
    repo = PromotionRepository(db)
    items = await repo.list_promotions(
        skip=skip,
        limit=limit,
        status=promo_status,
        active_only=active_only,
    )
    return list(items)


@router.post("", response_model=PROMOTION_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    payload: PROMOTION_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.create")),
) -> Promotion:
    repo = PromotionRepository(db)
    if payload.code:
        existing = await repo.get_by_code(payload.code.upper().strip())
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Coupon code already exists")

    promo_data = payload.model_dump()
    if promo_data.get("code"):
        promo_data["code"] = promo_data["code"].upper().strip()

    promo = await repo.create(**promo_data)
    await db.commit()
    return promo


@router.get("/{promo_id}", response_model=PROMOTION_RESPONSE_SCHEMA)
async def get_promotion(
    promo_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> Promotion:
    repo = PromotionRepository(db)
    promo = await repo.get_by_id(promo_id)
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")
    return promo


@router.patch("/{promo_id}", response_model=PROMOTION_RESPONSE_SCHEMA)
@router.put("/{promo_id}", response_model=PROMOTION_RESPONSE_SCHEMA)
async def update_promotion(
    promo_id: UUID,
    payload: PROMOTION_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.update")),
) -> Promotion:
    repo = PromotionRepository(db)
    promo = await repo.get_by_id(promo_id)
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "code" in update_data and update_data["code"]:
        update_data["code"] = update_data["code"].upper().strip()

    promo = await repo.update(promo, **update_data)
    await db.commit()
    return promo


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_promotion(
    promo_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("product.delete")),
) -> Response:
    repo = PromotionRepository(db)
    promo = await repo.get_by_id(promo_id)
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promotion not found")

    await repo.delete(promo)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/validate", response_model=COUPON_VALIDATION_RESPONSE_SCHEMA)
@router.post("/validate-coupon", response_model=COUPON_VALIDATION_RESPONSE_SCHEMA, include_in_schema=False)
async def validate_coupon(
    payload: COUPON_VALIDATION_REQUEST_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
) -> COUPON_VALIDATION_RESPONSE_SCHEMA:
    service = PROMOTION_SERVICE(db)
    return await service.validate_coupon(code=payload.code, cart_total=payload.cart_total)
