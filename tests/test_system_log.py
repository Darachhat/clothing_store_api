"""
Test: system_log inbound & outbound tracking via LOG_SERVICE.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.models.track_model import SYSTEM_LOG_MODEL
from app.services.log_service import LOG_SERVICE


def test_write_inbound_log(db_session):
    """
    LOG_SERVICE.write_inbound should persist a SYSTEM_LOG_MODEL record
    with traffic_type='inbound'.
    """
    LOG_SERVICE.write_inbound(
        db              = db_session
        , request_id    = "req_test001"
        , system_code   = "test_system"
        , method        = "POST"
        , endpoint      = "/api/v1/resource"
        , netloc        = "localhost:8000"
        , content_type  = "application/json"
        , user_agent    = "pytest/test"
        , req_headers   = {"content-type": "application/json", "x-api-key": "***"}
        , req_body      = {"key": "value"}
        , req_datetime  = datetime.now(timezone.utc)
        , client_ip     = "127.0.0.1"
        , resp_code     = 200
        , resp_headers  = {"content-type": "application/json"}
        , resp_body     = {"code": "00000"}
        , resp_duration = Decimal("12.34")
        , resp_datetime = datetime.now(timezone.utc)
    )

    record = db_session.query(SYSTEM_LOG_MODEL).filter(
        SYSTEM_LOG_MODEL.client_log_id == "req_test001"
    ).first()

    assert record is not None
    assert record.traffic_type     == "inbound"
    assert record.system_code      == "test_system"
    assert record.request_method   == "POST"
    assert record.request_endpoint == "/api/v1/resource"
    assert record.client_ip        == "127.0.0.1"
    assert record.response_code    == 200


def test_write_outbound_log(db_session):
    """
    LOG_SERVICE.write_outbound should persist a SYSTEM_LOG_MODEL record
    with traffic_type='outbound'.
    """
    LOG_SERVICE.write_outbound(
        db              = db_session
        , request_id    = "out_test001"
        , system_code   = "owsm_api"
        , method        = "GET"
        , endpoint      = "https://external.gov.kh/api/data"
        , netloc        = "external.gov.kh"
        , content_type  = "application/json"
        , req_headers   = {"Authorization": "Bearer ***"}
        , req_body      = None
        , req_datetime  = datetime.now(timezone.utc)
        , resp_code     = 200
        , resp_headers  = {"content-type": "application/json"}
        , resp_body     = {"status": "ok"}
        , resp_duration = Decimal("88.56")
        , resp_datetime = datetime.now(timezone.utc)
    )

    record = db_session.query(SYSTEM_LOG_MODEL).filter(
        SYSTEM_LOG_MODEL.client_log_id == "out_test001"
    ).first()

    assert record is not None
    assert record.traffic_type      == "outbound"
    assert record.system_code       == "owsm_api"
    assert record.request_method    == "GET"
    assert record.request_endpoint  == "https://external.gov.kh/api/data"
    assert record.response_code     == 200
    assert record.response_duration == Decimal("88.56")

