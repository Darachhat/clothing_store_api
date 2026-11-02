"""Purchases and Goods Receipts API endpoints."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models import GoodsReceipt, PurchaseOrder
from app.models import User
from app.repositories.purchase_repository import GoodsReceiptRepository, PurchaseOrderRepository
from app.schemas.purchase_schema import (
    GOODS_RECEIPT_CREATE_SCHEMA,
    GOODS_RECEIPT_CREATE_FOR_ORDER_SCHEMA,
    GOODS_RECEIPT_RESPONSE_SCHEMA,
    PURCHASE_ORDER_CREATE_SCHEMA,
    PURCHASE_ORDER_RESPONSE_SCHEMA,
    PURCHASE_ORDER_UPDATE_SCHEMA,
)
from app.services.purchase_service import PURCHASE_SERVICE

router = APIRouter(prefix="/purchases", tags=["Purchasing & Goods Receipts"])


# ── Purchase Orders ───────────────────────────────────────────────────────────
@router.get("", response_model=list[PURCHASE_ORDER_RESPONSE_SCHEMA])
async def list_purchase_orders(
    supplier_id: UUID | None = None,
    branch_id: UUID | None = None,
    warehouse_id: UUID | None = None,
    order_status: str | None = Query(None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> list[PurchaseOrder]:
    repo = PurchaseOrderRepository(db)
    orders = await repo.list_orders(
        skip=skip,
        limit=limit,
        supplier_id=supplier_id,
        branch_id=branch_id,
        warehouse_id=warehouse_id,
        status=order_status,
        from_date=from_date,
        to_date=to_date,
    )
    return list(orders)


@router.post("", response_model=PURCHASE_ORDER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PURCHASE_ORDER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("purchase.create")),
) -> PurchaseOrder:
    service = PURCHASE_SERVICE(db)
    po = await service.create_purchase_order(created_by=current_user.id, data=payload)
    await db.commit()
    return po


@router.get("/{order_id}", response_model=PURCHASE_ORDER_RESPONSE_SCHEMA)
async def get_purchase_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> PurchaseOrder:
    repo = PurchaseOrderRepository(db)
    po = await repo.get_by_id(order_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.patch("/{order_id}", response_model=PURCHASE_ORDER_RESPONSE_SCHEMA)
async def update_purchase_order(
    order_id: UUID,
    payload: PURCHASE_ORDER_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.create")),
) -> PurchaseOrder:
    service = PURCHASE_SERVICE(db)
    po = await service.update_purchase_order(po_id=order_id, data=payload)
    await db.commit()
    return po


@router.post("/{order_id}/approve", response_model=PURCHASE_ORDER_RESPONSE_SCHEMA)
async def approve_purchase_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("purchase.create")),
) -> PurchaseOrder:
    service = PURCHASE_SERVICE(db)
    po = await service.approve_purchase_order(po_id=order_id, approved_by=current_user.id)
    await db.commit()
    return po


@router.post("/{order_id}/cancel", response_model=PURCHASE_ORDER_RESPONSE_SCHEMA)
async def cancel_purchase_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.create")),
) -> PurchaseOrder:
    service = PURCHASE_SERVICE(db)
    po = await service.cancel_purchase_order(po_id=order_id)
    await db.commit()
    return po


# ── Goods Receipts ────────────────────────────────────────────────────────────
@router.get("/{order_id}/receipts", response_model=list[GOODS_RECEIPT_RESPONSE_SCHEMA])
async def list_order_receipts(
    order_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> list[GoodsReceipt]:
    repo = GoodsReceiptRepository(db)
    receipts = await repo.list_receipts(purchase_order_id=order_id, skip=skip, limit=limit)
    return list(receipts)


@router.post("/{order_id}/receive", response_model=GOODS_RECEIPT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def receive_purchase_order(
    order_id: UUID,
    payload: GOODS_RECEIPT_CREATE_FOR_ORDER_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("purchase.receive")),
) -> GoodsReceipt:
    service = PURCHASE_SERVICE(db)
    data = GOODS_RECEIPT_CREATE_SCHEMA(
        purchase_order_id=order_id,
        warehouse_id=payload.warehouse_id,
        notes=payload.notes if payload.notes is not None else payload.note,
        items=payload.items,
    )
    gr = await service.create_goods_receipt(received_by=current_user.id, data=data)
    await db.commit()
    return gr


@router.post("/receipts", response_model=GOODS_RECEIPT_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_goods_receipt(
    payload: GOODS_RECEIPT_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("purchase.receive")),
) -> GoodsReceipt:
    service = PURCHASE_SERVICE(db)
    gr = await service.create_goods_receipt(received_by=current_user.id, data=payload)
    await db.commit()
    return gr


@router.get("/receipts/{receipt_id}", response_model=GOODS_RECEIPT_RESPONSE_SCHEMA)
async def get_goods_receipt(
    receipt_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("purchase.read")),
) -> GoodsReceipt:
    repo = GoodsReceiptRepository(db)
    gr = await repo.get_by_id(receipt_id)
    if not gr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goods receipt not found")
    return gr
