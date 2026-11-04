"""Add POS Shifts table and associate with Sales.

Revision ID: 0008_add_pos_shifts
Revises: 0007_add_pos_terminals
Create Date: 2026-11-03 16:30:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0008_add_pos_shifts"
down_revision = "0007_add_pos_terminals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- 1. Create data.pos_shifts table
        CREATE TABLE IF NOT EXISTS data.pos_shifts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            terminal_id UUID NOT NULL REFERENCES data.pos_terminals(id) ON DELETE RESTRICT,
            branch_id UUID NOT NULL REFERENCES data.branches(id) ON DELETE RESTRICT,
            cashier_id UUID NOT NULL REFERENCES data.users(id) ON DELETE RESTRICT,
            opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ,
            opening_float_usd NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            opening_float_khr NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
            closing_cash_usd NUMERIC(12, 2),
            closing_cash_khr NUMERIC(12, 2),
            expected_cash_usd NUMERIC(12, 2),
            expected_cash_khr NUMERIC(12, 2),
            status_code VARCHAR(20) NOT NULL DEFAULT 'OPEN',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS ix_pos_shifts_terminal_id ON data.pos_shifts (terminal_id);
        CREATE INDEX IF NOT EXISTS ix_pos_shifts_branch_id ON data.pos_shifts (branch_id);
        CREATE INDEX IF NOT EXISTS ix_pos_shifts_cashier_id ON data.pos_shifts (cashier_id);
        CREATE INDEX IF NOT EXISTS ix_pos_shifts_status_code ON data.pos_shifts (status_code);

        -- 2. Add shift_id column to data.sales
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'data' AND table_name = 'sales' AND column_name = 'shift_id'
            ) THEN
                ALTER TABLE data.sales 
                ADD COLUMN shift_id UUID REFERENCES data.pos_shifts(id) ON DELETE SET NULL;
            END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS ix_sales_shift_id ON data.sales (shift_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS data.ix_sales_shift_id;
        ALTER TABLE data.sales DROP COLUMN IF EXISTS shift_id;
        DROP TABLE IF EXISTS data.pos_shifts CASCADE;
        """
    )

