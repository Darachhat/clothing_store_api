"""Add Telegram authentication, verified phone linking, and replay protection schema.

Revision ID: 0010_telegram_auth_and_phone_linking
Revises: 0009_add_system_settings
Create Date: 2026-11-05 15:10:00.000000
"""
from __future__ import annotations

from alembic import op

revision = "0010_telegram_auth_and_phone_linking"
down_revision = "0009_add_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE data.users
            ADD COLUMN IF NOT EXISTS phone_number VARCHAR(32),
            ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(64),
            ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(100),
            ADD COLUMN IF NOT EXISTS telegram_photo_url VARCHAR(500),
            ADD COLUMN IF NOT EXISTS telegram_linked_at TIMESTAMPTZ;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_number
            ON data.users (phone_number)
            WHERE phone_number IS NOT NULL AND deleted_datetime IS NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_telegram_id
            ON data.users (telegram_id)
            WHERE telegram_id IS NOT NULL AND deleted_datetime IS NULL;

        CREATE TABLE IF NOT EXISTS auth.telegram_auth_replays (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            auth_hash VARCHAR(128) NOT NULL UNIQUE,
            telegram_id VARCHAR(64) NOT NULL,
            auth_date INTEGER NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            status_code VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100)
        );

        CREATE INDEX IF NOT EXISTS ix_telegram_auth_replays_telegram_id
            ON auth.telegram_auth_replays (telegram_id);

        CREATE TABLE IF NOT EXISTS auth.phone_verifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES data.users(id) ON DELETE CASCADE,
            phone_number VARCHAR(32) NOT NULL,
            otp_hash VARCHAR(128) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            verified_at TIMESTAMPTZ,
            status_code VARCHAR(20) NOT NULL DEFAULT 'PENDING',
            created_datetime TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_datetime TIMESTAMPTZ DEFAULT NOW(),
            deleted_datetime TIMESTAMPTZ,
            created_by VARCHAR(100),
            updated_by VARCHAR(100),
            deleted_by VARCHAR(100)
        );

        CREATE INDEX IF NOT EXISTS ix_phone_verifications_user_id
            ON auth.phone_verifications (user_id);

        CREATE INDEX IF NOT EXISTS ix_phone_verifications_phone_number
            ON auth.phone_verifications (phone_number);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS auth.phone_verifications CASCADE;
        DROP TABLE IF EXISTS auth.telegram_auth_replays CASCADE;
        DROP INDEX IF EXISTS data.uq_users_telegram_id;
        DROP INDEX IF EXISTS data.uq_users_phone_number;
        ALTER TABLE data.users
            DROP COLUMN IF EXISTS telegram_linked_at,
            DROP COLUMN IF EXISTS telegram_photo_url,
            DROP COLUMN IF EXISTS telegram_username,
            DROP COLUMN IF EXISTS telegram_id,
            DROP COLUMN IF EXISTS phone_verified_at,
            DROP COLUMN IF EXISTS phone_number;
        """
    )

