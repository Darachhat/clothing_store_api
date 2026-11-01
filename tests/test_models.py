from app.models import (
    CREDENTIAL_BASIC_MODEL
    , SYSTEM_CREDENTIAL_MODEL
    , SYSTEM_ENDPOINT_MODEL
    , SYSTEM_MODEL
    , TELEGRAM_BOT_MODEL
)
from app.models import AUTH_TYPE_MODEL, STATUS_MODEL
from app.models import SYSTEM_LOG_MODEL


def test_system_and_credential_model_persistence(db_session):
    # 1. Create System
    system = SYSTEM_MODEL(
        code          = "owsm_api"
        , name        = "Ministry of Interior API"
        , description = "MOI integration system"
        , base_url    = "https://moi.gov.kh"
        , scope       = "external"
    )
    db_session.add(system)
    db_session.commit()
    db_session.refresh(system)

    assert system.id is not None
    assert system.code == "owsm_api"

    # 2. Create System Credential
    cred = SYSTEM_CREDENTIAL_MODEL(
        system_code      = "owsm_api"
        , traffic_type   = "inbound"
        , auth_type_code = "basic"
        , description    = "MOI inbound basic auth"
    )
    db_session.add(cred)
    db_session.commit()
    db_session.refresh(cred)

    assert cred.id is not None
    assert cred.system_code == "owsm_api"


def test_system_endpoint_and_log(db_session):
    endpoint = SYSTEM_ENDPOINT_MODEL(
        system_code       = "nsw_api"
        , code            = "get_masterlist"
        , name            = "Get Customs Masterlist"
        , endpoint        = "/api/v1/nsw/masterlist"
        , http_method     = "POST"
        , traffic_type    = "outbound"
        , request_timeout = 30
    )
    db_session.add(endpoint)
    db_session.commit()

    log = SYSTEM_LOG_MODEL(
        traffic_type        = "outbound"
        , system_code       = "nsw_api"
        , request_method    = "POST"
        , request_endpoint  = "/api/v1/nsw/masterlist"
        , response_code     = 200
        , response_duration = 120.5
    )
    db_session.add(log)
    db_session.commit()

    assert endpoint.id is not None
    assert log.id is not None
    assert log.traffic_type == "outbound"

