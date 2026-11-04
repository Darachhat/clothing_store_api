"""Add system_settings table for server-side store & tax configuration.

Revision ID: 0009_add_system_settings
Revises: 0008_add_pos_shifts
Create Date: 2026-11-03 16:45:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0009_add_system_settings"
down_revision = "0008_add_pos_shifts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS base_data.system_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category VARCHAR(50) NOT NULL,
            key VARCHAR(100) NOT NULL,
            value JSONB NOT NULL DEFAULT '{}'::jsonb,
            description VARCHAR(255),
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_setting_category_key UNIQUE (category, key)
        );

        CREATE INDEX IF NOT EXISTS ix_system_settings_category ON base_data.system_settings (category);

        -- Seed initial default store and tax settings
        INSERT INTO base_data.system_settings (id, category, key, value, description)
        VALUES 
        (
            gen_random_uuid(),
            'store',
            'store_info',
            '{"name": "Antigravity Clothing Store", "currency": "USD", "phone": "+855 23 888 999", "email": "store@antigravity.kh", "address": "Phnom Penh, Cambodia", "receipt_footer": "Thank you for shopping with us! Please come again."}'::jsonb,
            'Store general profile and receipt message'
        ),
        (
            gen_random_uuid(),
            'tax',
            'tax_settings',
            '{"default_tax_rate": 5, "tax_inclusive": false, "rounding": "round"}'::jsonb,
            'Tax and VAT configuration'
        )
        ON CONFLICT (category, key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS base_data.system_settings CASCADE;")

