"""Customer and Loyalty models."""
from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.sale import Sale


class Customer(UUIDBase):
    __tablename__ = "customers"

    customer_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    # ACTIVE | INACTIVE | BLACKLISTED

    sales: Mapped[list[Sale]] = relationship("Sale", back_populates="customer")
    loyalty_account: Mapped[LoyaltyAccount | None] = relationship(
        "LoyaltyAccount", back_populates="customer", uselist=False
    )


class LoyaltyAccount(UUIDBase):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (UniqueConstraint("customer_id", name="uq_loyalty_customer"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    points_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_earned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_redeemed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="BRONZE", nullable=False)
    # BRONZE | SILVER | GOLD | PLATINUM

    customer: Mapped[Customer] = relationship("Customer", back_populates="loyalty_account")
    transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        "LoyaltyTransaction", back_populates="account", cascade="all, delete-orphan"
    )


class LoyaltyTransaction(UUIDBase):
    __tablename__ = "loyalty_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loyalty_accounts.id", ondelete="CASCADE"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # EARN | REDEEM | EXPIRE | ADJUST
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    note: Mapped[str | None] = mapped_column(Text)

    account: Mapped[LoyaltyAccount] = relationship("LoyaltyAccount", back_populates="transactions")
