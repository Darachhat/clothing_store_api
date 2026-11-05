"""Payment Gateway configuration schemas."""
from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PAYMENT_GATEWAY_CONFIG_SCHEMA(BaseModel):
    system_code         : str           = "payway"
    name                : str           = "ABA PayWay"
    status_code         : str           = "active"
    base_url            : str           = "https://checkout-sandbox.payway.com.kh"
    merchant_id         : str           = ""
    public_key          : str           = ""
    rsa_public_key      : Optional[str] = None
    rsa_private_key     : Optional[str] = None
    callback_base_url   : Optional[str] = None
    qr_lifetime_minutes : int           = 10
    checkout_script_url : Optional[str] = "https://checkout.payway.com.kh/plugins/checkout2-0.js?hide-close=2"


class PAYMENT_GATEWAY_UPDATE_SCHEMA(BaseModel):
    name                : Optional[str] = None
    status_code         : Optional[str] = Field(default=None, description="'active' or 'inactive'")
    base_url            : Optional[str] = Field(default=None, description="PayWay sandbox or live base URL")
    merchant_id         : Optional[str] = None
    public_key          : Optional[str] = None
    rsa_public_key      : Optional[str] = None
    rsa_private_key     : Optional[str] = None
    callback_base_url   : Optional[str] = None
    qr_lifetime_minutes : Optional[int] = Field(default=None, ge=1, le=120)
    checkout_script_url : Optional[str] = None


class PAYMENT_GATEWAY_TEST_RESPONSE_SCHEMA(BaseModel):
    is_valid : bool
    message  : str
    details  : Optional[Dict[str, Any]] = None

