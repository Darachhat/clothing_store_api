"""Purchase service: purchase orders, approval, goods receipts and stock movement."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enum.common_enum import (
    COMMON_STATUS_ENUM
    , GOODS_RECEIPT_STATUS_ENUM
    , INVENTORY_MOVEMENT_TYPE_ENUM
    , PURCHASE_STATUS_ENUM
    , REFERENCE_TYPE_ENUM
)
from app.core.exceptions import BAD_REQUEST_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import (
    Branch
    , GoodsReceipt
    , GoodsReceiptItem
    , PurchaseItem
    , PurchaseOrder
    , Warehouse
)
from app.repositories.inventory_repository import InventoryStockRepository
from app.repositories.product_repository import ProductVariantRepository
from app.repositories.purchase_repository import (
    GoodsReceiptRepository
    , PurchaseOrderRepository
)
from app.schemas.purchase_schema import (
    GOODS_RECEIPT_CREATE_SCHEMA
    , PURCHASE_ORDER_CREATE_SCHEMA
    , PURCHASE_ORDER_UPDATE_SCHEMA
)
from app.utils.generators import generate_gr_number, generate_po_number

logger = get_logger(__name__)


class PURCHASE_SERVICE:
    """Service handling Purchase Orders procurement workflow and Goods Receipts stocking."""

    def __init__(self, db: AsyncSession) -> None:
        self.db           = db
        self.po_repo      = PurchaseOrderRepository(db)
        self.gr_repo      = GoodsReceiptRepository(db)
        self.stock_repo   = InventoryStockRepository(db)
        self.variant_repo = ProductVariantRepository(db)

    async def create_purchase_order(
        self
        , created_by : UUID
        , data       : PURCHASE_ORDER_CREATE_SCHEMA
    ) -> PurchaseOrder:
        branch_id    = data.branch_id
        warehouse_id = data.warehouse_id

        if not branch_id or not warehouse_id:
            if warehouse_id and not branch_id:
                wh = (
                    await self.db.execute(
                        select(Warehouse).where(Warehouse.id == warehouse_id)
                    )
                ).scalar_one_or_none()
                if wh:
                    branch_id = wh.branch_id

            if not branch_id:
                branch = (
                    await self.db.execute(
                        select(Branch)
                        .where(Branch.status == COMMON_STATUS_ENUM.ACTIVE.value)
                        .order_by(Branch.created_at.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if not branch:
                    branch = (await self.db.execute(select(Branch).limit(1))).scalar_one_or_none()
                if branch:
                    branch_id = branch.id

            if not warehouse_id and branch_id:
                wh = (
                    await self.db.execute(
                        select(Warehouse)
                        .where(
                            Warehouse.branch_id == branch_id
                            , Warehouse.status == COMMON_STATUS_ENUM.ACTIVE.value
                        )
                        .order_by(Warehouse.is_default.desc(), Warehouse.created_at.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if wh:
                    warehouse_id = wh.id

            if not warehouse_id:
                wh_any = (await self.db.execute(select(Warehouse).limit(1))).scalar_one_or_none()
                if wh_any:
                    warehouse_id = wh_any.id
                    if not branch_id:
                        branch_id = wh_any.branch_id

        po_number = await generate_po_number(self.db)

        subtotal = Decimal("0")
        items_to_create = []

        for item_in in data.items:
            variant = await self.variant_repo.get_by_id(item_in.variant_id)
            if not variant:
                raise NOT_FOUND_EXCEPTION(f"Variant {item_in.variant_id} not found")

            line_subtotal = Decimal(str(item_in.quantity_ordered)) * item_in.unit_cost
            subtotal += line_subtotal
            items_to_create.append(
                PurchaseItem(
                    variant_id        = item_in.variant_id
                    , quantity_ordered = item_in.quantity_ordered
                    , quantity_received = 0
                    , unit_cost       = item_in.unit_cost
                    , subtotal        = line_subtotal
                )
            )

        total = subtotal + data.tax_amount

        po = PurchaseOrder(
            po_number      = po_number
            , supplier_id  = data.supplier_id
            , branch_id    = branch_id
            , warehouse_id = warehouse_id
            , status       = PURCHASE_STATUS_ENUM.DRAFT.value
            , subtotal     = subtotal
            , tax_amount   = data.tax_amount
            , total        = total
            , expected_date = data.expected_date
            , notes        = data.notes
            , created_by   = created_by
            , items        = items_to_create
        )

        self.db.add(po)
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def update_purchase_order(
        self
        , po_id : UUID
        , data  : PURCHASE_ORDER_UPDATE_SCHEMA
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise NOT_FOUND_EXCEPTION(f"Purchase order {po_id} not found")

        valid_update_statuses = [
            PURCHASE_STATUS_ENUM.DRAFT.value
            , PURCHASE_STATUS_ENUM.ORDERED.value
        ]
        if po.status not in valid_update_statuses and data.status not in [None, po.status]:
            raise BAD_REQUEST_EXCEPTION(f"Cannot update purchase order in status {po.status}")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(po, key, value)

        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def approve_purchase_order(
        self
        , po_id       : UUID
        , approved_by : UUID
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise NOT_FOUND_EXCEPTION(f"Purchase order {po_id} not found")

        if po.status != PURCHASE_STATUS_ENUM.DRAFT.value:
            raise BAD_REQUEST_EXCEPTION(
                f"Only DRAFT purchase orders can be approved (current: {po.status})"
            )

        po.status      = PURCHASE_STATUS_ENUM.ORDERED.value
        po.approved_by = approved_by
        from app.services.audit_service import AUDIT_SERVICE

        await AUDIT_SERVICE.record(
            self.db
            , action      = "PURCHASE_ORDER_APPROVED"
            , entity_type = "purchase_order"
            , entity_id   = po.id
            , user_id     = approved_by
            , old_data    = {"status": PURCHASE_STATUS_ENUM.DRAFT.value}
            , new_data    = {"status": PURCHASE_STATUS_ENUM.ORDERED.value, "po_number": po.po_number}
        )
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def cancel_purchase_order(
        self
        , po_id : UUID
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise NOT_FOUND_EXCEPTION(f"Purchase order {po_id} not found")

        non_cancellable = [
            PURCHASE_STATUS_ENUM.RECEIVED.value
            , PURCHASE_STATUS_ENUM.CANCELLED.value
        ]
        if po.status in non_cancellable:
            raise BAD_REQUEST_EXCEPTION(f"Cannot cancel purchase order in status {po.status}")

        po.status = PURCHASE_STATUS_ENUM.CANCELLED.value
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def create_goods_receipt(
        self
        , received_by : UUID
        , data        : GOODS_RECEIPT_CREATE_SCHEMA
    ) -> GoodsReceipt:
        po = await self.po_repo.get_by_id(data.purchase_order_id)
        if not po:
            raise NOT_FOUND_EXCEPTION(f"Purchase order {data.purchase_order_id} not found")

        non_receivable = [
            PURCHASE_STATUS_ENUM.CANCELLED.value
            , PURCHASE_STATUS_ENUM.RECEIVED.value
        ]
        if po.status in non_receivable:
            raise BAD_REQUEST_EXCEPTION(
                f"Cannot receive goods for purchase order in status {po.status}"
            )

        target_warehouse_id = data.warehouse_id or po.warehouse_id
        gr_number           = await generate_gr_number(self.db)
        receipt_notes       = data.notes if data.notes is not None else getattr(data, "note", None)

        gr = GoodsReceipt(
            gr_number           = gr_number
            , purchase_order_id = po.id
            , warehouse_id      = target_warehouse_id
            , status            = GOODS_RECEIPT_STATUS_ENUM.COMPLETED.value
            , notes             = receipt_notes
            , received_by       = received_by
        )
        self.db.add(gr)
        await self.db.flush()

        po_items_map        = {item.id: item for item in po.items}
        po_items_by_variant = {item.variant_id: item for item in po.items}

        for item_in in data.items:
            po_item = po_items_map.get(item_in.purchase_item_id) if item_in.purchase_item_id else None
            if not po_item:
                po_item = po_items_by_variant.get(item_in.variant_id)
            if not po_item:
                raise BAD_REQUEST_EXCEPTION(
                    f"Purchase item {item_in.purchase_item_id or item_in.variant_id} does not belong to purchase order {po.id}"
                )

            effective_unit_cost = item_in.unit_cost if item_in.unit_cost is not None else po_item.unit_cost

            gr_item = GoodsReceiptItem(
                goods_receipt_id   = gr.id
                , purchase_item_id = po_item.id
                , variant_id       = item_in.variant_id
                , quantity_received = item_in.quantity_received
                , unit_cost        = effective_unit_cost
                , notes            = item_in.notes
            )
            self.db.add(gr_item)

            # Update received quantity on PO item
            po_item.quantity_received += item_in.quantity_received

            # Update inventory stock and record audit movement
            await self.stock_repo.adjust_stock(
                variant_id     = item_in.variant_id
                , warehouse_id   = target_warehouse_id
                , delta          = item_in.quantity_received
                , movement_type  = INVENTORY_MOVEMENT_TYPE_ENUM.PURCHASE.value
                , reference_type = "GOODS_RECEIPT"
                , reference_id   = gr.id
                , note           = f"Received via {gr_number} for PO {po.po_number}"
                , created_by     = received_by
            )

            # Update variant cost_price if desired
            variant = await self.variant_repo.get_by_id(item_in.variant_id)
            if variant:
                variant.cost_price = effective_unit_cost

        # Update PO status based on received items
        all_completed = True
        any_received  = False
        for item in po.items:
            if item.quantity_received < item.quantity_ordered:
                all_completed = False
            if item.quantity_received > 0:
                any_received = True

        if all_completed:
            po.status = PURCHASE_STATUS_ENUM.RECEIVED.value
        elif any_received:
            po.status = PURCHASE_STATUS_ENUM.PARTIAL.value
        else:
            po.status = PURCHASE_STATUS_ENUM.ORDERED.value

        from app.services.audit_service import AUDIT_SERVICE
        from app.services.product_service import PRODUCT_SERVICE

        await AUDIT_SERVICE.record(
            self.db
            , action      = "GOODS_RECEIPT_CREATED"
            , entity_type = "goods_receipt"
            , entity_id   = gr.id
            , user_id     = received_by
            , new_data    = {
                "gr_number": gr.gr_number
                , "purchase_order_id": str(po.id)
                , "po_status": po.status
                , "warehouse_id": str(target_warehouse_id) if target_warehouse_id else None
            }
        )
        await PRODUCT_SERVICE.increment_inventory_version(self.db)
        await PRODUCT_SERVICE.increment_catalog_version(self.db)
        await self.db.flush()
        return await self.gr_repo.get_by_id(gr.id)


PurchaseService = PURCHASE_SERVICE