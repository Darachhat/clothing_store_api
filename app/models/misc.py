"""Expense, ExpenseCategory, Promotion, AuditLog, LabelTemplate models."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDBase


class ExpenseCategory(UUIDBase):
    __tablename__ = "expense_categories"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # RENT | SALARY | ELECTRICITY | INTERNET | DELIVERY | MARKETING | MAINTENANCE | OTHER
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Expense(UUIDBase):
    __tablename__ = "expenses"

    expense_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expense_categories.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    receipt_url: Mapped[str | None] = mapped_column(String(500))
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    category: Mapped[ExpenseCategory] = relationship("ExpenseCategory")


class Promotion(UUIDBase):
    __tablename__ = "promotions"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    # PERCENTAGE | FIXED | PRODUCT | CATEGORY | BUY_X_GET_Y | COUPON
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    code: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)  # coupon code
    min_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    max_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applies_to: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)
    # ALL | CATEGORY | PRODUCT
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class AuditLog(Base):
    """Append-only audit log - never update, never delete."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    old_data: Mapped[dict | None] = mapped_column(JSONB)
    new_data: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LabelTemplate(UUIDBase):
    __tablename__ = "label_templates"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    paper_size: Mapped[str] = mapped_column(String(20), nullable=False, default="A4")
    # A4 | A5 | CUSTOM_58mm | CUSTOM_80mm
    width_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_mm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    template_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class NotificationSetting(UUIDBase):
    __tablename__ = "notification_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
