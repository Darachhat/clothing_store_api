"""Sales API endpoints."""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import ProductVariant
from app.models import Return, Sale, SaleItem
from app.models import User
from app.schemas.sale_schema import (
    RETURN_CREATE_SCHEMA,
    RETURN_CREATE_FOR_SALE_SCHEMA,
    RETURN_RESPONSE_SCHEMA,
    SALE_COMPLETE_SCHEMA,
    SALE_CREATE_SCHEMA,
    SALE_RESPONSE_SCHEMA,
)
from app.services.sale_service import SALE_SERVICE

router = APIRouter(prefix="/sales", tags=["Sales"])


def _sale_eager_options():
    return (
        selectinload(Sale.items)
        .selectinload(SaleItem.variant)
        .options(
            selectinload(ProductVariant.product),
            selectinload(ProductVariant.color),
            selectinload(ProductVariant.size),
        ),
        selectinload(Sale.payments),
        selectinload(Sale.customer),
        selectinload(Sale.branch),
        selectinload(Sale.cashier),
        selectinload(Sale.terminal),
    )


@router.get("", response_model=list[SALE_RESPONSE_SCHEMA], include_in_schema=False)
@router.get("/", response_model=list[SALE_RESPONSE_SCHEMA])
async def list_sales(
    skip: int = 0,
    limit: int = 50,
    q: str | None = None,
    search: str | None = None,
    sale_status: str | None = Query(None, alias="status"),
    payment_status: str | None = None,
    cashier_id: UUID | None = None,
    terminal_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.read")),
) -> list[Sale]:
    stmt = select(Sale).options(*_sale_eager_options())
    keyword = (q or search or "").strip()
    if keyword:
        stmt = stmt.where(Sale.invoice_number.ilike(f"%{keyword}%"))
    if sale_status:
        stmt = stmt.where(Sale.sale_status == sale_status.upper())
    if payment_status:
        stmt = stmt.where(Sale.payment_status == payment_status.upper())
    if cashier_id:
        stmt = stmt.where(Sale.cashier_id == cashier_id)
    if terminal_id:
        stmt = stmt.where(Sale.terminal_id == terminal_id)
    if from_date:
        start_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=UTC)
        stmt = stmt.where(Sale.created_at >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=UTC)
        stmt = stmt.where(Sale.created_at <= end_dt)

    result = await db.execute(
        stmt.offset(skip).limit(limit).order_by(Sale.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=SALE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=SALE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SALE_CREATE_SCHEMA,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.create")),
) -> Sale:
    service = SALE_SERVICE(db)
    items_data = [
        {
            "variant_id": item.variant_id,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_amount": item.discount_amount,
        }
        for item in body.items
    ]
    payments_data = [p.model_dump() for p in body.payments] if body.payments else None
    sale = await service.create_sale(
        branch_id=body.branch_id,
        warehouse_id=body.warehouse_id,
        cashier_id=current_user.id,
        items_data=items_data,
        customer_id=body.customer_id,
        discount_amount=body.discount_amount,
        tax_amount=body.tax_amount,
        notes=body.notes,
        promotion_id=body.promotion_id,
        terminal_id=body.terminal_id,
        shift_id=body.shift_id,
        payments=payments_data,
        background_tasks=background_tasks,
    )
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


@router.get("/returns", response_model=list[RETURN_RESPONSE_SCHEMA])
async def list_sales_returns_alias(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sale.refund")),
) -> list[Return]:
    result = await db.execute(
        select(Return).offset(skip).limit(limit).order_by(Return.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{id}", response_model=SALE_RESPONSE_SCHEMA)
async def get_sale(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sale.read")),
) -> Sale:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(*_sale_eager_options())
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return sale


@router.get("/{id}/receipt", response_model=SALE_RESPONSE_SCHEMA)
async def get_sale_receipt(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sale.read")),
) -> Sale:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(*_sale_eager_options())
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return sale


@router.post("/{id}/return", response_model=RETURN_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_sale_return(
    id: UUID,
    body: RETURN_CREATE_FOR_SALE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.refund")),
) -> Return:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(selectinload(Sale.items))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original sale not found")

    service = SALE_SERVICE(db)
    ret = await service.process_return(
        original_sale=sale,
        return_items_data=[i.model_dump() for i in body.items],
        refund_payments=[p.model_dump() for p in body.refund_payments],
        return_type=body.return_type,
        reason=body.reason,
        processed_by=current_user.id,
    )
    from app.services.product_service import PRODUCT_SERVICE

    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    await db.refresh(ret)
    return ret


@router.post("/{id}/complete", response_model=SALE_RESPONSE_SCHEMA)
async def complete_sale(
    id: UUID,
    body: SALE_COMPLETE_SCHEMA,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.create")),
) -> Sale:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(selectinload(Sale.items).selectinload(SaleItem.variant))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    service = SALE_SERVICE(db)
    sale = await service.complete_sale(
        sale,
        [p.model_dump() for p in body.payments],
        background_tasks=background_tasks,
    )
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


@router.post("/{id}/cancel", response_model=SALE_RESPONSE_SCHEMA)
@router.post("/{id}/void", response_model=SALE_RESPONSE_SCHEMA, include_in_schema=False)
async def cancel_sale(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.create")),
) -> Sale:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(*_sale_eager_options())
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    service = SALE_SERVICE(db)
    sale = await service.cancel_sale(sale, current_user.id)
    from app.services.product_service import PRODUCT_SERVICE
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


# ─── Returns ──────────────────────────────────────────────────────────────────
returns_router = APIRouter(prefix="/returns", tags=["Returns"])


@returns_router.get("", response_model=list[RETURN_RESPONSE_SCHEMA], include_in_schema=False)
@returns_router.get("/", response_model=list[RETURN_RESPONSE_SCHEMA])
async def list_returns(
    skip: int = 0,
    limit: int = 50,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sale.refund")),
) -> list[Return]:
    stmt = select(Return)
    if from_date:
        start_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=UTC)
        stmt = stmt.where(Return.created_at >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=UTC)
        stmt = stmt.where(Return.created_at <= end_dt)
    result = await db.execute(
        stmt.offset(skip).limit(limit).order_by(Return.created_at.desc())
    )
    return list(result.scalars().all())


@returns_router.post("", response_model=RETURN_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@returns_router.post("/", response_model=RETURN_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_return(
    body: RETURN_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.refund")),
) -> Return:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == body.original_sale_id)
        .options(selectinload(Sale.items))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original sale not found")

    service = SALE_SERVICE(db)
    ret = await service.process_return(
        original_sale=sale,
        return_items_data=[i.model_dump() for i in body.items],
        refund_payments=[p.model_dump() for p in body.refund_payments],
        return_type=body.return_type,
        reason=body.reason,
        processed_by=current_user.id,
    )
    from app.services.product_service import PRODUCT_SERVICE

    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    await db.refresh(ret)
    return ret
