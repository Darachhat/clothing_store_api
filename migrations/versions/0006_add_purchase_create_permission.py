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
        INSERT INTO base_data.permissions (id, code, name, module, status_code)
        SELECT gen_random_uuid(), 'purchase.create', 'Create / Approve Purchase Orders', 'purchases', 'ACTIVE'
        WHERE NOT EXISTS (SELECT 1 FROM base_data.permissions WHERE code = 'purchase.create');

        INSERT INTO base_data.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM base_data.roles r
        CROSS JOIN base_data.permissions p
        WHERE p.code = 'purchase.create'
          AND r.name IN ('ADMIN', 'MANAGER', 'WAREHOUSE')
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM base_data.role_permissions
        WHERE permission_id IN (SELECT id FROM base_data.permissions WHERE code = 'purchase.create');

        DELETE FROM base_data.permissions WHERE code = 'purchase.create';
        """
    )

