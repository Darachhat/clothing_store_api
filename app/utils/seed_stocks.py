"""Populate stocks and loyalty accounts for existing data."""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Warehouse
from app.models import Customer, LoyaltyAccount
from app.models import InventoryStock
from app.models import ProductVariant


async def main():
    async with AsyncSessionLocal() as db:
        wh_res = await db.execute(select(Warehouse))
        wh = wh_res.scalars().first()
        if not wh:
            print("No warehouse found!")
            return

        var_res = await db.execute(select(ProductVariant))
        variants = var_res.scalars().all()

        added_stocks = 0
        for v in variants:
            exists = await db.execute(
                select(InventoryStock).where(
                    InventoryStock.variant_id == v.id,
                    InventoryStock.warehouse_id == wh.id,
                )
            )
            if not exists.scalar_one_or_none():
                db.add(
                    InventoryStock(
                        variant_id=v.id,
                        warehouse_id=wh.id,
                        quantity=45,
                        reorder_level=10,
                    )
                )
                added_stocks += 1

        cust_res = await db.execute(select(Customer))
        customers = cust_res.scalars().all()
        added_loyalty = 0
        for c in customers:
            exists = await db.execute(
                select(LoyaltyAccount).where(LoyaltyAccount.customer_id == c.id)
            )
            if not exists.scalar_one_or_none():
                db.add(
                    LoyaltyAccount(
                        customer_id=c.id,
                        points_balance=150,
                        total_points_earned=150,
                        total_points_redeemed=0,
                        tier="BRONZE",
                    )
                )
                added_loyalty += 1

        await db.commit()
        print(f"Added {added_stocks} stock records and {added_loyalty} loyalty accounts.")


if __name__ == "__main__":
    asyncio.run(main())
