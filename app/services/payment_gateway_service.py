"""Payment Gateway service — management of ABA PayWay credentials, endpoints, and status."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import NOT_FOUND_EXCEPTION
from app.models.auth_schema_model import (
    CREDENTIAL_API_KEY_MODEL,
    SYSTEM_ENDPOINT_MODEL,
    SYSTEM_MODEL,
)
from app.models import SystemSetting
from app.schemas.payment_gateway_schema import (
    PAYMENT_GATEWAY_CONFIG_SCHEMA,
    PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA,
    PAYMENT_GATEWAY_UPDATE_SCHEMA,
)
from app.services.payway import payway_client


class PAYMENT_GATEWAY_SERVICE:
    """Service for managing payment gateway (ABA PayWay) database configuration."""

    @staticmethod
    def get_gateway_config(
        db          : Session,
        system_code : str = "payway"
    ) -> PAYMENT_GATEWAY_CONFIG_SCHEMA:
        # 1. Fetch system record
        system_row = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == system_code,
                SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not system_row:
            raise NOT_FOUND_EXCEPTION(f"Payment gateway system '{system_code}' was not found.")

        # 2. Fetch API key credentials
        cred_rows = (
            db.query(CREDENTIAL_API_KEY_MODEL)
            .filter(
                CREDENTIAL_API_KEY_MODEL.system_code == system_code,
                CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None)
            )
            .all()
        )
        creds_map: Dict[str, str] = {row.key_name: (row.key_value or "") for row in cred_rows}

        # 3. Fetch checkout script endpoint
        endpoint_row = (
            db.query(SYSTEM_ENDPOINT_MODEL)
            .filter(
                SYSTEM_ENDPOINT_MODEL.system_code == system_code,
                SYSTEM_ENDPOINT_MODEL.code == "payway_checkout_script",
                SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        script_url = endpoint_row.endpoint if endpoint_row else settings.PAYWAY_CHECKOUT_SCRIPT_URL

        # 4. Fetch dynamic operational settings (callback URL, QR lifetime)
        setting_row = (
            db.query(SystemSetting)
            .filter(
                SystemSetting.category == "payment",
                SystemSetting.key == "payway_config",
                SystemSetting.deleted_datetime.is_(None)
            )
            .first()
        )
        extra_cfg = setting_row.value if setting_row and isinstance(setting_row.value, dict) else {}

        callback_url = extra_cfg.get("callback_base_url") or settings.PAYWAY_CALLBACK_BASE_URL
        qr_lifetime  = int(extra_cfg.get("qr_lifetime_minutes") or settings.PAYWAY_QR_LIFETIME_MINUTES or 10)

        return PAYMENT_GATEWAY_CONFIG_SCHEMA(
            system_code         = system_row.code,
            name                = system_row.name,
            status_code         = system_row.status_code,
            base_url            = system_row.base_url or "https://checkout-sandbox.payway.com.kh",
            merchant_id         = creds_map.get("merchant_id", ""),
            public_key          = creds_map.get("public_key", ""),
            rsa_public_key      = creds_map.get("rsa_public_key", ""),
            rsa_private_key     = creds_map.get("rsa_private_key", ""),
            callback_base_url   = callback_url,
            qr_lifetime_minutes = qr_lifetime,
            checkout_script_url = script_url,
        )

    @staticmethod
    def update_gateway_config(
        db          : Session,
        data        : PAYMENT_GATEWAY_UPDATE_SCHEMA,
        system_code : str = "payway"
    ) -> PAYMENT_GATEWAY_CONFIG_SCHEMA:
        now = datetime.now(timezone.utc)

        # 1. Update or create system row
        system_row = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == system_code,
                SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not system_row:
            system_row = SYSTEM_MODEL(
                code              = system_code,
                name              = data.name or "ABA PayWay",
                base_url          = data.base_url or "https://checkout-sandbox.payway.com.kh",
                status_code       = data.status_code or "active",
                created_by        = "admin",
                created_datetime  = now,
            )
            db.add(system_row)
        else:
            if data.name is not None:
                system_row.name = data.name
            if data.status_code is not None:
                system_row.status_code = data.status_code
            if data.base_url is not None:
                system_row.base_url = data.base_url
            system_row.updated_datetime = now
            system_row.updated_by = "admin"

        # 2. Update credentials in auth.credential_api_key
        cred_fields = {
            "merchant_id"     : data.merchant_id,
            "public_key"      : data.public_key,
            "rsa_public_key"  : data.rsa_public_key,
            "rsa_private_key" : data.rsa_private_key,
        }

        for key_name, key_val in cred_fields.items():
            if key_val is None:
                continue
            row = (
                db.query(CREDENTIAL_API_KEY_MODEL)
                .filter(
                    CREDENTIAL_API_KEY_MODEL.system_code == system_code,
                    CREDENTIAL_API_KEY_MODEL.key_name == key_name,
                    CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
            if row:
                row.key_value        = key_val
                row.updated_datetime = now
                row.updated_by       = "admin"
                row.status_code      = "active"
            else:
                db.add(
                    CREDENTIAL_API_KEY_MODEL(
                        system_code      = system_code,
                        traffic_type     = "outbound",
                        key_location     = "body",
                        key_name         = key_name,
                        key_value        = key_val,
                        description      = f"PayWay {key_name}",
                        status_code      = "active",
                        created_by       = "admin",
                        created_datetime = now,
                        updated_datetime = now,
                    )
                )

        # 3. Update checkout script endpoint
        if data.checkout_script_url is not None:
            endpoint_row = (
                db.query(SYSTEM_ENDPOINT_MODEL)
                .filter(
                    SYSTEM_ENDPOINT_MODEL.system_code == system_code,
                    SYSTEM_ENDPOINT_MODEL.code == "payway_checkout_script",
                    SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
                )
                .first()
            )
            if endpoint_row:
                endpoint_row.endpoint         = data.checkout_script_url
                endpoint_row.updated_datetime = now
                endpoint_row.updated_by       = "admin"
            else:
                db.add(
                    SYSTEM_ENDPOINT_MODEL(
                        system_code      = system_code,
                        code             = "payway_checkout_script",
                        name             = "PayWay Checkout Script",
                        operation_type   = "checkout_script",
                        endpoint         = data.checkout_script_url,
                        http_method      = "GET",
                        traffic_type     = "outbound",
                        request_timeout  = 30,
                        status_code      = "active",
                        created_by       = "admin",
                        created_datetime = now,
                        updated_datetime = now,
                    )
                )

        # 4. Save callback and lifetime to system settings
        if data.callback_base_url is not None or data.qr_lifetime_minutes is not None:
            setting_row = (
                db.query(SystemSetting)
                .filter(
                    SystemSetting.category == "payment",
                    SystemSetting.key == "payway_config",
                    SystemSetting.deleted_datetime.is_(None)
                )
                .first()
            )
            current_val = dict(setting_row.value) if (setting_row and isinstance(setting_row.value, dict)) else {}
            if data.callback_base_url is not None:
                current_val["callback_base_url"] = data.callback_base_url
            if data.qr_lifetime_minutes is not None:
                current_val["qr_lifetime_minutes"] = data.qr_lifetime_minutes

            if setting_row:
                setting_row.value = current_val
                setting_row.updated_datetime = now
                setting_row.updated_by = "admin"
            else:
                db.add(
                    SystemSetting(
                        category         = "payment",
                        key              = "payway_config",
                        value            = current_val,
                        description      = "PayWay callback and QR settings",
                        created_by       = "admin",
                        created_datetime = now,
                        updated_datetime = now,
                    )
                )

        db.commit()

        # Invalidate client TTL cache so immediate subsequent requests see updated config
        payway_client._cached_config = None
        payway_client._cache_time   = 0.0

        return PAYMENT_GATEWAY_SERVICE.get_gateway_config(db=db, system_code=system_code)

    @staticmethod
    async def test_gateway_connection(
        db          : Session,
        system_code : str = "payway"
    ) -> PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA:
        """Verify gateway parameters and test connectivity to ABA PayWay."""
        cfg = PAYMENT_GATEWAY_SERVICE.get_gateway_config(db=db, system_code=system_code)

        if not cfg.merchant_id or not cfg.public_key:
            return PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA(
                is_valid = False,
                message  = "Merchant ID or Public Key is missing in database.",
                details  = {"merchant_id": bool(cfg.merchant_id), "public_key": bool(cfg.public_key)}
            )

        # Test request to check-transaction-2 endpoint with a mock dummy tran_id
        endpoint = f"{cfg.base_url.rstrip('/')}/api/payment-gateway/v1/payments/check-transaction-2"
        now_str  = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        test_tran_id = "TEST_PING"

        import base64
        import hashlib
        import hmac
        key_bytes = cfg.public_key.encode("utf-8")
        raw_data  = f"{now_str}{cfg.merchant_id}{test_tran_id}"
        sig       = base64.b64encode(hmac.new(key_bytes, raw_data.encode("utf-8"), hashlib.sha512).digest()).decode("ascii")

        payload = {
            "req_time"    : now_str,
            "merchant_id" : cfg.merchant_id,
            "tran_id"     : test_tran_id,
            "hash"        : sig,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(endpoint, json=payload)
                data = resp.json()

            # ABA PayWay returns HTTP 200 with JSON error message for unknown tran_id if merchant/hash is valid
            # or a specific status code
            status_obj = data.get("status") if isinstance(data, dict) else None
            msg = status_obj.get("message") if isinstance(status_obj, dict) else str(data)

            return PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA(
                is_valid = resp.status_code == 200,
                message  = f"PayWay Gateway responded (HTTP {resp.status_code}): {msg}",
                details  = {
                    "http_status" : resp.status_code,
                    "endpoint"    : endpoint,
                    "response"    : data,
                }
            )
        except Exception as exc:
            return PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA(
                is_valid = False,
                message  = f"Connection to PayWay failed: {str(exc)}",
                details  = {"endpoint": endpoint, "error": str(exc)}
            )
