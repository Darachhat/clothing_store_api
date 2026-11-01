"""Add purchase.create permission and assign to ADMIN, MANAGER, and WAREHOUSE.

Revision ID: 0006_add_purchase_create_permission
Revises: 0005_schema_alignment_and_sequences
Create Date: 2026-11-01 16:05:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0006_add_purchase_create_permission"
down_revision = "0005_schema_alignment_and_sequences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (id, code, name, module, created_at, updated_at)
        SELECT gen_random_uuid(), 'purchase.create', 'Create / Approve Purchase Orders', 'purchases', NOW(), NOW()
        WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'purchase.create');

        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE p.code = 'purchase.create'
          AND r.name IN ('ADMIN', 'MANAGER', 'WAREHOUSE')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'purchase.create');

        DELETE FROM permissions WHERE code = 'purchase.create';
        """
    )

