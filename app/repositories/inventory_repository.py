"""Inventory repository: stock queries and movement recording."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import InventoryMovement, InventoryStock
from app.repositories.base import BaseRepository


class InventoryStockRepository(BaseRepository[InventoryStock]):
    def __init__(self, db) -> None:
        super().__init__(InventoryStock, db)

    async def get_stock(
        self, variant_id: UUID, warehouse_id: UUID, *, lock: bool = False
    ) -> InventoryStock | None:
        """Fetch a stock row. With ``lock=True`` the row is locked (SELECT ... FOR UPDATE)
        until the surrounding transaction ends, so concurrent adjustments serialize and
        no update is lost. The row is also refreshed so a stale identity-map copy is never used."""
        stmt = select(InventoryStock).where(
            InventoryStock.variant_id == variant_id,
            InventoryStock.warehouse_id == warehouse_id,
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_stock(
        self, variant_id: UUID, warehouse_id: UUID, *, lock: bool = False
    ) -> InventoryStock:
        """Return the stock row, creating it at quantity 0 if missing.

        Safe under concurrency: the insert runs in a SAVEPOINT, and if another transaction
        created the row first (unique violation) we fall back to reading (and locking) it.
        """
        stock = await self.get_stock(variant_id, warehouse_id, lock=lock)
        if stock:
            return stock
        try:
            async with self.db.begin_nested():
                stock = InventoryStock(variant_id=variant_id, warehouse_id=warehouse_id, quantity=0)
                self.db.add(stock)
                await self.db.flush()
            if lock:
                stock = await self.get_stock(variant_id, warehouse_id, lock=True) or stock
            return stock
        except IntegrityError:
            existing = await self.get_stock(variant_id, warehouse_id, lock=lock)
            if existing is None:
                raise
            return existing
    async def get_low_stock(self, warehouse_id: UUID | None = None) -> list[InventoryStock]:
        stmt = select(InventoryStock).where(
            InventoryStock.quantity <= InventoryStock.reorder_level
        )
        if warehouse_id:
            stmt = stmt.where(InventoryStock.warehouse_id == warehouse_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def adjust_stock(
        self,
        variant_id: UUID,
        warehouse_id: UUID,
        delta: int,
        movement_type: str,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        note: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[InventoryStock, InventoryMovement]:
        """Atomically adjust stock and record movement. Must be called within a transaction."""
        stock = await self.get_or_create_stock(variant_id, warehouse_id, lock=True)
        before = stock.quantity
        after = before + delta

        if after < 0:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {before}, requested: {abs(delta)}",
            )

        stock.quantity = after

        movement = InventoryMovement(
            variant_id=variant_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=delta,
            before_quantity=before,
            after_quantity=after,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=created_by,
        )
        self.db.add(movement)
        return stock, movement
