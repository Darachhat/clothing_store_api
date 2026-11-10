"""Add login_url to auth.telegram_bot (portal URL used by the bot's seamless-login button).

Revision ID: 0012_telegram_bot_login_url
Revises: 0011_seed_payway_and_telegram_config
Create Date: 2026-11-10 20:45:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision      = "0012_telegram_bot_login_url"
down_revision = "0011_seed_payway_and_telegram_config"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.add_column(
        "telegram_bot",
        sa.Column("login_url", sa.String(length=500), nullable=True),
        schema="auth",
    )
    # Preserve existing behaviour for the seeded bot.
    op.execute("""
        UPDATE auth.telegram_bot
        SET login_url = 'https://admin.kimvannak.store/login'
        WHERE code = 'clothing_store_bot' AND login_url IS NULL
    """)


def downgrade() -> None:
    op.drop_column("telegram_bot", "login_url", schema="auth")

