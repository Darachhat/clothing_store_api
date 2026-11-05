"""Seed PayWay system integration and Telegram bot/chat bootstrap rows.

Revision ID: 0011_seed_payway_and_telegram_config
Revises: 0010_telegram_auth_and_phone_linking
Create Date: 2026-11-05 19:47:00.000000
"""
from __future__ import annotations

from alembic import op

revision      = "0011_seed_payway_and_telegram_config"
down_revision = "0010_telegram_auth_and_phone_linking"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # ── Telegram Bot ──────────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO auth.telegram_bot (
            id, code, name, username, token, description,
            status_code, created_datetime, updated_datetime, created_by
        )
        VALUES (
            gen_random_uuid(),
            'clothing_store_bot',
            'Clothing Store Bot',
            'clothing_store_kvm_bot',
            '8453886789:AAEYlrepnRAlWvOYz-fZX_De6Hs9eLbJRWE',
            'Primary notification bot for Clothing Store',
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)

    # ── Telegram Chat ─────────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO auth.telegram_chat (
            id, code, telegram_bot_code, name, type, chat_id, description,
            status_code, created_datetime, updated_datetime, created_by
        )
        VALUES (
            gen_random_uuid(),
            'clothing_store_alerts',
            'clothing_store_bot',
            'Clothing Store Alerts Group',
            'group',
            '-5195769348',
            'Main alert group for operational notifications',
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)

    # ── PayWay System ─────────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO auth.system (
            id, code, name, description, base_url, scope,
            is_encrypted_body, status_code, created_datetime, updated_datetime, created_by
        )
        VALUES (
            gen_random_uuid(),
            'payway',
            'ABA PayWay',
            'ABA PayWay payment gateway integration (sandbox)',
            'https://checkout-sandbox.payway.com.kh',
            'external',
            false,
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)

    # ── PayWay System Credential (outbound) ───────────────────────────────────
    op.execute("""
        INSERT INTO auth.system_credential (
            id, system_code, description, traffic_type, auth_type_code,
            status_code, created_datetime, updated_datetime, created_by
        )
        VALUES (
            gen_random_uuid(),
            'payway',
            'PayWay HMAC-SHA512 API credentials',
            'outbound',
            'api_key',
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)

    # ── PayWay API Keys ───────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO auth.credential_api_key (
            id, system_code, traffic_type, key_location, key_name, key_value,
            description, status_code, created_datetime, updated_datetime, created_by
        )
        VALUES
        (
            gen_random_uuid(),
            'payway',
            'outbound',
            'body',
            'merchant_id',
            'ec479700',
            'PayWay Merchant ID',
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'outbound',
            'body',
            'public_key',
            '3F3C50388E2F0236777CC5E9BB90D47C35447D5B',
            'PayWay HMAC-SHA512 signing key',
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'outbound',
            'body',
            'rsa_public_key',
            'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDCt4VrCyJJ9hYhA6ulkqz4Z/FhZMngg0XOpdS3dOHaeUe+aEQ1q2opkDncCG9rAxM+qK3kSPiHDOwkMxmp956iR1wusTqvDOwJf0m6x8mKWWgbHIbxD0KCfyZjqNrUZ3PP+VTxUJ0+jOupingtQD5eAx9IdRAk7Yss+feJ7hzaxQIDAQAB',
            'PayWay RSA Public Key',
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'outbound',
            'body',
            'rsa_private_key',
            'MIICXAIBAAKBgQDCt4VrCyJJ9hYhA6ulkqz4Z/FhZMngg0XOpdS3dOHaeUe+aEQ1q2opkDncCG9rAxM+qK3kSPiHDOwkMxmp956iR1wusTqvDOwJf0m6x8mKWWgbHIbxD0KCfyZjqNrUZ3PP+VTxUJ0+jOupingtQD5eAx9IdRAk7Yss+feJ7hzaxQIDAQABAoGADcboZLuD8JG93RYiZfOr02OfW5HDCuSe4tEu7NATTt736Yv9D4MSXuB6h4v9PigYi31p2FYlZ4DNkH4hGbqQebE8Ucmy7Cy94ERPEP02NKpKPY0FrOa5/VQud2lF44uYpi8XmqP2S47Wb7aUFPYVzr8tq/00N4kWOy/S3GDvQCECQQDxTETlGtE182JVquT3IRxXLQb9BbmM2UjhRVrkqa5CHnr8PI+pK4zV+6fjdNHpM1uxucNg1lvlAJgqh6C+rOH5AkEAzpSv/lMbTg1pJ1apaZLZoxzHNCPdONMcdRdvzJEqewFtg+zWRw3niQEzcwS1C0FJs+uALB6VArPAXdD0n+qyLQJBANSSczM+L8aOljeQKMvJoJTv9vMagv8hQIIsPkmpbfmTrpbdp1XKJvUwERRhircdZo8oboW18hjJMERvXV39IckCQAXafrYlIrPue1lLAlfkelg924MltQIEMV08AcX5IwwDOVgwoM24niPqrcuHiZ29BtqbRLF7WFuQPlYqMpRJcS0CQDJ8PG73m6lUZl8lHjwblAAUPJj+zRmRLa7zCiVJwyjdPNspiLMCoOvwQLhZxBILILf9wdo5KpcB8Em5+DJ/jDY=',
            'PayWay RSA Private Key',
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)

    # ── PayWay Endpoints ──────────────────────────────────────────────────────
    op.execute("""
        INSERT INTO auth.system_endpoint (
            id, system_code, code, name, operation_type, endpoint,
            http_method, traffic_type, request_timeout, status_code,
            created_datetime, updated_datetime, created_by
        )
        VALUES
        (
            gen_random_uuid(),
            'payway',
            'payway_generate_qr',
            'PayWay Generate QR',
            'generate_qr',
            '/api/payment-gateway/v1/payments/generate-qr',
            'POST',
            'outbound',
            30,
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'payway_check_transaction',
            'PayWay Check Transaction',
            'check_transaction',
            '/api/payment-gateway/v1/payments/check-transaction-2',
            'POST',
            'outbound',
            30,
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'payway_close_transaction',
            'PayWay Close Transaction',
            'close_transaction',
            '/api/payment-gateway/v1/payments/close-transaction',
            'POST',
            'outbound',
            30,
            'active',
            NOW(), NOW(), 'system'
        ),
        (
            gen_random_uuid(),
            'payway',
            'payway_checkout_script',
            'PayWay Checkout Script',
            'checkout_script',
            'https://checkout.payway.com.kh/plugins/checkout2-0.js?hide-close=2',
            'GET',
            'outbound',
            30,
            'active',
            NOW(), NOW(), 'system'
        )
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    # Remove PayWay endpoints
    op.execute("""
        DELETE FROM auth.system_endpoint
        WHERE system_code = 'payway'
          AND code IN (
              'payway_generate_qr',
              'payway_check_transaction',
              'payway_close_transaction',
              'payway_checkout_script'
          );
    """)

    # Remove PayWay API key credentials
    op.execute("""
        DELETE FROM auth.credential_api_key
        WHERE system_code = 'payway'
          AND key_name IN ('merchant_id', 'public_key');
    """)

    # Remove PayWay system credential record
    op.execute("""
        DELETE FROM auth.system_credential
        WHERE system_code = 'payway'
          AND traffic_type = 'outbound'
          AND auth_type_code = 'api_key';
    """)

    # Remove PayWay system entry
    op.execute("""
        DELETE FROM auth.system
        WHERE code = 'payway';
    """)

    # Remove Telegram chat
    op.execute("""
        DELETE FROM auth.telegram_chat
        WHERE code = 'clothing_store_alerts';
    """)

    # Remove Telegram bot
    op.execute("""
        DELETE FROM auth.telegram_bot
        WHERE code = 'clothing_store_bot';
    """)
