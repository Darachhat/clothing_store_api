"""Sales API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.product import ProductVariant
from app.models.sale import Return, Sale, SaleItem
from app.models.user import User
from app.schemas.sale import ReturnCreate, ReturnOut, SaleComplete, SaleCreate, SaleOut
from app.services.sale_service import SaleService

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
    )


@router.get("/", response_model=list[SaleOut])
async def list_sales(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.read")),
) -> list[Sale]:
    result = await db.execute(
        select(Sale)
        .options(*_sale_eager_options())
        .offset(skip)
        .limit(limit)
        .order_by(Sale.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(
    body: SaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.create")),
) -> Sale:
    service = SaleService(db)
    items_data = [
        {
            "variant_id": item.variant_id,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "discount_amount": item.discount_amount,
        }
        for item in body.items
    ]
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
    )
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


@router.get("/{id}", response_model=SaleOut)
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


@router.post("/{id}/complete", response_model=SaleOut)
async def complete_sale(
    id: UUID,
    body: SaleComplete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sale.create")),
) -> Sale:
    result = await db.execute(
        select(Sale)
        .where(Sale.id == id)
        .options(selectinload(Sale.items))
    )
    sale = result.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    service = SaleService(db)
    sale = await service.complete_sale(
        sale,
        [p.model_dump() for p in body.payments],
    )
    from app.services.product_service import ProductService
    await ProductService.increment_inventory_version(db)
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


@router.post("/{id}/cancel", response_model=SaleOut)
@router.post("/{id}/void", response_model=SaleOut, include_in_schema=False)
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

    service = SaleService(db)
    sale = await service.cancel_sale(sale, current_user.id)
    from app.services.product_service import ProductService
    await ProductService.increment_inventory_version(db)
    await db.commit()
    res = await db.execute(
        select(Sale)
        .where(Sale.id == sale.id)
        .options(*_sale_eager_options())
    )
    return res.scalar_one()


# ─── Returns ──────────────────────────────────────────────────────────────────
returns_router = APIRouter(prefix="/returns", tags=["Returns"])


@returns_router.get("/", response_model=list[ReturnOut])
async def list_returns(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sale.refund")),
) -> list[Return]:
    result = await db.execute(
        select(Return).offset(skip).limit(limit).order_by(Return.created_at.desc())
    )
    return list(result.scalars().all())


@returns_router.post("/", response_model=ReturnOut, status_code=status.HTTP_201_CREATED)
async def create_return(
    body: ReturnCreate,
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

    service = SaleService(db)
    ret = await service.process_return(
        original_sale=sale,
        return_items_data=[i.model_dump() for i in body.items],
        refund_payments=[p.model_dump() for p in body.refund_payments],
        return_type=body.return_type,
        reason=body.reason,
        processed_by=current_user.id,
    )
    await db.commit()
    await db.refresh(ret)
    return ret
