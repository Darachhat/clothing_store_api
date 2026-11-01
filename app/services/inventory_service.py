"""Inventory service: stock adjustments, transfers."""
from __future__ import annotations

from datetime import UTC
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryMovement, InventoryStock, StockTransfer, StockTransferItem
from app.repositories.inventory_repository import InventoryStockRepository
from app.utils.generators import generate_transfer_number


class InventoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.stock_repo = InventoryStockRepository(db)

    async def adjust_stock(
        self,
        variant_id: UUID,
        warehouse_id: UUID,
        quantity_delta: int,
        movement_type: str,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        note: str | None = None,
        created_by: UUID | None = None,
    ) -> tuple[InventoryStock, InventoryMovement]:
        """Adjust stock and record movement. Call within a transaction."""
        stock, movement = await self.stock_repo.adjust_stock(
            variant_id=variant_id,
            warehouse_id=warehouse_id,
            delta=quantity_delta,
            movement_type=movement_type,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=created_by,
        )
        from app.services.audit_service import AuditService

        await AuditService.record(
            self.db,
            action=f"INVENTORY_{movement_type.upper()}",
            entity_type="inventory_stock",
            entity_id=stock.id,
            user_id=created_by,
            old_data={"quantity": movement.before_quantity},
            new_data={
                "quantity": movement.after_quantity,
                "delta": quantity_delta,
                "variant_id": str(variant_id),
                "warehouse_id": str(warehouse_id),
                "note": note,
            },
        )
        return stock, movement

    async def create_transfer(
        self,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        items: list[dict],
        created_by: UUID,
        notes: str | None = None,
    ) -> StockTransfer:
        if from_warehouse_id == to_warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source and destination warehouses must differ",
            )

        transfer_number = await generate_transfer_number(self.db)
        transfer = StockTransfer(
            transfer_number=transfer_number,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            status="DRAFT",
            notes=notes,
            created_by=created_by,
        )
        self.db.add(transfer)
        await self.db.flush()

        for item_data in items:
            item = StockTransferItem(
                transfer_id=transfer.id,
                variant_id=item_data["variant_id"],
                quantity_requested=item_data["quantity"],
            )
            self.db.add(item)

        await self.db.flush()
        return transfer

    async def dispatch_transfer(
        self, transfer: StockTransfer, dispatched_by: UUID
    ) -> StockTransfer:
        if transfer.status not in ("PENDING", "DRAFT", "APPROVED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DRAFT, PENDING, or APPROVED transfers can be dispatched",
            )

        for item in transfer.items:
            await self.stock_repo.adjust_stock(
                variant_id=item.variant_id,
                warehouse_id=transfer.from_warehouse_id,
                delta=-item.quantity_requested,
                movement_type="TRANSFER_OUT",
                reference_type="transfer",
                reference_id=transfer.id,
                created_by=dispatched_by,
            )
            item.quantity_sent = item.quantity_requested

        from datetime import datetime

        transfer.status = "IN_TRANSIT"
        transfer.shipped_at = datetime.now(UTC)
        await self.db.flush()
        return transfer

    async def complete_transfer(
        self, transfer: StockTransfer, completed_by: UUID
    ) -> StockTransfer:
        """Complete a transfer in one step or finalize an IN_TRANSIT transfer."""
        if transfer.status in ("DRAFT", "PENDING", "APPROVED"):
            await self.dispatch_transfer(transfer, completed_by)
        if transfer.status == "IN_TRANSIT":
            await self.receive_transfer(transfer, completed_by)
            return transfer
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete transfer in status {transfer.status}",
        )

    async def receive_transfer(
        self, transfer: StockTransfer, received_by: UUID
    ) -> StockTransfer:
        if transfer.status != "IN_TRANSIT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only IN_TRANSIT transfers can be received",
            )

        for item in transfer.items:
            await self.stock_repo.adjust_stock(
                variant_id=item.variant_id,
                warehouse_id=transfer.to_warehouse_id,
                delta=item.quantity_sent,
                movement_type="TRANSFER_IN",
                reference_type="transfer",
                reference_id=transfer.id,
                created_by=received_by,
            )
            item.quantity_received = item.quantity_sent

        from datetime import datetime

        transfer.status = "RECEIVED"
        transfer.received_at = datetime.now(UTC)
        await self.db.flush()
        return transfer

    async def cancel_transfer(
        self, transfer: StockTransfer, cancelled_by: UUID
    ) -> StockTransfer:
        if transfer.status not in ("DRAFT", "PENDING", "IN_TRANSIT"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel transfer in status {transfer.status}",
            )

        # If already IN_TRANSIT, restore source stock
        if transfer.status == "IN_TRANSIT":
            for item in transfer.items:
                await self.stock_repo.adjust_stock(
                    variant_id=item.variant_id,
                    warehouse_id=transfer.from_warehouse_id,
                    delta=item.quantity_sent,
                    movement_type="TRANSFER_IN",
                    reference_type="transfer_cancel",
                    reference_id=transfer.id,
                    note="Transfer cancelled - stock restored",
                    created_by=cancelled_by,
                )

        transfer.status = "CANCELLED"
        await self.db.flush()
        return transfer
