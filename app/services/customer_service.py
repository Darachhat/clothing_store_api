"""Customer and loyalty program service."""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, LoyaltyAccount, LoyaltyTransaction
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


def calculate_tier(points_earned: int) -> str:
    if points_earned >= 10000:
        return "PLATINUM"
    elif points_earned >= 5000:
        return "GOLD"
    elif points_earned >= 1500:
        return "SILVER"
    return "BRONZE"


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CustomerRepository(db)

    async def create_customer(self, data: CustomerCreate) -> Customer:
        code = await self.repo.next_customer_code()
        customer = Customer(
            customer_code=code,
            name=data.name,
            phone=data.phone,
            email=str(data.email) if data.email else None,
            address=data.address,
            date_of_birth=data.date_of_birth,
            notes=data.notes,
            status=data.status,
        )
        self.db.add(customer)
        await self.db.flush()

        loyalty = LoyaltyAccount(
            customer_id=customer.id,
            points_balance=0,
            total_points_earned=0,
            total_points_redeemed=0,
            tier="BRONZE",
        )
        self.db.add(loyalty)
        await self.db.commit()
        await self.db.refresh(customer)
        return await self.repo.get_with_loyalty(customer.id)  # type: ignore

    async def update_customer(self, customer_id: UUID, data: CustomerUpdate) -> Customer:
        customer = await self.repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        update_dict = data.model_dump(exclude_unset=True)
        if "email" in update_dict and update_dict["email"] is not None:
            update_dict["email"] = str(update_dict["email"])

        for k, v in update_dict.items():
            setattr(customer, k, v)

        await self.db.commit()
        await self.db.refresh(customer)
        return await self.repo.get_with_loyalty(customer.id)  # type: ignore

    async def get_customer(self, customer_id: UUID) -> Customer:
        customer = await self.repo.get_with_loyalty(customer_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        return customer

    async def adjust_loyalty_points(
        self,
        customer_id: UUID,
        points: int,
        note: str | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> LoyaltyAccount:
        customer = await self.repo.get_with_loyalty(customer_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

        account = customer.loyalty_account
        if not account:
            account = LoyaltyAccount(customer_id=customer.id)
            self.db.add(account)
            await self.db.flush()

        if points < 0 and account.points_balance + points < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient points balance ({account.points_balance})",
            )

        account.points_balance += points
        if points > 0:
            account.total_points_earned += points
            tx_type = "EARN"
        else:
            account.total_points_redeemed += abs(points)
            tx_type = "REDEEM"

        account.tier = calculate_tier(account.total_points_earned)

        tx = LoyaltyTransaction(
            account_id=account.id,
            transaction_type=tx_type,
            points=points,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
        )
        self.db.add(tx)
        await self.db.commit()
        await self.db.refresh(account)
        return account
