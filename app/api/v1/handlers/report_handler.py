"""Reports API endpoints."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.inventory import InventoryMovement, InventoryStock
from app.models.misc import Expense
from app.models.product import Product, ProductVariant
from app.models.purchase import GoodsReceiptItem, PurchaseItem, PurchaseOrder
from app.models.sale import Return, Sale, SaleItem
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reports"])


def _resolve_date_range(
    start_date: date | None,
    end_date: date | None,
    from_date: date | None,
    to_date: date | None,
) -> tuple[date, date, datetime, datetime]:
    today = datetime.now(UTC).date()
    resolved_start = start_date or from_date or (today - timedelta(days=30))
    resolved_end = end_date or to_date or today
    start_dt = datetime.combine(resolved_start, datetime.min.time()).replace(tzinfo=UTC)
    end_dt = datetime.combine(resolved_end, datetime.max.time()).replace(tzinfo=UTC)
    return resolved_start, resolved_end, start_dt, end_dt


def _period_key(dt: datetime | date, group_by: str) -> str:
    d = dt.date() if isinstance(dt, datetime) else dt
    if group_by == "month":
        return d.strftime("%Y-%m")
    if group_by == "week":
        iso_year, iso_week, _ = d.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return d.isoformat()


@router.get("/dashboard")
async def dashboard(
    period: str = Query("today", pattern="^(today|yesterday|7days|last_7_days|30days|last_30_days|this_month)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("report.read")),
) -> dict:
    now = datetime.now(UTC)
    today = now.date()

    if period == "today":
        start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
        end = now
    elif period == "yesterday":
        yesterday = date.fromordinal(today.toordinal() - 1)
        start = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=UTC)
        end = datetime.combine(yesterday, datetime.max.time()).replace(tzinfo=UTC)
    elif period in ("7days", "last_7_days"):
        start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC) - timedelta(days=7)
        end = now
    elif period in ("30days", "last_30_days"):
        start = now - timedelta(days=30)
        end = now
    else:  # this_month
        start = datetime.combine(today.replace(day=1), datetime.min.time()).replace(tzinfo=UTC)
        end = now

    # Total sales and revenue
    sales_result = await db.execute(
        select(
            func.count(Sale.id).label("count"),
            func.coalesce(func.sum(Sale.total), 0).label("revenue"),
            func.coalesce(func.sum(Sale.subtotal - Sale.discount_amount), 0).label("subtotal"),
        ).where(
            and_(
                Sale.sale_status == "COMPLETED",
                Sale.created_at >= start,
                Sale.created_at <= end,
            )
        )
    )
    sales_row = sales_result.one()

    # Gross profit calculation
    profit_result = await db.execute(
        select(
            func.coalesce(
                func.sum(SaleItem.subtotal - (SaleItem.cost_price * SaleItem.quantity)), 0
            ).label("gross_profit")
        ).join(Sale, SaleItem.sale_id == Sale.id).where(
            and_(
                Sale.sale_status == "COMPLETED",
                Sale.created_at >= start,
                Sale.created_at <= end,
            )
        )
    )
    gross_profit = profit_result.scalar_one()

    # Expenses
    expense_result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            and_(
                Expense.status == "APPROVED",
                Expense.expense_date >= start.date(),
                Expense.expense_date <= end.date(),
            )
        )
    )
    total_expenses = expense_result.scalar_one()

    # Low stock count
    low_stock_result = await db.execute(
        select(func.count()).select_from(InventoryStock).where(
            InventoryStock.quantity <= InventoryStock.reorder_level
        )
    )
    low_stock_count = low_stock_result.scalar_one()

    return {
        "period": period,
        "sales_count": sales_row.count,
        "revenue": float(sales_row.revenue),
        "gross_profit": float(gross_profit),
        "expenses": float(total_expenses),
        "net_profit": float(gross_profit) - float(total_expenses),
        "low_stock_count": low_stock_count,
    }


@router.get("/sales")
async def sales_report(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    branch_id: UUID | None = None,
    cashier_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("report.read")),
) -> dict:
    from sqlalchemy.orm import selectinload

    s_date, e_date, start, end = _resolve_date_range(start_date, end_date, from_date, to_date)

    stmt = (
        select(Sale)
        .options(selectinload(Sale.items))
        .where(
            and_(
                Sale.sale_status == "COMPLETED",
                Sale.created_at >= start,
                Sale.created_at <= end,
            )
        )
        .order_by(Sale.created_at.asc())
    )
    if branch_id:
        stmt = stmt.where(Sale.branch_id == branch_id)
    if cashier_id:
        stmt = stmt.where(Sale.cashier_id == cashier_id)

    sales = list((await db.execute(stmt)).scalars().all())

    total_sales = len(sales)
    total_revenue = sum(float(s.total) for s in sales)
    total_discounts = sum(float(s.discount_amount) for s in sales)
    total_tax = sum(float(s.tax_amount) for s in sales)

    buckets: dict[str, dict] = {}
    for s in sales:
        key = _period_key(s.created_at, group_by)
        bucket = buckets.setdefault(
            key,
            {
                "period": key,
                "transaction_count": 0,
                "items_sold": 0,
                "revenue": 0.0,
                "discount_total": 0.0,
            },
        )
        bucket["transaction_count"] += 1
        bucket["items_sold"] += sum(i.quantity for i in (s.items or []))
        bucket["revenue"] = round(bucket["revenue"] + float(s.total), 2)
        bucket["discount_total"] = round(bucket["discount_total"] + float(s.discount_amount), 2)

    return {
        "start_date": str(s_date),
        "end_date": str(e_date),
        "total_sales": total_sales,
        "total_revenue": round(total_revenue, 2),
        "total_discounts": round(total_discounts, 2),
        "total_tax": round(total_tax, 2),
        "rows": list(buckets.values()),
    }


@router.get("/profit")
async def profit_report(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("report.read")),
) -> dict:
    from sqlalchemy.orm import selectinload

    s_date, e_date, start, end = _resolve_date_range(start_date, end_date, from_date, to_date)

    sales_res = await db.execute(
        select(Sale)
        .options(selectinload(Sale.items))
        .where(and_(Sale.sale_status == "COMPLETED", Sale.created_at.between(start, end)))
        .order_by(Sale.created_at.asc())
    )
    sales = list(sales_res.scalars().all())

    expenses_res = await db.execute(
        select(Expense)
        .where(and_(Expense.status == "APPROVED", Expense.expense_date.between(s_date, e_date)))
        .order_by(Expense.expense_date.asc())
    )
    expense_list = list(expenses_res.scalars().all())

    returns_res = await db.execute(
        select(func.coalesce(func.sum(Return.total_refund), 0)).where(
            and_(Return.status == "COMPLETED", Return.created_at.between(start, end))
        )
    )
    total_refunds = float(returns_res.scalar_one())

    revenue = sum(float(s.total) for s in sales)
    discounts = sum(float(s.discount_amount) for s in sales)
    cogs = sum(
        float(item.cost_price) * item.quantity
        for s in sales
        for item in (s.items or [])
    )
    expenses = sum(float(e.amount) for e in expense_list)

    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses
    margin = round((net_profit / revenue) * 100, 1) if revenue > 0 else 0.0

    buckets: dict[str, dict] = {}
    for s in sales:
        key = _period_key(s.created_at, group_by)
        b = buckets.setdefault(key, {"period": key, "revenue": 0.0, "cogs": 0.0, "expenses": 0.0, "net_profit": 0.0})
        b["revenue"] = round(b["revenue"] + float(s.total), 2)
        b["cogs"] = round(b["cogs"] + sum(float(i.cost_price) * i.quantity for i in (s.items or [])), 2)

    for e in expense_list:
        key = _period_key(e.expense_date, group_by)
        b = buckets.setdefault(key, {"period": key, "revenue": 0.0, "cogs": 0.0, "expenses": 0.0, "net_profit": 0.0})
        b["expenses"] = round(b["expenses"] + float(e.amount), 2)

    rows = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        b["net_profit"] = round(b["revenue"] - b["cogs"] - b["expenses"], 2)
        rows.append(b)

    return {
        "start_date": str(s_date),
        "end_date": str(e_date),
        "revenue": round(revenue, 2),
        "cost_of_goods_sold": round(cogs, 2),
        "gross_profit": round(gross_profit, 2),
        "total_expenses": round(expenses, 2),
        "expenses": round(expenses, 2),
        "discounts": round(discounts, 2),
        "refunds": round(total_refunds, 2),
        "net_profit": round(net_profit, 2),
        "margin": f"{margin:.1f}",
        "rows": rows,
    }


@router.get("/inventory")
async def inventory_report(
    warehouse_id: UUID | None = None,
    low_stock_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("report.read")),
) -> dict:
    """Current inventory report: stock levels, valuation, low-stock items."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(InventoryStock)
        .options(
            selectinload(InventoryStock.variant).selectinload(ProductVariant.product),
            selectinload(InventoryStock.warehouse),
        )
    )
    if warehouse_id:
        stmt = stmt.where(InventoryStock.warehouse_id == warehouse_id)
    if low_stock_only:
        stmt = stmt.where(InventoryStock.quantity <= InventoryStock.reorder_level)

    result = await db.execute(stmt)
    stocks = result.scalars().all()

    total_items = len(stocks)
    total_quantity = sum(s.quantity for s in stocks)
    low_stock_count = sum(1 for s in stocks if s.quantity <= s.reorder_level)
    out_of_stock_count = sum(1 for s in stocks if s.quantity == 0)

    # Valuation: quantity * cost_price per variant
    total_cost_value = sum(
        s.quantity * float(s.variant.cost_price) for s in stocks if s.variant
    )
    total_retail_value = sum(
        s.quantity * float(s.variant.selling_price) for s in stocks if s.variant
    )

    items = [
        {
            "variant_id": str(s.variant_id),
            "sku": s.variant.sku if s.variant else None,
            "product_name": s.variant.product.name if s.variant and s.variant.product else None,
            "warehouse": s.warehouse.name if s.warehouse else None,
            "quantity": s.quantity,
            "reorder_level": s.reorder_level,
            "is_low_stock": s.quantity <= s.reorder_level,
            "cost_price": float(s.variant.cost_price) if s.variant else 0,
            "selling_price": float(s.variant.selling_price) if s.variant else 0,
            "cost_value": s.quantity * float(s.variant.cost_price) if s.variant else 0,
        }
        for s in stocks
    ]

    return {
        "total_sku_count": total_items,
        "total_quantity": total_quantity,
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "total_cost_value": total_cost_value,
        "total_retail_value": total_retail_value,
        "items": items,
    }


@router.get("/purchases")
async def purchases_report(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    group_by: str = Query("day", pattern="^(day|week|month)$"),
    supplier_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("report.read")),
) -> dict:
    """Purchase report: orders, items received, cost summary."""
    from sqlalchemy.orm import selectinload

    s_date, e_date, start, end = _resolve_date_range(start_date, end_date, from_date, to_date)

    stmt = (
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.items))
        .where(
            and_(
                PurchaseOrder.created_at >= start,
                PurchaseOrder.created_at <= end,
            )
        )
        .order_by(PurchaseOrder.created_at.asc())
    )
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)

    orders = list((await db.execute(stmt)).scalars().all())
    order_count = len(orders)
    total_cost = sum(float(o.total) for o in orders)
    total_tax = sum(float(o.tax_amount) for o in orders)

    status_counts: dict[str, int] = {}
    buckets: dict[str, dict] = {}
    for o in orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1
        key = _period_key(o.created_at, group_by)
        b = buckets.setdefault(
            key,
            {
                "period": key,
                "order_count": 0,
                "items_received": 0,
                "total_cost": 0.0,
            },
        )
        b["order_count"] += 1
        b["items_received"] += sum(i.quantity_received for i in (o.items or []))
        b["total_cost"] = round(b["total_cost"] + float(o.total), 2)

    # Total items received via goods receipts in period
    received_stmt = (
        select(func.coalesce(func.sum(GoodsReceiptItem.quantity_received), 0))
        .join(PurchaseItem, GoodsReceiptItem.purchase_item_id == PurchaseItem.id)
        .join(PurchaseOrder, PurchaseItem.purchase_order_id == PurchaseOrder.id)
        .where(
            and_(
                PurchaseOrder.created_at >= start,
                PurchaseOrder.created_at <= end,
            )
        )
    )
    total_received = (await db.execute(received_stmt)).scalar_one()

    return {
        "start_date": str(s_date),
        "end_date": str(e_date),
        "order_count": order_count,
        "total_cost": round(total_cost, 2),
        "total_tax": round(total_tax, 2),
        "total_items_received": int(total_received),
        "orders_by_status": status_counts,
        "rows": list(buckets.values()),
    }
