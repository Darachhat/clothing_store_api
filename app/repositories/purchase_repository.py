"""Purchase order and goods receipt repositories."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import GoodsReceipt, PurchaseOrder
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(PurchaseOrder, db)

    async def get_by_id(self, id: UUID) -> PurchaseOrder | None:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.id == id)
            .options(
                selectinload(PurchaseOrder.items),
                selectinload(PurchaseOrder.goods_receipts).selectinload(GoodsReceipt.items),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_po_number(self, po_number: str) -> PurchaseOrder | None:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.po_number == po_number)
            .options(
                selectinload(PurchaseOrder.items),
                selectinload(PurchaseOrder.goods_receipts).selectinload(GoodsReceipt.items),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_orders(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        supplier_id: UUID | None = None,
        branch_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> Sequence[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.items),
                selectinload(PurchaseOrder.goods_receipts).selectinload(GoodsReceipt.items),
            )
            .order_by(PurchaseOrder.created_at.desc())
        )
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if branch_id:
            stmt = stmt.where(PurchaseOrder.branch_id == branch_id)
        if warehouse_id:
            stmt = stmt.where(PurchaseOrder.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if from_date:
            stmt = stmt.where(func.date(PurchaseOrder.created_at) >= from_date)
        if to_date:
            stmt = stmt.where(func.date(PurchaseOrder.created_at) <= to_date)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_orders(
        self,
        *,
        supplier_id: UUID | None = None,
        branch_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(PurchaseOrder)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if branch_id:
            stmt = stmt.where(PurchaseOrder.branch_id == branch_id)
        if warehouse_id:
            stmt = stmt.where(PurchaseOrder.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if from_date:
            stmt = stmt.where(func.date(PurchaseOrder.created_at) >= from_date)
        if to_date:
            stmt = stmt.where(func.date(PurchaseOrder.created_at) <= to_date)

        result = await self.db.execute(stmt)
        return result.scalar_one()


class GoodsReceiptRepository(BaseRepository[GoodsReceipt]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(GoodsReceipt, db)

    async def get_by_id(self, id: UUID) -> GoodsReceipt | None:
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.id == id)
            .options(selectinload(GoodsReceipt.items))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_receipts(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        purchase_order_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        status: str | None = None,
    ) -> Sequence[GoodsReceipt]:
        stmt = (
            select(GoodsReceipt)
            .options(selectinload(GoodsReceipt.items))
            .order_by(GoodsReceipt.created_at.desc())
        )
        if purchase_order_id:
            stmt = stmt.where(GoodsReceipt.purchase_order_id == purchase_order_id)
        if warehouse_id:
            stmt = stmt.where(GoodsReceipt.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(GoodsReceipt.status == status)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_receipts(
        self,
        *,
        purchase_order_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        status: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(GoodsReceipt)
        if purchase_order_id:
            stmt = stmt.where(GoodsReceipt.purchase_order_id == purchase_order_id)
        if warehouse_id:
            stmt = stmt.where(GoodsReceipt.warehouse_id == warehouse_id)
        if status:
            stmt = stmt.where(GoodsReceipt.status == status)

        result = await self.db.execute(stmt)
        return result.scalar_one()
