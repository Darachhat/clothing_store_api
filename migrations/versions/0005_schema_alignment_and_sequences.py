"""Create catalog_versions table, business sequences, and missing customer indexes.

Revision ID: 0005_schema_alignment_and_sequences
Revises: 0004_loyalty_model_alignment
Create Date: 2026-11-01 00:15:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0005_schema_alignment_and_sequences"
down_revision = "0004_loyalty_model_alignment"
branch_labels = None
depends_on = None

SEQUENCES = [
    "qr_reference_seq",
    "invoice_number_seq",
    "po_number_seq",
    "gr_number_seq",
    "transfer_number_seq",
    "return_number_seq",
    "expense_number_seq",
    "customer_code_seq",
    "supplier_code_seq",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_versions (
            id INTEGER PRIMARY KEY DEFAULT 1,
            version BIGINT NOT NULL DEFAULT 1,
            inventory_version BIGINT NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        INSERT INTO catalog_versions (id, version, inventory_version)
        VALUES (1, 1, 1)
        ON CONFLICT (id) DO NOTHING;
        """
    )

    for seq_name in SEQUENCES:
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START WITH 1000 INCREMENT BY 1;")

    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_phone ON customers (phone);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_email ON customers (email);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customers_email;")
    op.execute("DROP INDEX IF EXISTS ix_customers_phone;")
    for seq_name in reversed(SEQUENCES):
        op.execute(f"DROP SEQUENCE IF EXISTS {seq_name};")
    op.execute("DROP TABLE IF EXISTS catalog_versions;")

