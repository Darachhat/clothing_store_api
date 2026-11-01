"""Sale service: create sale, process payment, returns."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Return, ReturnItem, ReturnPayment, Sale, SaleItem, SalePayment
from app.repositories.inventory_repository import InventoryStockRepository
from app.repositories.product_repository import ProductVariantRepository
from app.utils.generators import generate_invoice_number, generate_return_number


class SaleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.variant_repo = ProductVariantRepository(db)
        self.stock_repo = InventoryStockRepository(db)

    async def create_sale(
        self,
        branch_id: UUID | None,
        warehouse_id: UUID | None,
        cashier_id: UUID,
        items_data: list[dict],
        customer_id: UUID | None = None,
        discount_amount: Decimal = Decimal("0"),
        tax_amount: Decimal = Decimal("0"),
        notes: str | None = None,
        promotion_id: UUID | None = None,
    ) -> Sale:
        """Create a sale and reduce stock atomically."""
        from sqlalchemy import select
        from app.models import Branch, Warehouse

        if not branch_id or not warehouse_id:
            if not branch_id:
                branch = (await self.db.execute(select(Branch).where(Branch.status == "ACTIVE").order_by(Branch.created_at.asc()).limit(1))).scalar_one_or_none()
                if not branch:
                    branch = (await self.db.execute(select(Branch).limit(1))).scalar_one_or_none()
                if branch:
                    branch_id = branch.id

            if not warehouse_id and branch_id:
                wh = (
                    await self.db.execute(
                        select(Warehouse)
                        .where(Warehouse.branch_id == branch_id, Warehouse.status == "ACTIVE")
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

        invoice_number = await generate_invoice_number(self.db)

        # Calculate totals
        subtotal = Decimal("0")
        sale_items = []

        for item_data in items_data:
            variant = await self.variant_repo.get_by_id(item_data["variant_id"])
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant {item_data['variant_id']} not found",
                )

            qty = item_data["quantity"]
            if qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Quantity must be greater than zero",
                )
            # Price is always taken from the catalog; client-supplied unit_price is ignored
            # so a modified client cannot sell below the real price.
            unit_price = variant.selling_price
            gross = unit_price * qty
            item_discount = item_data.get("discount_amount")
            if item_discount is None:
                item_discount = Decimal("0")
            if item_discount < 0 or item_discount > gross:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid line discount",
                )
            item_subtotal = gross - item_discount
            subtotal += item_subtotal

            sale_items.append(
                {
                    "variant_id": variant.id,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "cost_price": variant.cost_price,
                    "discount_amount": item_discount,
                    "subtotal": item_subtotal,
                }
            )

        if discount_amount < 0 or discount_amount > subtotal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid order discount",
            )
        if tax_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tax amount",
            )
        total = subtotal - discount_amount + tax_amount

        sale = Sale(
            invoice_number=invoice_number,
            customer_id=customer_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            payment_status="PENDING",
            sale_status="DRAFT",
            notes=notes,
            cashier_id=cashier_id,
            promotion_id=promotion_id,
        )
        self.db.add(sale)
        await self.db.flush()

        for item_data in sale_items:
            si = SaleItem(sale=sale, **item_data)
            self.db.add(si)

        await self.db.flush()
        await self.db.refresh(sale, ["items"])
        return sale

    async def complete_sale(
        self, sale: Sale, payments: list[dict]
    ) -> Sale:
        """Mark sale complete, collect payments, decrement inventory."""
        if sale.sale_status != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sale already in status: {sale.sale_status}",
            )

        total_paid = sum(Decimal(str(p["amount"])) for p in payments)

        # Create payment records
        for p in payments:
            sp = SalePayment(
                sale_id=sale.id,
                payment_method=p["payment_method"],
                amount=Decimal(str(p["amount"])),
                reference_number=p.get("reference_number"),
            )
            self.db.add(sp)

        # Decrease stock for each item
        for item in sale.items:
            await self.stock_repo.adjust_stock(
                variant_id=item.variant_id,
                warehouse_id=sale.warehouse_id,
                delta=-item.quantity,
                movement_type="SALE",
                reference_type="sale",
                reference_id=sale.id,
                created_by=sale.cashier_id,
            )

        sale.sale_status = "COMPLETED"
        if total_paid >= sale.total:
            sale.payment_status = "PAID"
        else:
            sale.payment_status = "PARTIAL"

        # Award loyalty points if customer is linked and sale is paid
        if sale.customer_id and sale.payment_status == "PAID":
            from app.services.customer_service import CustomerService

            cust_svc = CustomerService(self.db)
            points_to_earn = int(sale.total)
            if points_to_earn > 0:
                await cust_svc.award_sale_points(
                    customer_id=sale.customer_id,
                    points=points_to_earn,
                    sale_id=sale.id,
                    invoice_number=sale.invoice_number,
                )

        from app.services.audit_service import AuditService

        await AuditService.record(
            self.db,
            action="SALE_COMPLETED",
            entity_type="sale",
            entity_id=sale.id,
            user_id=sale.cashier_id,
            new_data={
                "invoice_number": sale.invoice_number,
                "total": str(sale.total),
                "payment_status": sale.payment_status,
            },
        )
        await self.db.flush()
        return sale

    async def cancel_sale(self, sale: Sale, cancelled_by: UUID) -> Sale:
        if sale.sale_status not in ("DRAFT", "COMPLETED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel sale in status: {sale.sale_status}",
            )

        # If completed, restore stock
        if sale.sale_status == "COMPLETED":
            for item in sale.items:
                await self.stock_repo.adjust_stock(
                    variant_id=item.variant_id,
                    warehouse_id=sale.warehouse_id,
                    delta=item.quantity,
                    movement_type="RETURN",
                    reference_type="sale_cancel",
                    reference_id=sale.id,
                    note="Sale cancelled",
                    created_by=cancelled_by,
                )

        prev_status = sale.sale_status
        sale.sale_status = "CANCELLED"

        if prev_status == "COMPLETED" and sale.customer_id:
            from app.services.customer_service import CustomerService

            cust_svc = CustomerService(self.db)
            points_to_claw = int(sale.total)
            if points_to_claw > 0:
                await cust_svc.clawback_points(
                    customer_id=sale.customer_id,
                    points=points_to_claw,
                    reference_type="sale_cancel",
                    reference_id=sale.id,
                    note=f"Points clawback from cancelled sale {sale.invoice_number}",
                )

        from app.services.audit_service import AuditService

        await AuditService.record(
            self.db,
            action="SALE_CANCELLED",
            entity_type="sale",
            entity_id=sale.id,
            user_id=cancelled_by,
            old_data={"sale_status": prev_status},
            new_data={"sale_status": "CANCELLED", "invoice_number": sale.invoice_number},
        )
        await self.db.flush()
        return sale

    async def process_return(
        self,
        original_sale: Sale,
        return_items_data: list[dict],
        refund_payments: list[dict],
        return_type: str,
        reason: str | None,
        processed_by: UUID,
    ) -> Return:
        """Process a return/refund with inventory restoration."""
        from sqlalchemy import func, select

        if original_sale.sale_status not in ("COMPLETED", "RETURNED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot return a sale in status: {original_sale.sale_status}",
            )

        return_number = await generate_return_number(self.db)

        # Quantity already returned per sale item (completed returns only)
        returned_rows = await self.db.execute(
            select(ReturnItem.sale_item_id, func.coalesce(func.sum(ReturnItem.quantity), 0))
            .join(Return, ReturnItem.return_id == Return.id)
            .where(
                Return.original_sale_id == original_sale.id,
                Return.status == "COMPLETED",
            )
            .group_by(ReturnItem.sale_item_id)
        )
        already_returned = {row[0]: int(row[1]) for row in returned_rows.all()}

        # Validate items and compute total_refund from the actual sale item prices
        sale_item_map = {item.id: item for item in original_sale.items}
        validated: list[dict] = []
        total_refund = Decimal("0")
        requested: dict = {}
        for item_data in return_items_data:
            sale_item_id = item_data["sale_item_id"]
            sale_item = sale_item_map.get(sale_item_id)
            if not sale_item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sale item {sale_item_id} not found in original sale",
                )
            qty = item_data["quantity"]
            if qty <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Return quantity must be greater than zero",
                )
            requested[sale_item_id] = requested.get(sale_item_id, 0) + qty
            if requested[sale_item_id] + already_returned.get(sale_item_id, 0) > sale_item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Return quantity exceeds quantity sold for item {sale_item_id}",
                )
            total_refund += sale_item.unit_price * qty
            validated.append({"sale_item": sale_item, "quantity": qty})

        ret = Return(
            return_number=return_number,
            original_sale_id=original_sale.id,
            customer_id=original_sale.customer_id,
            branch_id=original_sale.branch_id,
            return_type=return_type,
            reason=reason,
            total_refund=total_refund,
            status="PENDING",
            processed_by=processed_by,
        )
        self.db.add(ret)
        await self.db.flush()

        for item_d in validated:
            sale_item = item_d["sale_item"]
            qty = item_d["quantity"]
            ri = ReturnItem(
                return_id=ret.id,
                sale_item_id=sale_item.id,
                variant_id=sale_item.variant_id,
                quantity=qty,
                unit_price=sale_item.unit_price,
                subtotal=sale_item.unit_price * qty,
            )
            self.db.add(ri)

            # Restore inventory
            await self.stock_repo.adjust_stock(
                variant_id=sale_item.variant_id,
                warehouse_id=original_sale.warehouse_id,
                delta=qty,
                movement_type="RETURN",
                reference_type="return",
                reference_id=ret.id,
                created_by=processed_by,
            )

        # Create refund payments
        for rp in refund_payments:
            rp_obj = ReturnPayment(
                return_id=ret.id,
                payment_method=rp["payment_method"],
                amount=Decimal(str(rp["amount"])),
            )
            self.db.add(rp_obj)

        ret.status = "COMPLETED"
        # Fully refunded only when every sold unit has been returned
        for sid, q in requested.items():
            already_returned[sid] = already_returned.get(sid, 0) + q
        fully_returned = all(
            already_returned.get(i.id, 0) >= i.quantity for i in original_sale.items
        )
        if fully_returned:
            original_sale.payment_status = "REFUNDED"
            original_sale.sale_status = "RETURNED"
        else:
            original_sale.payment_status = "PARTIALLY_REFUNDED"

        if original_sale.customer_id and total_refund > Decimal("0"):
            from app.services.customer_service import CustomerService

            cust_svc = CustomerService(self.db)
            points_to_claw = int(total_refund)
            if points_to_claw > 0:
                await cust_svc.clawback_points(
                    customer_id=original_sale.customer_id,
                    points=points_to_claw,
                    reference_type="sale_return",
                    reference_id=ret.id,
                    note=f"Points clawback from return {ret.return_number} of sale {original_sale.invoice_number}",
                )

        from app.services.audit_service import AuditService

        await AuditService.record(
            self.db,
            action="SALE_RETURN_PROCESSED",
            entity_type="return",
            entity_id=ret.id,
            user_id=processed_by,
            new_data={
                "return_number": ret.return_number,
                "original_sale_id": str(original_sale.id),
                "return_type": return_type,
                "total_refund": str(total_refund),
            },
        )
        await self.db.flush()
        return ret
