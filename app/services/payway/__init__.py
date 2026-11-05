"""ABA PayWay HTTP client.

Handles:
- req_time generation (YYYYMMDDHHmmss UTC)
- HMAC-SHA512 hash building with UTF-8 encoded secret key
- POST /api/payment-gateway/v1/payments/generate-qr (in-store POS KHQR)
- POST /api/payment-gateway/v1/payments/check-transaction-2 (status polling)
- POST /api/payment-gateway/v1/payments/close-transaction (cancel)
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings


# ── Configuration dataclass & DB loader ──────────────────────────────────────

@dataclass
class PayWayConfig:
    """PayWay runtime credentials and gateway endpoints."""
    merchant_id: str
    public_key: str
    base_url: str


def _load_payway_config() -> PayWayConfig:
    """Load PayWay configuration directly from the database (auth.system & auth.credential_api_key)."""
    merchant_id = ""
    public_key = ""
    base_url = ""

    from app.core.database import get_static_session
    from app.models.auth_schema_model import CREDENTIAL_API_KEY_MODEL, SYSTEM_MODEL

    session = get_static_session()
    try:
        # Query system configuration
        system_row = (
            session.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == "payway",
                SYSTEM_MODEL.deleted_datetime.is_(None),
                SYSTEM_MODEL.status_code.in_(["active", "ACTIVE"]),
            )
            .first()
        )
        if system_row and system_row.base_url:
            base_url = system_row.base_url

        # Query API key credentials (merchant_id, public_key)
        cred_rows = (
            session.query(CREDENTIAL_API_KEY_MODEL)
            .filter(
                CREDENTIAL_API_KEY_MODEL.system_code == "payway",
                CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None),
                CREDENTIAL_API_KEY_MODEL.status_code.in_(["active", "ACTIVE"]),
            )
            .all()
        )
        for row in cred_rows:
            if row.key_name == "merchant_id" and row.key_value:
                merchant_id = row.key_value
            elif row.key_name == "public_key" and row.key_value:
                public_key = row.key_value
    finally:
        session.close()

    return PayWayConfig(
        merchant_id=merchant_id,
        public_key=public_key,
        base_url=base_url.rstrip("/"),
    )


# ── Status code mapping ──────────────────────────────────────────────────────
_STATUS_MAP: dict[str, str] = {
    "0": "APPROVED",
    "00": "APPROVED",
    "2": "PENDING",
    "3": "DECLINED",
    "4": "REFUNDED",
    "7": "CANCELLED",
}


def map_payway_status(response: dict[str, Any]) -> tuple[str, str]:
    """Extract (status, apv) from a check-transaction-2 response body.

    ABA PayWay check-transaction-2 returns:
    {
      "data": {
        "payment_status_code": 2,
        "payment_status": "PENDING",
        "apv": ""
      },
      "status": {"code": "00", "message": "Success!"}
    }
    """
    data = response.get("data")
    if isinstance(data, dict):
        status_name = (data.get("payment_status") or "").upper()
        if status_name in ("APPROVED", "PENDING", "DECLINED", "REFUNDED", "CANCELLED"):
            return status_name, data.get("apv") or ""

        code = str(data.get("payment_status_code", ""))
        mapped = _STATUS_MAP.get(code)
        if mapped:
            return mapped, data.get("apv") or ""

    # Fallback to top-level if format varies
    top_status = response.get("status")
    if isinstance(top_status, dict):
        code = str(top_status.get("code", ""))
        return _STATUS_MAP.get(code, "PENDING"), response.get("apv") or ""
    elif top_status is not None:
        return _STATUS_MAP.get(str(top_status), "PENDING"), response.get("apv") or ""

    return "PENDING", ""


# ── Hash helpers ─────────────────────────────────────────────────────────────

def _hmac_sha512_b64(key: str, data: str) -> str:
    """Return base64(HMAC-SHA512(data, key_bytes)) using raw string key as UTF-8 bytes."""
    key_bytes = key.encode("utf-8")
    digest = hmac.new(key_bytes, data.encode("utf-8"), hashlib.sha512).digest()
    return base64.b64encode(digest).decode("ascii")


def _req_time() -> str:
    """Current UTC time formatted as YYYYMMDDHHmmss."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _generate_qr_hash(
    req_time: str,
    merchant_id: str,
    tran_id: str,
    amount_str: str,
    items_b64: str,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    purchase_type: str,
    payment_option: str,
    callback_url_b64: str,
    return_deeplink: str,
    currency: str,
    custom_fields: str,
    return_params: str,
    payout: str,
    lifetime: str,
    qr_image_template: str,
    public_key: Optional[str] = None,
) -> str:
    """HMAC-SHA512 over the 19 concatenated fields documented for /generate-qr."""
    data = (
        req_time
        + merchant_id
        + tran_id
        + amount_str
        + items_b64
        + first_name
        + last_name
        + email
        + phone
        + purchase_type
        + payment_option
        + callback_url_b64
        + return_deeplink
        + currency
        + custom_fields
        + return_params
        + payout
        + lifetime
        + qr_image_template
    )
    if not public_key:
        raise ValueError("PayWay public_key is required for signing but is not configured in DB (auth.credential_api_key)")
    return _hmac_sha512_b64(public_key, data)


def _purchase_hash(
    req_time: str,
    merchant_id: str,
    tran_id: str,
    amount_str: str,
    items_b64: str,
    shipping: str,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    type_str: str,
    payment_option: str,
    return_url: str,
    cancel_url: str,
    continue_success_url: str,
    return_deeplink: str,
    currency: str,
    custom_fields: str,
    return_params: str,
    payout: str,
    lifetime: str,
    additional_params: str,
    google_pay_token: str,
    skip_success_page: str,
    public_key: Optional[str] = None,
) -> str:
    """HMAC-SHA512 over the 24 concatenated fields documented for /purchase."""
    data = (
        req_time
        + merchant_id
        + tran_id
        + amount_str
        + items_b64
        + shipping
        + first_name
        + last_name
        + email
        + phone
        + type_str
        + payment_option
        + return_url
        + cancel_url
        + continue_success_url
        + return_deeplink
        + currency
        + custom_fields
        + return_params
        + payout
        + lifetime
        + additional_params
        + google_pay_token
        + skip_success_page
    )
    if not public_key:
        raise ValueError("PayWay public_key is required for signing but is not configured in DB (auth.credential_api_key)")
    return _hmac_sha512_b64(public_key, data)


def _check_hash(req_time: str, merchant_id: str, tran_id: str, public_key: Optional[str] = None) -> str:
    """HMAC-SHA512 for Check Transaction: req_time + merchant_id + tran_id."""
    data = req_time + merchant_id + tran_id
    if not public_key:
        raise ValueError("PayWay public_key is required for signing but is not configured in DB (auth.credential_api_key)")
    return _hmac_sha512_b64(public_key, data)


def _close_hash(req_time: str, merchant_id: str, tran_id: str, public_key: Optional[str] = None) -> str:
    """HMAC-SHA512 for Close Transaction: req_time + merchant_id + tran_id."""
    data = req_time + merchant_id + tran_id
    if not public_key:
        raise ValueError("PayWay public_key is required for signing but is not configured in DB (auth.credential_api_key)")
    return _hmac_sha512_b64(public_key, data)


# ── Client ───────────────────────────────────────────────────────────────────

class PayWayClient:
    """Async HTTP client for ABA PayWay."""

    def __init__(self) -> None:
        self._cached_config: Optional[PayWayConfig] = None
        self._cache_time: float = 0.0
        self._cache_ttl_seconds: float = 60.0

    def get_config(self) -> PayWayConfig:
        """Get cached PayWayConfig or refresh from DB if TTL has expired."""
        now = time.time()
        if self._cached_config is None or (now - self._cache_time) > self._cache_ttl_seconds:
            self._cached_config = _load_payway_config()
            self._cache_time = now
        return self._cached_config

    @property
    def base_url(self) -> str:
        return self.get_config().base_url

    @property
    def merchant_id(self) -> str:
        return self.get_config().merchant_id

    @property
    def public_key(self) -> str:
        return self.get_config().public_key

    async def create_khqr(
        self,
        tran_id: str,
        amount_usd: float,
        item_name: str = "Store Purchase",
        first_name: str = "Customer",
        last_name: str = "POS",
        phone: str = "012345678",
        email: str = "pos@clothingstore.com",
    ) -> dict[str, Any]:
        """Call POST /generate-qr with abapay_khqr payment_option.

        Returns dict containing:
        - qrString: EMVCo KHQR payload
        - qrImage: Pre-rendered base64 PNG data URL
        - abapay_deeplink: Deep link to ABA Mobile app
        """
        cfg = self.get_config()
        req_time = _req_time()
        amount_str = f"{amount_usd:.2f}"
        items_list = [{"name": item_name[:40], "quantity": 1, "price": amount_str}]
        items_b64 = base64.b64encode(json.dumps(items_list).encode("utf-8")).decode("ascii")

        callback_url_b64 = ""
        if settings.PAYWAY_CALLBACK_BASE_URL:
            raw_cb = f"{settings.PAYWAY_CALLBACK_BASE_URL.rstrip('/')}/api/payments/aba/pushback"
            callback_url_b64 = base64.b64encode(raw_cb.encode("utf-8")).decode("ascii")

        purchase_type = "purchase"
        payment_option = "abapay_khqr"
        return_deeplink = ""
        currency = "USD"
        custom_fields = ""
        return_params = ""
        payout = ""
        lifetime_min = str(settings.PAYWAY_QR_LIFETIME_MINUTES or 10)
        qr_image_template = "template3_color"

        hash_val = _generate_qr_hash(
            req_time=req_time,
            merchant_id=cfg.merchant_id,
            tran_id=tran_id,
            amount_str=amount_str,
            items_b64=items_b64,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            purchase_type=purchase_type,
            payment_option=payment_option,
            callback_url_b64=callback_url_b64,
            return_deeplink=return_deeplink,
            currency=currency,
            custom_fields=custom_fields,
            return_params=return_params,
            payout=payout,
            lifetime=lifetime_min,
            qr_image_template=qr_image_template,
            public_key=cfg.public_key,
        )

        payload = {
            "req_time": req_time,
            "merchant_id": cfg.merchant_id,
            "tran_id": tran_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "amount": amount_str,
            "purchase_type": purchase_type,
            "payment_option": payment_option,
            "items": items_b64,
            "currency": currency,
            "callback_url": callback_url_b64 or None,
            "return_deeplink": None,
            "custom_fields": None,
            "return_params": None,
            "payout": None,
            "lifetime": int(lifetime_min),
            "qr_image_template": qr_image_template,
            "hash": hash_val,
        }

        endpoint = f"{cfg.base_url}/api/payment-gateway/v1/payments/generate-qr"
        logger.debug(f"[PayWay] generate-qr tran_id={tran_id} amount={amount_str}")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)

        body = resp.json()
        logger.debug(f"[PayWay] generate-qr HTTP {resp.status_code} tran_id={tran_id}")

        if resp.status_code != 200 or not (body.get("qrString") or body.get("qr_string")):
            status_obj = body.get("status")
            msg = status_obj.get("message") if isinstance(status_obj, dict) else str(body)
            raise RuntimeError(f"PayWay generate-qr error: {msg}")

        return body

    async def check_transaction(self, tran_id: str) -> dict[str, Any]:
        """Call POST /check-transaction-2 and return response body."""
        cfg = self.get_config()
        req_time = _req_time()
        hash_value = _check_hash(req_time, cfg.merchant_id, tran_id, public_key=cfg.public_key)

        payload = {
            "req_time": req_time,
            "merchant_id": cfg.merchant_id,
            "tran_id": tran_id,
            "hash": hash_value,
        }

        endpoint = f"{cfg.base_url}/api/payment-gateway/v1/payments/check-transaction-2"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)

        body = resp.json()
        logger.debug(f"[PayWay] check-transaction-2 HTTP {resp.status_code} tran_id={tran_id}")
        return body

    async def close_transaction(self, tran_id: str) -> dict[str, Any]:
        """Call POST /close-transaction to cancel a pending QR."""
        cfg = self.get_config()
        req_time = _req_time()
        hash_value = _close_hash(req_time, cfg.merchant_id, tran_id, public_key=cfg.public_key)

        payload = {
            "req_time": req_time,
            "merchant_id": cfg.merchant_id,
            "tran_id": tran_id,
            "hash": hash_value,
        }

        endpoint = f"{cfg.base_url}/api/payment-gateway/v1/payments/close-transaction"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)

        body = resp.json()
        logger.debug(f"[PayWay] close-transaction HTTP {resp.status_code} tran_id={tran_id}")
        return body

    def build_purchase_form_data(
        self,
        tran_id: str,
        amount_usd: float,
        payment_option: str = "cards",
        item_name: str = "Store Purchase",
        first_name: str = "Customer",
        last_name: str = "POS",
        phone: str = "012345678",
        email: str = "pos@clothingstore.com",
    ) -> tuple[str, dict[str, str]]:
        """Build parameters and HMAC-SHA512 hash for POST /purchase (modal popup / bottom sheet).

        Returns:
            (action_url, form_data_dict)
        """
        cfg = self.get_config()
        req_time = _req_time()
        amount_str = f"{amount_usd:.2f}"
        items_list = [{"name": item_name[:40], "quantity": 1, "price": amount_str}]
        items_b64 = base64.b64encode(json.dumps(items_list).encode("utf-8")).decode("ascii")

        callback_url_b64 = ""
        if settings.PAYWAY_CALLBACK_BASE_URL:
            raw_cb = f"{settings.PAYWAY_CALLBACK_BASE_URL.rstrip('/')}/api/payments/aba/pushback"
            callback_url_b64 = base64.b64encode(raw_cb.encode("utf-8")).decode("ascii")

        type_str = "purchase"
        shipping = ""
        cancel_url = ""
        continue_success_url = ""
        return_deeplink = ""
        currency = "USD"
        custom_fields = ""
        return_params = ""
        payout = ""
        lifetime = str(settings.PAYWAY_QR_LIFETIME_MINUTES or 10)
        additional_params = ""
        google_pay_token = ""
        skip_success_page = "1"

        hash_val = _purchase_hash(
            req_time=req_time,
            merchant_id=cfg.merchant_id,
            tran_id=tran_id,
            amount_str=amount_str,
            items_b64=items_b64,
            shipping=shipping,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            type_str=type_str,
            payment_option=payment_option or "",
            return_url=callback_url_b64,
            cancel_url=cancel_url,
            continue_success_url=continue_success_url,
            return_deeplink=return_deeplink,
            currency=currency,
            custom_fields=custom_fields,
            return_params=return_params,
            payout=payout,
            lifetime=lifetime,
            additional_params=additional_params,
            google_pay_token=google_pay_token,
            skip_success_page=skip_success_page,
            public_key=cfg.public_key,
        )

        form_data = {
            "req_time": req_time,
            "merchant_id": cfg.merchant_id,
            "tran_id": tran_id,
            "amount": amount_str,
            "items": items_b64,
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "phone": phone,
            "type": type_str,
            "payment_option": payment_option or "",
            "currency": currency,
            "lifetime": lifetime,
            "skip_success_page": skip_success_page,
            "view_type": "popup",
            "payment_gate": "0",
            "hash": hash_val,
        }
        if callback_url_b64:
            form_data["return_url"] = callback_url_b64

        action_url = f"{cfg.base_url}/api/payment-gateway/v1/payments/purchase"
        return action_url, form_data

    async def get_transaction_detail(self, tran_id: str) -> dict[str, Any]:
        """Call POST /transaction-detail to retrieve full transaction metadata."""
        cfg = self.get_config()
        req_time = _req_time()
        hash_value = _check_hash(req_time, cfg.merchant_id, tran_id, public_key=cfg.public_key)

        payload = {
            "req_time": req_time,
            "merchant_id": cfg.merchant_id,
            "tran_id": tran_id,
            "hash": hash_value,
        }

        endpoint = f"{cfg.base_url}/api/payment-gateway/v1/payments/transaction-detail"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)

        body = resp.json()
        logger.debug(f"[PayWay] transaction-detail HTTP {resp.status_code} tran_id={tran_id}")
        return body
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(endpoint, json=payload)

        body = resp.json()
        logger.debug(f"[PayWay] transaction-detail HTTP {resp.status_code} tran_id={tran_id}")
        return body


# Singleton
payway_client = PayWayClient()

