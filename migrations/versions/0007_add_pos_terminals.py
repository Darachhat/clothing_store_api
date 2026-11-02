"""Add POS Terminals table and associate with Sales.

Revision ID: 0007_add_pos_terminals
Revises: 0006_add_purchase_create_permission
Create Date: 2026-11-02 21:05:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0007_add_pos_terminals"
down_revision = "0006_add_purchase_create_permission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        -- 1. Create data.pos_terminals table
        CREATE TABLE IF NOT EXISTS data.pos_terminals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id UUID NOT NULL REFERENCES data.branches(id) ON DELETE RESTRICT,
            warehouse_id UUID NOT NULL REFERENCES data.warehouses(id) ON DELETE RESTRICT,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            status_code VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            notes TEXT,
            last_active_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_branch_terminal_code UNIQUE (branch_id, code)
        );

        CREATE INDEX IF NOT EXISTS ix_pos_terminals_branch_id ON data.pos_terminals (branch_id);
        CREATE INDEX IF NOT EXISTS ix_pos_terminals_warehouse_id ON data.pos_terminals (warehouse_id);

        -- 2. Add terminal_id column to data.sales
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'data' AND table_name = 'sales' AND column_name = 'terminal_id'
            ) THEN
                ALTER TABLE data.sales 
                ADD COLUMN terminal_id UUID REFERENCES data.pos_terminals(id) ON DELETE SET NULL;
            END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS ix_sales_terminal_id ON data.sales (terminal_id);

        -- 3. Seed default POS-01 terminal for existing default branch & warehouse
        INSERT INTO data.pos_terminals (id, branch_id, warehouse_id, code, name, status_code, notes, created_at, updated_at)
        SELECT 
            gen_random_uuid(),
            b.id,
            w.id,
            'POS-01',
            'Main Register 1',
            'ACTIVE',
            'Primary checkout terminal',
            NOW(),
            NOW()
        FROM data.branches b
        JOIN data.warehouses w ON w.branch_id = b.id AND w.is_default = true
        WHERE NOT EXISTS (
            SELECT 1 FROM data.pos_terminals pt WHERE pt.branch_id = b.id AND pt.code = 'POS-01'
        )
        LIMIT 1;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS data.ix_sales_terminal_id;
        ALTER TABLE data.sales DROP COLUMN IF EXISTS terminal_id;
        DROP TABLE IF EXISTS data.pos_terminals CASCADE;
        """
    )

