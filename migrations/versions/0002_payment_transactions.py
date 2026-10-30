"""Add payment_transactions table.

Revision ID: 0002_payment_transactions
Revises: 0001_initial_schema
Create Date: 2026-10-23 00:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_payment_transactions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False, server_default="ABA_PAYWAY"),
        sa.Column("tran_id", sa.String(20), nullable=False),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(10), nullable=False, server_default="POS"),
        sa.Column("payment_option", sa.String(30), nullable=False, server_default="abapay_khqr_deeplink"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(15), nullable=False, server_default="PENDING"),
        sa.Column("apv", sa.String(30), nullable=True),
        sa.Column("qr_string", sa.Text, nullable=True),
        sa.Column("checkout_url", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_payment_transactions_tran_id", "payment_transactions", ["tran_id"], unique=True)
    op.create_index("ix_payment_transactions_sale_id", "payment_transactions", ["sale_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_sale_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_tran_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
