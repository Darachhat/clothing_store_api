"""Inventory service: stock adjustments, transfers."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enum.common_enum import (
    INVENTORY_MOVEMENT_TYPE_ENUM
    , REFERENCE_TYPE_ENUM
    , STOCK_TRANSFER_STATUS_ENUM
)
from app.core.exceptions import BAD_REQUEST_EXCEPTION
from app.core.logging import get_logger
from app.models import InventoryMovement, InventoryStock, StockTransfer, StockTransferItem
from app.repositories.inventory_repository import InventoryStockRepository
from app.schemas.inventory_schema import (
    INVENTORY_MOVEMENT_RESPONSE_SCHEMA
    , INVENTORY_STOCK_RESPONSE_SCHEMA
    , STOCK_ADJUSTMENT_CREATE_SCHEMA
    , STOCK_ADJUSTMENT_RESPONSE_SCHEMA
    , STOCK_TRANSFER_CREATE_SCHEMA
    , STOCK_TRANSFER_RESPONSE_SCHEMA
)
from app.utils.generators import generate_transfer_number

logger = get_logger(__name__)


class INVENTORY_SERVICE:
    """Service managing Inventory stock adjustments, audits, and warehouse-to-warehouse transfers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db         = db
        self.stock_repo = InventoryStockRepository(db)

    async def adjust_stock(
        self
        , variant_id     : UUID
        , warehouse_id   : UUID
        , quantity_delta : int
        , movement_type  : str
        , reference_type : Optional[str] = None
        , reference_id   : Optional[UUID] = None
        , note           : Optional[str] = None
        , created_by     : Optional[UUID] = None
    ) -> Tuple[InventoryStock, InventoryMovement]:
        """Adjust stock and record movement. Call within a transaction."""
        stock, movement = await self.stock_repo.adjust_stock(
            variant_id     = variant_id
            , warehouse_id   = warehouse_id
            , delta          = quantity_delta
            , movement_type  = movement_type
            , reference_type = reference_type
            , reference_id   = reference_id
            , note           = note
            , created_by     = created_by
        )
        from app.services.audit_service import AUDIT_SERVICE

        await AUDIT_SERVICE.record(
            self.db
            , action      = f"INVENTORY_{movement_type.upper()}"
            , entity_type = "inventory_stock"
            , entity_id   = stock.id
            , user_id     = created_by
            , old_data    = {"quantity": movement.before_quantity}
            , new_data    = {
                "quantity": movement.after_quantity
                , "delta": quantity_delta
                , "variant_id": str(variant_id)
                , "warehouse_id": str(warehouse_id)
                , "note": note
            }
        )
        return stock, movement

    async def create_transfer(
        self
        , from_warehouse_id : UUID
        , to_warehouse_id   : UUID
        , items             : List[Dict[str, Any]]
        , created_by        : UUID
        , notes             : Optional[str] = None
    ) -> StockTransfer:
        if from_warehouse_id == to_warehouse_id:
            raise BAD_REQUEST_EXCEPTION("Source and destination warehouses must differ")

        transfer_number = await generate_transfer_number(self.db)
        transfer = StockTransfer(
            transfer_number   = transfer_number
            , from_warehouse_id = from_warehouse_id
            , to_warehouse_id   = to_warehouse_id
            , status            = STOCK_TRANSFER_STATUS_ENUM.DRAFT.value
            , notes             = notes
            , created_by        = created_by
        )
        self.db.add(transfer)
        await self.db.flush()

        for item_data in items:
            item = StockTransferItem(
                transfer_id        = transfer.id
                , variant_id         = item_data["variant_id"]
                , quantity_requested = item_data["quantity"]
            )
            self.db.add(item)

        await self.db.flush()
        return transfer

    async def dispatch_transfer(
        self
        , transfer      : StockTransfer
        , dispatched_by : UUID
    ) -> StockTransfer:
        valid_dispatch_statuses = (
            STOCK_TRANSFER_STATUS_ENUM.PENDING.value
            , STOCK_TRANSFER_STATUS_ENUM.DRAFT.value
            , STOCK_TRANSFER_STATUS_ENUM.APPROVED.value
        )
        if transfer.status not in valid_dispatch_statuses:
            raise BAD_REQUEST_EXCEPTION("Only DRAFT, PENDING, or APPROVED transfers can be dispatched")

        for item in transfer.items:
            await self.stock_repo.adjust_stock(
                variant_id     = item.variant_id
                , warehouse_id   = transfer.from_warehouse_id
                , delta          = -item.quantity_requested
                , movement_type  = INVENTORY_MOVEMENT_TYPE_ENUM.TRANSFER_OUT.value
                , reference_type = REFERENCE_TYPE_ENUM.TRANSFER.value
                , reference_id   = transfer.id
                , created_by     = dispatched_by
            )
            item.quantity_sent = item.quantity_requested

        transfer.status     = STOCK_TRANSFER_STATUS_ENUM.IN_TRANSIT.value
        transfer.shipped_at = datetime.now(UTC)
        await self.db.flush()
        return transfer

    async def complete_transfer(
        self
        , transfer     : StockTransfer
        , completed_by : UUID
    ) -> StockTransfer:
        """Complete a transfer in one step or finalize an IN_TRANSIT transfer."""
        pre_dispatch_statuses = (
            STOCK_TRANSFER_STATUS_ENUM.DRAFT.value
            , STOCK_TRANSFER_STATUS_ENUM.PENDING.value
            , STOCK_TRANSFER_STATUS_ENUM.APPROVED.value
        )
        if transfer.status in pre_dispatch_statuses:
            await self.dispatch_transfer(transfer, completed_by)
        if transfer.status == STOCK_TRANSFER_STATUS_ENUM.IN_TRANSIT.value:
            await self.receive_transfer(transfer, completed_by)
            return transfer
        raise BAD_REQUEST_EXCEPTION(f"Cannot complete transfer in status {transfer.status}")

    async def receive_transfer(
        self
        , transfer    : StockTransfer
        , received_by : UUID
    ) -> StockTransfer:
        if transfer.status != STOCK_TRANSFER_STATUS_ENUM.IN_TRANSIT.value:
            raise BAD_REQUEST_EXCEPTION("Only IN_TRANSIT transfers can be received")

        for item in transfer.items:
            await self.stock_repo.adjust_stock(
                variant_id     = item.variant_id
                , warehouse_id   = transfer.to_warehouse_id
                , delta          = item.quantity_sent
                , movement_type  = INVENTORY_MOVEMENT_TYPE_ENUM.TRANSFER_IN.value
                , reference_type = REFERENCE_TYPE_ENUM.TRANSFER.value
                , reference_id   = transfer.id
                , created_by     = received_by
            )
            item.quantity_received = item.quantity_sent

        transfer.status      = STOCK_TRANSFER_STATUS_ENUM.RECEIVED.value
        transfer.received_at = datetime.now(UTC)
        await self.db.flush()
        return transfer

    async def cancel_transfer(
        self
        , transfer     : StockTransfer
        , cancelled_by : UUID
    ) -> StockTransfer:
        cancellable_statuses = (
            STOCK_TRANSFER_STATUS_ENUM.DRAFT.value
            , STOCK_TRANSFER_STATUS_ENUM.PENDING.value
            , STOCK_TRANSFER_STATUS_ENUM.IN_TRANSIT.value
        )
        if transfer.status not in cancellable_statuses:
            raise BAD_REQUEST_EXCEPTION(f"Cannot cancel transfer in status {transfer.status}")

        # If already IN_TRANSIT, restore source stock
        if transfer.status == STOCK_TRANSFER_STATUS_ENUM.IN_TRANSIT.value:
            for item in transfer.items:
                await self.stock_repo.adjust_stock(
                    variant_id     = item.variant_id
                    , warehouse_id   = transfer.from_warehouse_id
                    , delta          = item.quantity_sent
                    , movement_type  = INVENTORY_MOVEMENT_TYPE_ENUM.TRANSFER_IN.value
                    , reference_type = f"{REFERENCE_TYPE_ENUM.TRANSFER.value}_cancel"
                    , reference_id   = transfer.id
                    , note           = "Transfer cancelled - stock restored"
                    , created_by     = cancelled_by
                )

        transfer.status = STOCK_TRANSFER_STATUS_ENUM.CANCELLED.value
        await self.db.flush()
        return transfer

    async def adjust_stock_payload(
        self
        , payload    : STOCK_ADJUSTMENT_CREATE_SCHEMA
        , created_by : Optional[UUID] = None
    ) -> Tuple[InventoryStock, InventoryMovement]:
        """Adjust inventory stock using structured STOCK_ADJUSTMENT_CREATE_SCHEMA."""
        delta = payload.quantity_delta
        if delta is None and payload.new_quantity is not None:
            current_stock = await self.stock_repo.get_stock(payload.variant_id, payload.warehouse_id)
            current_qty = current_stock.quantity if current_stock else 0
            delta = payload.new_quantity - current_qty

        return await self.adjust_stock(
            variant_id     = payload.variant_id
            , warehouse_id   = payload.warehouse_id
            , quantity_delta = delta or 0
            , movement_type  = payload.movement_type
            , reference_type = "ADJUSTMENT"
            , reference_id   = None
            , note           = payload.note
            , created_by     = created_by
        )

    async def create_transfer_payload(
        self
        , payload    : STOCK_TRANSFER_CREATE_SCHEMA
        , created_by : UUID
    ) -> StockTransfer:
        """Create warehouse stock transfer using structured STOCK_TRANSFER_CREATE_SCHEMA."""
        return await self.create_transfer(
            from_warehouse_id = payload.from_warehouse_id
            , to_warehouse_id   = payload.to_warehouse_id
            , items             = [item.model_dump() for item in payload.items]
            , created_by        = created_by
            , notes             = payload.notes
        )
