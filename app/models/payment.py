"""PaymentTransaction model — tracks every ABA PayWay request."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import UUIDBase

if TYPE_CHECKING:
    from app.models.sale import Sale
    from app.models.user import User


class PaymentTransaction(UUIDBase):
    """One payment attempt via ABA PayWay.

    Status lifecycle:
        PENDING -> APPROVED  (happy path)
        PENDING -> DECLINED
        PENDING -> CANCELLED (cashier hit Cancel QR)
        PENDING -> EXPIRED   (QR lifetime exceeded, never confirmed)
        APPROVED -> REFUNDED (future)
    """

    __tablename__ = "payment_transactions"

    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="ABA_PAYWAY")
    tran_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)

    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales.id", ondelete="SET NULL"), index=True
    )

    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="POS")
    # POS | ONLINE

    payment_option: Mapped[str] = mapped_column(String(30), nullable=False, default="abapay_khqr_deeplink")

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    status: Mapped[str] = mapped_column(String(15), nullable=False, default="PENDING", index=True)
    # PENDING | APPROVED | DECLINED | CANCELLED | EXPIRED | REFUNDED | FAILED

    apv: Mapped[str | None] = mapped_column(String(30))
    qr_string: Mapped[str | None] = mapped_column(Text)
    checkout_url: Mapped[str | None] = mapped_column(Text)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    request_payload: Mapped[dict | None] = mapped_column(JSONB)
    last_response: Mapped[dict | None] = mapped_column(JSONB)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    sale: Mapped[Sale | None] = relationship("Sale")
    creator: Mapped[User | None] = relationship("User")
