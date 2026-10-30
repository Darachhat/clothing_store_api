"""Align loyalty tables with the ORM models.

Revision ID: 0004_loyalty_model_alignment
Revises: 0003_template_core_schemas
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_loyalty_model_alignment"
down_revision = "0003_template_core_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # lifetime_points -> total_points_earned (same meaning, model name)
    op.alter_column("loyalty_accounts", "lifetime_points", new_column_name="total_points_earned")
    op.add_column(
        "loyalty_accounts",
        sa.Column("total_points_redeemed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "loyalty_accounts",
        sa.Column("tier", sa.String(20), nullable=False, server_default="BRONZE"),
    )
    # type -> transaction_type
    op.alter_column("loyalty_transactions", "type", new_column_name="transaction_type")


def downgrade() -> None:
    op.alter_column("loyalty_transactions", "transaction_type", new_column_name="type")
    op.drop_column("loyalty_accounts", "tier")
    op.drop_column("loyalty_accounts", "total_points_redeemed")
    op.alter_column("loyalty_accounts", "total_points_earned", new_column_name="lifetime_points")

