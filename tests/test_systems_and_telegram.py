from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest

from app.core.logger import rotate_logs
from app.core.utils.crypto_utils import build_basic_auth, generate_ulid, redact_headers
from app.services.system_service import SYSTEM_SERVICE


def test_ulid_and_header_redaction():
    ulid = generate_ulid()
    assert len(ulid) == 26

    headers = {
        "Authorization"  : "Bearer secret_token"
        , "X-API-Key"    : "sk_live_123"
        , "Content-Type" : "application/json"
    }
    redacted = redact_headers(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["X-API-Key"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"


def test_auth_client_registration_and_verification(sync_client, allow_system_admin):
    # Register client
    resp = sync_client.post(
        "/api/v1/auth/clients"
        , json = {
            "code"          : "moi_client"
            , "name"        : "Ministry of Interior Client"
            , "description" : "Integration client"
        }
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["code"] == "moi_client"
    assert data["raw_api_key"].startswith("sk_live_")

    # List clients
    list_resp = sync_client.get("/api/v1/auth/clients")
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    assert any(c["code"] == "moi_client" for c in items)

    # Revoke client
    rev_resp = sync_client.put("/api/v1/auth/clients/moi_client/revoke")
    assert rev_resp.status_code == 200
    assert rev_resp.json()["data"]["status_code"] == "inactive"


def test_system_endpoint_and_credential_crud_endpoints(sync_client, allow_system_admin):
    # 1. Create System
    sys_resp = sync_client.post(
        "/api/v1/systems"
        , json = {
            "code"          : "cdc_service"
            , "name"        : "CDC Core Service"
            , "base_url"    : "https://service.cdc.gov.kh"
            , "scope"       : "external"
            , "status_code" : "active"
        }
    )
    assert sys_resp.status_code == 201
    assert sys_resp.json()["data"]["code"] == "cdc_service"

    # 2. List Systems with stats
    list_resp = sync_client.get("/api/v1/systems?search=cdc")
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert list_data["total"] >= 1
    assert list_data["stats"]["active"] >= 1

    # 3. Create Endpoint for System
    ep_resp = sync_client.post(
        "/api/v1/systems/cdc_service/endpoints"
        , json = {
            "system_code"       : "cdc_service"
            , "code"            : "lookup_invoice"
            , "name"            : "Lookup Invoice Endpoint"
            , "endpoint"        : "/api/v1/lookup"
            , "http_method"     : "POST"
            , "traffic_type"    : "outbound"
            , "request_timeout" : 15
        }
    )
    assert ep_resp.status_code == 201
    ep_id = ep_resp.json()["data"]["id"]

    # 4. Create Outbound Basic Credential for System
    cred_resp = sync_client.post(
        "/api/v1/systems/cdc_service/credentials"
        , json = {
            "system_code"      : "cdc_service"
            , "traffic_type"   : "outbound"
            , "auth_type_code" : "basic"
            , "username"       : "cdc_user"
            , "password"       : "cdc_pass"
        }
    )
    assert cred_resp.status_code == 201

    # 5. Update Endpoint
    upd_ep = sync_client.put(
        f"/api/v1/systems/endpoints/{ep_id}"
        , json = {"request_timeout": 45}
    )
    assert upd_ep.status_code == 200
    assert upd_ep.json()["data"]["request_timeout"] == 45


@pytest.mark.asyncio
async def test_system_service_call_endpoint_outbound(db_session):
    from app.schemas.auth_schema import (
        SYSTEM_CREATE_SCHEMA
        , SYSTEM_CREDENTIAL_CREATE_SCHEMA
        , SYSTEM_ENDPOINT_CREATE_SCHEMA
    )

    SYSTEM_SERVICE.create_system(
        db     = db_session
        , data = SYSTEM_CREATE_SCHEMA(
            code       = "qip_sys"
            , name     = "QIP System"
            , base_url = "https://qip.gov.kh"
        )
    )
    SYSTEM_SERVICE.create_endpoint(
        db     = db_session
        , data = SYSTEM_ENDPOINT_CREATE_SCHEMA(
            system_code   = "qip_sys"
            , code        = "confirm"
            , name        = "Confirm Endpoint"
            , endpoint    = "/api/v1/confirm"
            , http_method = "POST"
        )
    )
    SYSTEM_SERVICE.create_credential(
        db     = db_session
        , data = SYSTEM_CREDENTIAL_CREATE_SCHEMA(
            system_code      = "qip_sys"
            , traffic_type   = "outbound"
            , auth_type_code = "basic"
            , username       = "qip_user"
            , password       = "qip_secret"
        )
    )

    with patch("app.services.system_service.HTTP_CLIENT.request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"status": "CONFIRMED"}
        result = await SYSTEM_SERVICE.call_endpoint(
            db              = db_session
            , system_code   = "qip_sys"
            , endpoint_code = "confirm"
            , json_data     = {"ref": "123"}
        )
        assert result == {"status": "CONFIRMED"}
        mock_req.assert_called_once()
        called_kwargs = mock_req.call_args.kwargs
        assert called_kwargs["url"] == "https://qip.gov.kh/api/v1/confirm"
        assert called_kwargs["headers"]["Authorization"] == build_basic_auth("qip_user", "qip_secret")


def test_telegram_bot_and_chat_crud_and_send(sync_client, db_session, allow_system_admin):
    # 1. Create Telegram Bot
    bot_resp = sync_client.post(
        "/api/v1/telegram/bots"
        , json = {
            "code"       : "ops_bot"
            , "name"     : "Ops Alert Bot"
            , "username" : "ops_alert_bot"
            , "token"    : "123456:ABC-DEF"
        }
    )
    assert bot_resp.status_code == 201
    bot_id = bot_resp.json()["data"]["id"]

    # 2. Create Telegram Chat
    chat_resp = sync_client.post(
        "/api/v1/telegram/chats"
        , json = {
            "code"                : "ops_channel"
            , "telegram_bot_code" : "ops_bot"
            , "name"              : "Ops Alert Channel"
            , "chat_type"         : "topic"
            , "chat_id"           : "-100123456789"
            , "thread_id"         : "42"
        }
    )
    assert chat_resp.status_code == 201
    chat_id = chat_resp.json()["data"]["id"]

    # 3. List Bots & Chats
    assert sync_client.get("/api/v1/telegram/bots").status_code == 200
    assert sync_client.get("/api/v1/telegram/chats").status_code == 200

    # 4. Send Telegram Notification via API (mocking HTTP_CLIENT.request)
    with patch(
        "app.core.utils.telegram_utils.HTTP_CLIENT.request"
        , new_callable = AsyncMock
        , return_value = {"ok": True, "result": {"message_id": 999}}
    ):
        send_resp = sync_client.post(
            "/api/v1/telegram/send"
            , json = {
                "chat_code"    : "ops_channel"
                , "text"       : "<b>Deployment Complete</b>"
                , "parse_mode" : "HTML"
            }
        )
        assert send_resp.status_code == 200
        assert send_resp.json()["data"]["ok"] is True

    # Verify track.telegram_outbound record was written
    outbound_logs = sync_client.get("/api/v1/logs/telegram-outbound?telegram_chat_code=ops_channel").json()["data"]
    assert len(outbound_logs) >= 1
    assert outbound_logs[0]["is_success"] is True
    assert outbound_logs[0]["telegram_message_id"] == "999"

    # 5. Soft-delete Chat & Bot
    assert sync_client.delete(f"/api/v1/telegram/chats/{chat_id}").status_code == 204
    assert sync_client.delete(f"/api/v1/telegram/bots/{bot_id}").status_code == 204


def test_log_rotation_archiving(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    app_log = log_dir / "app.log"
    app_log.write_text(
        "2020-01-01 10:00:00 | INFO     | app:main:1 - Old log line\n"
        "2099-12-31 10:00:00 | INFO     | app:main:2 - Future/today log line\n"
        , encoding = "utf-8"
    )

    summary = rotate_logs(log_dir=log_dir, retention_days=36500)
    assert summary["archived_lines"] == 1
    assert "2020-01-01-app.log" in summary["archived_files"]
    assert (log_dir / "archived" / "2020-01-01-app.log").exists()
    remaining = app_log.read_text(encoding="utf-8")
    assert "2020-01-01" not in remaining
    assert "2099-12-31" in remaining

