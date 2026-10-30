"""Customer & Loyalty API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.customer import (
    AdjustPointsRequest,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    LoyaltyAccountSchema,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers & Loyalty"])


@router.get("/", response_model=CustomerListResponse)
async def list_customers(
    q: str | None = Query(None, description="Search query"),
    status: str | None = Query(None, description="Customer status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.read")),
) -> CustomerListResponse:
    service = CustomerService(db)
    items, total = await service.repo.search(q=q, status=status, skip=skip, limit=limit)
    return CustomerListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=[CustomerResponse.model_validate(item) for item in items],
    )


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.create")),
) -> CustomerResponse:
    service = CustomerService(db)
    customer = await service.create_customer(data)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.read")),
) -> CustomerResponse:
    service = CustomerService(db)
    customer = await service.get_customer(customer_id)
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=CustomerResponse)
@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.update")),
) -> CustomerResponse:
    service = CustomerService(db)
    customer = await service.update_customer(customer_id, data)
    return CustomerResponse.model_validate(customer)


@router.post("/{customer_id}/points", response_model=LoyaltyAccountSchema)
async def adjust_loyalty_points(
    customer_id: UUID,
    payload: AdjustPointsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("customer.update")),
) -> LoyaltyAccountSchema:
    service = CustomerService(db)
    account = await service.adjust_loyalty_points(
        customer_id=customer_id,
        points=payload.points,
        note=payload.note,
    )
    return LoyaltyAccountSchema.model_validate(account)
