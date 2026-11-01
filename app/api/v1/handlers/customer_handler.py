"""Customer & Loyalty API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import User
from app.schemas.customer_schema import (
    ADJUST_POINTS_REQUEST_SCHEMA,
    CUSTOMER_CREATE_SCHEMA,
    CUSTOMER_LIST_OUT_SCHEMA,
    CUSTOMER_RESPONSE_SCHEMA,
    CUSTOMER_UPDATE_SCHEMA,
    LOYALTY_ACCOUNT_RESPONSE_SCHEMA,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers & Loyalty"])


@router.get("/", response_model=CUSTOMER_LIST_OUT_SCHEMA)
async def list_customers(
    q: str | None = Query(None, description="Search query"),
    status: str | None = Query(None, description="Customer status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.read")),
) -> CUSTOMER_LIST_OUT_SCHEMA:
    service = CustomerService(db)
    items, total = await service.repo.search(q=q, status=status, skip=skip, limit=limit)
    return CUSTOMER_LIST_OUT_SCHEMA(
        total=total,
        skip=skip,
        limit=limit,
        items=[CUSTOMER_RESPONSE_SCHEMA.model_validate(item) for item in items],
    )


@router.post("/", response_model=CUSTOMER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CUSTOMER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.create")),
) -> CUSTOMER_RESPONSE_SCHEMA:
    service = CustomerService(db)
    customer = await service.create_customer(data)
    return CUSTOMER_RESPONSE_SCHEMA.model_validate(customer)


@router.get("/{customer_id}", response_model=CUSTOMER_RESPONSE_SCHEMA)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.read")),
) -> CUSTOMER_RESPONSE_SCHEMA:
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)
    return CUSTOMER_RESPONSE_SCHEMA.model_validate(customer)


@router.put("/{customer_id}", response_model=CUSTOMER_RESPONSE_SCHEMA)
@router.patch("/{customer_id}", response_model=CUSTOMER_RESPONSE_SCHEMA)
async def update_customer(
    customer_id: UUID,
    data: CUSTOMER_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.update")),
) -> CUSTOMER_RESPONSE_SCHEMA:
    service = CustomerService(db)
    customer = await service.update_customer(customer_id, data)
    return CUSTOMER_RESPONSE_SCHEMA.model_validate(customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.update")),
) -> Response:
    service = CustomerService(db)
    customer = await service.repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    customer.status = "INACTIVE"
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{customer_id}/loyalty", response_model=LOYALTY_ACCOUNT_RESPONSE_SCHEMA)
async def get_customer_loyalty(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.read")),
) -> LOYALTY_ACCOUNT_RESPONSE_SCHEMA:
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)
    if not customer.loyalty_account:
        from app.models import LoyaltyAccount

        account = LoyaltyAccount(customer_id=customer.id, points_balance=0, total_points_earned=0, total_points_redeemed=0, tier="BRONZE")
        db.add(account)
        await db.commit()
        await db.refresh(account)
        customer = await service.get_customer(customer_id)
    return LOYALTY_ACCOUNT_RESPONSE_SCHEMA.model_validate(customer.loyalty_account)


@router.post("/{customer_id}/points", response_model=LOYALTY_ACCOUNT_RESPONSE_SCHEMA)
@router.post("/{customer_id}/loyalty/adjust", response_model=LOYALTY_ACCOUNT_RESPONSE_SCHEMA)
async def adjust_loyalty_points(
    customer_id: UUID,
    payload: ADJUST_POINTS_REQUEST_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.update")),
) -> LOYALTY_ACCOUNT_RESPONSE_SCHEMA:
    service = CustomerService(db)
    account = await service.adjust_loyalty_points(
        customer_id=customer_id,
        points=payload.points,
        note=payload.note,
    )
    customer = await service.get_customer(customer_id)
    return LOYALTY_ACCOUNT_RESPONSE_SCHEMA.model_validate(customer.loyalty_account or account)
