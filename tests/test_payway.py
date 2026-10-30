"""Unit tests for ABA PayWay integration (hash helpers, response status mapping)."""
import pytest
from app.services.payway import _hmac_sha512_b64, _check_hash, _close_hash, map_payway_status


def test_hmac_sha512_b64_deterministic():
    key = "TEST_PUBLIC_KEY"
    data = "20261024120000merchant123tran456"
    h1 = _hmac_sha512_b64(key, data)
    h2 = _hmac_sha512_b64(key, data)
    assert h1 == h2
    assert len(h1) > 20


def test_map_payway_status_approved():
    resp = {
        "data": {
            "payment_status_code": 0,
            "payment_status": "APPROVED",
            "apv": "123456",
            "payment_amount": 10.50,
        },
        "status": {"code": "00", "message": "Success!"},
    }
    status, apv = map_payway_status(resp)
    assert status == "APPROVED"
    assert apv == "123456"


def test_map_payway_status_pending():
    resp = {
        "data": {
            "payment_status_code": 2,
            "payment_status": "PENDING",
            "apv": "",
        },
        "status": {"code": "00", "message": "Success!"},
    }
    status, apv = map_payway_status(resp)
    assert status == "PENDING"
    assert apv == ""


def test_map_payway_status_declined():
    resp = {
        "data": {
            "payment_status_code": 3,
            "payment_status": "DECLINED",
            "apv": "",
        },
        "status": {"code": "00", "message": "Success!"},
    }
    status, apv = map_payway_status(resp)
    assert status == "DECLINED"


def test_map_payway_status_cancelled():
    resp = {
        "data": {
            "payment_status_code": 7,
            "payment_status": "CANCELLED",
            "apv": "",
        },
        "status": {"code": "00", "message": "Success!"},
    }
    status, apv = map_payway_status(resp)
    assert status == "CANCELLED"
