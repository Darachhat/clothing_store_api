"""Official Telegram Login Widget cryptographic verification utilities."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
from typing import Any

from app.core.exceptions import BAD_REQUEST_EXCEPTION, UNAUTHORIZED_EXCEPTION


def compute_telegram_login_hash(
    auth_data: dict[str, Any],
    bot_token: str,
) -> str:
    """Compute the official Telegram Login Widget HMAC-SHA256 signature.

    Per https://core.telegram.org/widgets/login#checking-authorization:
      secret_key = SHA256(bot_token)
      data_check_string = sorted key=value pairs joined by '\\n' (excluding 'hash' and None/empty fields)
      signature = HMAC_SHA256(secret_key, data_check_string).hexdigest()
    """
    filtered: dict[str, str] = {}
    for key, value in auth_data.items():
        if key == "hash" or value is None or value == "":
            continue
        filtered[str(key)] = str(value)

    data_check_string = "\n".join(f"{k}={filtered[k]}" for k in sorted(filtered.keys()))
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_telegram_login_data(
    auth_data: dict[str, Any],
    bot_token: str,
    *,
    max_age_seconds: int = 300,
) -> dict[str, Any]:
    """Validate Telegram Login payload signature, fields, and timestamp freshness.

    Returns a normalized dict with verified `telegram_id`, `username`, `first_name`,
    `last_name`, `photo_url`, `auth_date`, and `hash`.
    """
    if not bot_token or not bot_token.strip():
        raise BAD_REQUEST_EXCEPTION("Telegram authentication is not configured on the server")

    raw_id = auth_data.get("id")
    raw_auth_date = auth_data.get("auth_date")
    received_hash = auth_data.get("hash")

    if raw_id is None or raw_auth_date is None or not received_hash:
        raise UNAUTHORIZED_EXCEPTION("Missing required Telegram authentication fields (id, auth_date, hash)")

    telegram_id = str(raw_id).strip()
    if not telegram_id.isdigit():
        raise UNAUTHORIZED_EXCEPTION("Invalid Telegram user ID")

    try:
        auth_date = int(raw_auth_date)
    except (TypeError, ValueError) as exc:
        raise UNAUTHORIZED_EXCEPTION("Invalid Telegram auth_date timestamp") from exc

    # Verify HMAC-SHA256 signature using constant-time comparison
    expected_hash = compute_telegram_login_hash(auth_data, bot_token.strip())
    if not hmac.compare_digest(expected_hash.lower(), str(received_hash).strip().lower()):
        raise UNAUTHORIZED_EXCEPTION("Invalid Telegram authentication signature")

    # Validate timestamp freshness
    now_ts = int(datetime.now(UTC).timestamp())
    if auth_date > now_ts + 60:
        raise UNAUTHORIZED_EXCEPTION("Telegram authentication timestamp is in the future")
    if now_ts - auth_date > max_age_seconds:
        raise UNAUTHORIZED_EXCEPTION("Telegram authentication data has expired")

    return {
        "telegram_id": telegram_id,
        "first_name": str(auth_data.get("first_name") or "").strip() or None,
        "last_name": str(auth_data.get("last_name") or "").strip() or None,
        "username": str(auth_data.get("username") or "").strip() or None,
        "photo_url": str(auth_data.get("photo_url") or "").strip() or None,
        "auth_date": auth_date,
        "hash": str(received_hash).strip().lower(),
    }

