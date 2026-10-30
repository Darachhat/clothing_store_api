"""create auth, base_data, and track schemas and core tables

Revision ID: 0003_template_core_schemas
Revises: 0002_payment_transactions
Create Date: 2026-10-30 16:38:00.000000

"""
from pathlib import Path
from alembic import op

# revision identifiers, used by Alembic.
revision      = "0003_template_core_schemas"
down_revision = "0002_payment_transactions"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    sql_path = Path(__file__).resolve().parent.parent / "sql" / "create_core_tables.sql"
    op.execute(sql_path.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.drop_table("telegram_outbound", schema="track")
    op.drop_table("system_log", schema="track")
    op.drop_table("system_endpoint", schema="auth")
    op.drop_table("telegram_chat", schema="auth")
    op.drop_table("telegram_bot", schema="auth")
    op.drop_table("credential_oauth2", schema="auth")
    op.drop_table("credential_api_key", schema="auth")
    op.drop_table("credential_bearer", schema="auth")
    op.drop_table("credential_basic", schema="auth")
    op.drop_table("system_credential", schema="auth")
    op.drop_table("system_client", schema="auth")
    op.drop_table("system", schema="auth")
    op.drop_table("currency", schema="base_data")
    op.drop_table("language", schema="base_data")
    op.drop_table("auth_type", schema="base_data")
    op.drop_table("status", schema="base_data")
    op.drop_table("translate", schema="base_data")

