"""Purchase service: purchase orders, approval, goods receipts and stock movement."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import GoodsReceipt, GoodsReceiptItem, PurchaseItem, PurchaseOrder
from app.repositories.inventory_repository import InventoryStockRepository
from app.repositories.product_repository import ProductVariantRepository
from app.repositories.purchase_repository import GoodsReceiptRepository, PurchaseOrderRepository
from app.schemas.purchase import GoodsReceiptCreate, PurchaseOrderCreate, PurchaseOrderUpdate
from app.utils.generators import generate_gr_number, generate_po_number


class PurchaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.po_repo = PurchaseOrderRepository(db)
        self.gr_repo = GoodsReceiptRepository(db)
        self.stock_repo = InventoryStockRepository(db)
        self.variant_repo = ProductVariantRepository(db)

    async def create_purchase_order(
        self,
        created_by: UUID,
        data: PurchaseOrderCreate,
    ) -> PurchaseOrder:
        po_number = await generate_po_number(self.db)

        subtotal = Decimal("0")
        items_to_create = []

        for item_in in data.items:
            variant = await self.variant_repo.get_by_id(item_in.variant_id)
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant {item_in.variant_id} not found",
                )
            line_subtotal = Decimal(str(item_in.quantity_ordered)) * item_in.unit_cost
            subtotal += line_subtotal
            items_to_create.append(
                PurchaseItem(
                    variant_id=item_in.variant_id,
                    quantity_ordered=item_in.quantity_ordered,
                    quantity_received=0,
                    unit_cost=item_in.unit_cost,
                    subtotal=line_subtotal,
                )
            )

        total = subtotal + data.tax_amount

        po = PurchaseOrder(
            po_number=po_number,
            supplier_id=data.supplier_id,
            branch_id=data.branch_id,
            warehouse_id=data.warehouse_id,
            status="DRAFT",
            subtotal=subtotal,
            tax_amount=data.tax_amount,
            total=total,
            expected_date=data.expected_date,
            notes=data.notes,
            created_by=created_by,
            items=items_to_create,
        )

        self.db.add(po)
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def update_purchase_order(
        self,
        po_id: UUID,
        data: PurchaseOrderUpdate,
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found",
            )

        if po.status not in ["DRAFT", "ORDERED"] and data.status not in [None, po.status]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update purchase order in status {po.status}",
            )

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(po, key, value)

        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def approve_purchase_order(
        self,
        po_id: UUID,
        approved_by: UUID,
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found",
            )
        if po.status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only DRAFT purchase orders can be approved (current: {po.status})",
            )

        po.status = "ORDERED"
        po.approved_by = approved_by
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def cancel_purchase_order(
        self,
        po_id: UUID,
    ) -> PurchaseOrder:
        po = await self.po_repo.get_by_id(po_id)
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {po_id} not found",
            )
        if po.status in ["RECEIVED", "CANCELLED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel purchase order in status {po.status}",
            )

        po.status = "CANCELLED"
        await self.db.flush()
        return await self.po_repo.get_by_id(po.id)

    async def create_goods_receipt(
        self,
        received_by: UUID,
        data: GoodsReceiptCreate,
    ) -> GoodsReceipt:
        po = await self.po_repo.get_by_id(data.purchase_order_id)
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Purchase order {data.purchase_order_id} not found",
            )

        if po.status in ["CANCELLED", "RECEIVED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot receive goods for purchase order in status {po.status}",
            )

        target_warehouse_id = data.warehouse_id or po.warehouse_id
        gr_number = await generate_gr_number(self.db)

        gr = GoodsReceipt(
            gr_number=gr_number,
            purchase_order_id=po.id,
            warehouse_id=target_warehouse_id,
            status="COMPLETED",
            notes=data.notes,
            received_by=received_by,
        )
        self.db.add(gr)
        await self.db.flush()

        po_items_map = {item.id: item for item in po.items}

        for item_in in data.items:
            po_item = po_items_map.get(item_in.purchase_item_id)
            if not po_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Purchase item {item_in.purchase_item_id} does not belong to purchase order {po.id}",
                )

            gr_item = GoodsReceiptItem(
                goods_receipt_id=gr.id,
                purchase_item_id=po_item.id,
                variant_id=item_in.variant_id,
                quantity_received=item_in.quantity_received,
                unit_cost=item_in.unit_cost,
                notes=item_in.notes,
            )
            self.db.add(gr_item)

            # Update received quantity on PO item
            po_item.quantity_received += item_in.quantity_received

            # Update inventory stock and record audit movement
            await self.stock_repo.adjust_stock(
                variant_id=item_in.variant_id,
                warehouse_id=target_warehouse_id,
                delta=item_in.quantity_received,
                movement_type="PURCHASE",
                reference_type="GOODS_RECEIPT",
                reference_id=gr.id,
                note=f"Received via {gr_number} for PO {po.po_number}",
                created_by=received_by,
            )

            # Update variant cost_price if desired
            variant = await self.variant_repo.get_by_id(item_in.variant_id)
            if variant:
                variant.cost_price = item_in.unit_cost

        # Update PO status based on received items
        all_completed = True
        any_received = False
        for item in po.items:
            if item.quantity_received < item.quantity_ordered:
                all_completed = False
            if item.quantity_received > 0:
                any_received = True

        if all_completed:
            po.status = "RECEIVED"
        elif any_received:
            po.status = "PARTIAL"
        else:
            po.status = "ORDERED"

        await self.db.flush()
        return await self.gr_repo.get_by_id(gr.id)
