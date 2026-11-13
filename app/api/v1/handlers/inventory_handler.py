"""Inventory API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import InventoryMovement, InventoryStock, StockTransfer
from app.models import User
from app.schemas.inventory_schema import (
    INVENTORY_MOVEMENT_RESPONSE_SCHEMA,
    INVENTORY_STOCK_RESPONSE_SCHEMA,
    REORDER_LEVEL_UPDATE_SCHEMA,
    STOCK_ADJUSTMENT_CREATE_SCHEMA,
    STOCK_TRANSFER_CREATE_SCHEMA,
    STOCK_TRANSFER_RESPONSE_SCHEMA,
)
from app.services.inventory_service import INVENTORY_SERVICE

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=list[INVENTORY_STOCK_RESPONSE_SCHEMA], include_in_schema=False)
@router.get("/", response_model=list[INVENTORY_STOCK_RESPONSE_SCHEMA])
@router.get("/stocks", response_model=list[INVENTORY_STOCK_RESPONSE_SCHEMA])
async def list_stocks(
    response: Response,
    warehouse_id: UUID | None = None,
    variant_id: UUID | None = None,
    product_id: UUID | None = None,
    q: str | None = Query(None, description="Match SKU, barcode or product name/code"),
    stock_status: str | None = Query(None, description="LOW | OUT | IN"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
) -> list[InventoryStock]:
    """List stock rows (one per variant/warehouse). Total matches are returned in ``X-Total-Count``."""
    from sqlalchemy import func, or_
    from sqlalchemy.orm import selectinload
    from app.models import Product, ProductVariant

    conditions = []
    if warehouse_id:
        conditions.append(InventoryStock.warehouse_id == warehouse_id)
    if variant_id:
        conditions.append(InventoryStock.variant_id == variant_id)

    needs_variant_join = bool(product_id or (q and q.strip()))
    if needs_variant_join and product_id:
        conditions.append(ProductVariant.product_id == product_id)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                ProductVariant.sku.ilike(like),
                ProductVariant.barcode.ilike(like),
                Product.name.ilike(like),
                Product.code.ilike(like),
            )
        )

    flag = (stock_status or "").upper()
    if flag == "OUT":
        conditions.append(InventoryStock.quantity <= 0)
    elif flag == "LOW":
        conditions.append(InventoryStock.quantity > 0)
        conditions.append(InventoryStock.quantity <= func.greatest(InventoryStock.reorder_level, 0))
    elif flag == "IN":
        conditions.append(InventoryStock.quantity > InventoryStock.reorder_level)

    base = select(InventoryStock)
    count_stmt = select(func.count(InventoryStock.id))
    if needs_variant_join:
        base = base.join(ProductVariant, ProductVariant.id == InventoryStock.variant_id).join(
            Product, Product.id == ProductVariant.product_id
        )
        count_stmt = count_stmt.join(ProductVariant, ProductVariant.id == InventoryStock.variant_id).join(
            Product, Product.id == ProductVariant.product_id
        )
    for cond in conditions:
        base = base.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    response.headers["X-Total-Count"] = str(total)

    stmt = (
        base.options(
            selectinload(InventoryStock.variant).options(
                selectinload(ProductVariant.product),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            ),
            selectinload(InventoryStock.warehouse),
        )
        .order_by(InventoryStock.created_at.desc(), InventoryStock.id)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.put("/stocks/reorder-level", response_model=INVENTORY_STOCK_RESPONSE_SCHEMA)
async def set_reorder_level(
    body: REORDER_LEVEL_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.adjust")),
) -> InventoryStock:
    """Set the low-stock threshold for one variant in one warehouse (creates the row at 0 if absent)."""
    service = INVENTORY_SERVICE(db)
    stock = await service.stock_repo.get_or_create_stock(body.variant_id, body.warehouse_id, lock=True)
    old_level = stock.reorder_level
    stock.reorder_level = body.reorder_level
    from app.services.audit_service import AUDIT_SERVICE
    await AUDIT_SERVICE.record(
        db,
        action="INVENTORY_REORDER_LEVEL",
        entity_type="inventory_stock",
        entity_id=stock.id,
        user_id=current_user.id,
        old_data={"reorder_level": old_level},
        new_data={"reorder_level": body.reorder_level},
    )
    await db.commit()
    await db.refresh(stock)
    return stock


@router.get("/low-stock", response_model=list[INVENTORY_STOCK_RESPONSE_SCHEMA])
async def list_low_stock(
    warehouse_id: UUID | None = None,
    skip: int = 0,
    limit: int = 500,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
) -> list[InventoryStock]:
    from sqlalchemy.orm import selectinload
    from app.models import ProductVariant

    stmt = (
        select(InventoryStock)
        .where(InventoryStock.quantity <= InventoryStock.reorder_level)
        .options(
            selectinload(InventoryStock.variant).options(
                selectinload(ProductVariant.product),
                selectinload(ProductVariant.color),
                selectinload(ProductVariant.size),
            ),
            selectinload(InventoryStock.warehouse),
        )
    )
    if warehouse_id:
        stmt = stmt.where(InventoryStock.warehouse_id == warehouse_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/movements", response_model=list[INVENTORY_MOVEMENT_RESPONSE_SCHEMA])
async def list_movements(
    variant_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    movement_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
) -> list[InventoryMovement]:
    stmt = select(InventoryMovement).order_by(InventoryMovement.created_at.desc())
    if variant_id:
        stmt = stmt.where(InventoryMovement.variant_id == variant_id)
    if warehouse_id:
        stmt = stmt.where(InventoryMovement.warehouse_id == warehouse_id)
    if movement_type:
        stmt = stmt.where(InventoryMovement.movement_type == movement_type)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/adjustments", response_model=INVENTORY_STOCK_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
@router.post("/adjust", response_model=INVENTORY_STOCK_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_adjustment(
    body: STOCK_ADJUSTMENT_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.adjust")),
) -> InventoryStock:
    service = INVENTORY_SERVICE(db)
    delta = body.quantity_delta
    if delta is None:
        if body.new_quantity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either quantity_delta or new_quantity is required",
            )
        # Lock the row so the delta is computed against the value that is actually updated.
        current_stock = await service.stock_repo.get_or_create_stock(
            body.variant_id, body.warehouse_id, lock=True
        )
        delta = body.new_quantity - current_stock.quantity

    stock, _ = await service.adjust_stock(
        variant_id=body.variant_id,
        warehouse_id=body.warehouse_id,
        quantity_delta=delta,
        movement_type=body.movement_type,
        note=body.note,
        created_by=current_user.id,
    )
    from app.services.product_service import PRODUCT_SERVICE
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    return stock


# ─── Stock Transfers ──────────────────────────────────────────────────────────
transfers_router = APIRouter(prefix="/inventory/transfers", tags=["Stock Transfers"])


@transfers_router.get("", response_model=list[STOCK_TRANSFER_RESPONSE_SCHEMA], include_in_schema=False)
@transfers_router.get("/", response_model=list[STOCK_TRANSFER_RESPONSE_SCHEMA])
async def list_transfers(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("inventory.read")),
) -> list[StockTransfer]:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(StockTransfer)
        .options(selectinload(StockTransfer.items))
        .offset(skip).limit(limit)
        .order_by(StockTransfer.created_at.desc())
    )
    return list(result.scalars().all())


@transfers_router.post("", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@transfers_router.post("/", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_transfer(
    body: STOCK_TRANSFER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    service = INVENTORY_SERVICE(db)
    items_data = [{"variant_id": i.variant_id, "quantity": i.quantity} for i in body.items]
    transfer = await service.create_transfer(
        from_warehouse_id=body.from_warehouse_id,
        to_warehouse_id=body.to_warehouse_id,
        items=items_data,
        created_by=current_user.id,
        notes=body.notes,
    )
    await db.commit()
    await db.refresh(transfer)
    return transfer


@transfers_router.post("/{id}/approve", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA)
async def approve_transfer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(StockTransfer).where(StockTransfer.id == id).options(selectinload(StockTransfer.items))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    if transfer.status != "DRAFT":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only DRAFT transfers can be approved")
    transfer.status = "PENDING"
    transfer.approved_by = current_user.id
    await db.commit()
    return transfer


@transfers_router.post("/{id}/dispatch", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA)
async def dispatch_transfer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    from sqlalchemy.orm import selectinload
    from app.services.product_service import PRODUCT_SERVICE

    result = await db.execute(
        select(StockTransfer).where(StockTransfer.id == id).options(selectinload(StockTransfer.items))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    service = INVENTORY_SERVICE(db)
    transfer = await service.dispatch_transfer(transfer, current_user.id)
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    return transfer


@transfers_router.post("/{id}/receive", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA)
async def receive_transfer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    from sqlalchemy.orm import selectinload
    from app.services.product_service import PRODUCT_SERVICE

    result = await db.execute(
        select(StockTransfer).where(StockTransfer.id == id).options(selectinload(StockTransfer.items))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    service = INVENTORY_SERVICE(db)
    transfer = await service.receive_transfer(transfer, current_user.id)
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    return transfer


@transfers_router.post("/{id}/complete", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA)
async def complete_transfer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    from sqlalchemy.orm import selectinload
    from app.services.product_service import PRODUCT_SERVICE

    result = await db.execute(
        select(StockTransfer).where(StockTransfer.id == id).options(selectinload(StockTransfer.items))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    service = INVENTORY_SERVICE(db)
    transfer = await service.complete_transfer(transfer, current_user.id)
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    return transfer


@transfers_router.post("/{id}/cancel", response_model=STOCK_TRANSFER_RESPONSE_SCHEMA)
async def cancel_transfer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inventory.transfer")),
) -> StockTransfer:
    from sqlalchemy.orm import selectinload
    from app.services.product_service import PRODUCT_SERVICE

    result = await db.execute(
        select(StockTransfer).where(StockTransfer.id == id).options(selectinload(StockTransfer.items))
    )
    transfer = result.scalar_one_or_none()
    if not transfer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer not found")
    service = INVENTORY_SERVICE(db)
    transfer = await service.cancel_transfer(transfer, current_user.id)
    await PRODUCT_SERVICE.increment_inventory_version(db)
    await db.commit()
    return transfer
