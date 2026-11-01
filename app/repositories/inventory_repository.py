"""Inventory repository: stock queries and movement recording."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.models import InventoryMovement, InventoryStock
from app.repositories.base import BaseRepository


class InventoryStockRepository(BaseRepository[InventoryStock]):
    def __init__(self, db) -> None:
        super().__init__(InventoryStock, db)

    async def get_stock(self, variant_id: UUID, warehouse_id: UUID) -> InventoryStock | None:
        result = await self.db.execute(
            select(InventoryStock)
            .where(
                InventoryStock.variant_id == variant_id,
                InventoryStock.warehouse_id == warehouse_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_stock(
        self, variant_id: UUID, warehouse_id: UUID
    ) -> InventoryStock:
        stock = await self.get_stock(variant_id, warehouse_id)
        if not stock:
            stock = await self.create(
                variant_id=variant_id,
                warehouse_id=warehouse_id,
                quantity=0,
            )
        return stock

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
        stock = await self.get_or_create_stock(variant_id, warehouse_id)
        before = stock.quantity
        after = before + delta

        if after < 0:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock. Available: {before}, requested: {abs(delta)}",
            )

        stock.quantity = after
        await self.db.flush()

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
        await self.db.flush()
        return stock, movement
