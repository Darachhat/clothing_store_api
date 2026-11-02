"""Customer and loyalty program service."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enum.common_enum import (
    COMMON_STATUS_ENUM
    , LOYALTY_TIER_ENUM
    , LOYALTY_TRANSACTION_TYPE_ENUM
    , REFERENCE_TYPE_ENUM
    , STATUS_CODE_ENUM
)
from app.core.exceptions import BAD_REQUEST_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.logging import get_logger
from app.models import Customer, LoyaltyAccount, LoyaltyTransaction
from app.repositories.customer_repository import CustomerRepository
from app.schemas.customer_schema import (
    CUSTOMER_CREATE_SCHEMA
    , CUSTOMER_LIST_OUT_SCHEMA
    , CUSTOMER_RESPONSE_SCHEMA
    , CUSTOMER_UPDATE_SCHEMA
    , LOYALTY_ACCOUNT_RESPONSE_SCHEMA
    , LOYALTY_ADJUST_REQUEST_SCHEMA
    , LOYALTY_AWARD_REQUEST_SCHEMA
    , LOYALTY_CLAWBACK_REQUEST_SCHEMA
)

logger = get_logger(__name__)


def calculate_tier(points_earned: int) -> str:
    if points_earned >= 10000:
        return LOYALTY_TIER_ENUM.PLATINUM.value
    elif points_earned >= 5000:
        return LOYALTY_TIER_ENUM.GOLD.value
    elif points_earned >= 1500:
        return LOYALTY_TIER_ENUM.SILVER.value
    return LOYALTY_TIER_ENUM.BRONZE.value


class CUSTOMER_SERVICE:
    """Service handling Customer profile lifecycle and Loyalty point accounting."""

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = CustomerRepository(db)

    async def create_customer(self, data: CUSTOMER_CREATE_SCHEMA) -> Customer:
        code = await self.repo.next_customer_code()
        customer = Customer(
            customer_code = code
            , name        = data.name
            , phone       = data.phone
            , email       = str(data.email) if data.email else None
            , address     = data.address
            , date_of_birth = data.date_of_birth
            , notes       = data.notes
            , status      = data.status or COMMON_STATUS_ENUM.ACTIVE.value
        )
        self.db.add(customer)
        await self.db.flush()

        loyalty = LoyaltyAccount(
            customer_id           = customer.id
            , points_balance       = 0
            , total_points_earned  = 0
            , total_points_redeemed = 0
            , tier                 = LOYALTY_TIER_ENUM.BRONZE.value
        )
        self.db.add(loyalty)
        await self.db.commit()
        await self.db.refresh(customer)
        return await self.repo.get_with_loyalty(customer.id)  # type: ignore

    async def update_customer(self, customer_id: UUID, data: CUSTOMER_UPDATE_SCHEMA) -> Customer:
        customer = await self.repo.get_by_id(customer_id)
        if not customer:
            raise NOT_FOUND_EXCEPTION("Customer not found")

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
            raise NOT_FOUND_EXCEPTION("Customer not found")
        return customer

    async def adjust_loyalty_points(
        self
        , customer_id    : UUID
        , points         : int
        , note           : Optional[str] = None
        , reference_type : Optional[str] = None
        , reference_id   : Optional[UUID] = None
    ) -> LoyaltyAccount:
        customer = await self.repo.get_with_loyalty(customer_id)
        if not customer:
            raise NOT_FOUND_EXCEPTION("Customer not found")

        account = customer.loyalty_account
        if not account:
            account = LoyaltyAccount(customer_id=customer.id)
            customer.loyalty_account = account
            self.db.add(account)
            await self.db.flush()

        if points < 0 and account.points_balance + points < 0:
            raise BAD_REQUEST_EXCEPTION(f"Insufficient points balance ({account.points_balance})")

        account.points_balance += points
        if points > 0:
            account.total_points_earned += points
            tx_type = LOYALTY_TRANSACTION_TYPE_ENUM.EARN.value
        else:
            account.total_points_redeemed += abs(points)
            tx_type = LOYALTY_TRANSACTION_TYPE_ENUM.REDEEM.value

        account.tier = calculate_tier(account.total_points_earned)

        tx = LoyaltyTransaction(
            account_id       = account.id
            , transaction_type = tx_type
            , points         = points
            , reference_type = reference_type or REFERENCE_TYPE_ENUM.MANUAL.value
            , reference_id   = reference_id
            , note           = note
        )
        self.db.add(tx)
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def award_sale_points(
        self
        , customer_id    : UUID
        , points         : int
        , sale_id        : UUID
        , invoice_number : str
    ) -> Optional[LoyaltyAccount]:
        if points <= 0:
            return None
        customer = await self.repo.get_with_loyalty(customer_id)
        if not customer:
            return None
        account = customer.loyalty_account
        if not account:
            account = LoyaltyAccount(customer_id=customer.id)
            customer.loyalty_account = account
            self.db.add(account)
            await self.db.flush()

        account.points_balance += points
        account.total_points_earned += points
        account.tier = calculate_tier(account.total_points_earned)

        tx = LoyaltyTransaction(
            account_id       = account.id
            , transaction_type = LOYALTY_TRANSACTION_TYPE_ENUM.EARN.value
            , points         = points
            , reference_type = REFERENCE_TYPE_ENUM.SALE.value
            , reference_id   = sale_id
            , note           = f"Points earned from sale {invoice_number}"
        )
        self.db.add(tx)
        await self.db.flush()
        return account

    async def clawback_points(
        self
        , customer_id    : UUID
        , points         : int
        , reference_type : str
        , reference_id   : UUID
        , note           : str
    ) -> Optional[LoyaltyAccount]:
        if points <= 0:
            return None
        customer = await self.repo.get_with_loyalty(customer_id)
        if not customer:
            return None
        account = customer.loyalty_account
        if not account:
            account = LoyaltyAccount(customer_id=customer.id)
            customer.loyalty_account = account
            self.db.add(account)
            await self.db.flush()

        account.points_balance = max(0, account.points_balance - points)
        account.total_points_earned = max(0, account.total_points_earned - points)
        account.tier = calculate_tier(account.total_points_earned)

        tx = LoyaltyTransaction(
            account_id       = account.id
            , transaction_type = LOYALTY_TRANSACTION_TYPE_ENUM.ADJUST.value
            , points         = -points
            , reference_type = reference_type
            , reference_id   = reference_id
            , note           = note
        )
        self.db.add(tx)
        await self.db.flush()
        return account

    async def adjust_loyalty_points_payload(
        self
        , customer_id : UUID
        , payload     : LOYALTY_ADJUST_REQUEST_SCHEMA
    ) -> LoyaltyAccount:
        """Adjust customer loyalty points using structured LOYALTY_ADJUST_REQUEST_SCHEMA."""
        return await self.adjust_loyalty_points(
            customer_id    = customer_id
            , points         = payload.points
            , note           = payload.note
            , reference_type = payload.reference_type
            , reference_id   = payload.reference_id
        )

    async def award_sale_points_payload(
        self
        , payload : LOYALTY_AWARD_REQUEST_SCHEMA
    ) -> Optional[LoyaltyAccount]:
        """Award loyalty points from sale using structured LOYALTY_AWARD_REQUEST_SCHEMA."""
        return await self.award_sale_points(
            customer_id    = payload.customer_id
            , points         = payload.points
            , sale_id        = payload.sale_id
            , invoice_number = payload.invoice_number
        )

    async def clawback_points_payload(
        self
        , payload : LOYALTY_CLAWBACK_REQUEST_SCHEMA
    ) -> Optional[LoyaltyAccount]:
        """Clawback loyalty points using structured LOYALTY_CLAWBACK_REQUEST_SCHEMA."""
        return await self.clawback_points(
            customer_id    = payload.customer_id
            , points         = payload.points
            , reference_type = payload.reference_type
            , reference_id   = payload.reference_id
            , note           = payload.note
        )
    async def award_sale_points_payload(
        self
        , payload : LOYALTY_AWARD_REQUEST_SCHEMA
    ) -> Optional[LoyaltyAccount]:
        """Award loyalty points from sale using structured LOYALTY_AWARD_REQUEST_SCHEMA."""
        return await self.award_sale_points(
            customer_id    = payload.customer_id
            , points         = payload.points
            , sale_id        = payload.sale_id
            , invoice_number = payload.invoice_number
        )

    async def clawback_points_payload(
        self
        , payload : LOYALTY_CLAWBACK_REQUEST_SCHEMA
    ) -> Optional[LoyaltyAccount]:
        """Clawback loyalty points using structured LOYALTY_CLAWBACK_REQUEST_SCHEMA."""
        return await self.clawback_points(
            customer_id    = payload.customer_id
            , points         = payload.points
            , reference_type = payload.reference_type
            , reference_id   = payload.reference_id
            , note           = payload.note
        )


CustomerService = CUSTOMER_SERVICE