"""Inbound system/client credential gate (X-System-Authorization / X-API-KEY)."""
from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.utils.crypto_utils import hash_api_key
from app.models import (
    CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , SYSTEM_CLIENT_MODEL
    , SYSTEM_MODEL
)
from app.schemas.auth_schema import SYSTEM_CREDENTIAL_CREATE_SCHEMA
from app.services.system_auth_service import hash_inbound_secret
from app.services.system_service import SYSTEM_SERVICE

HEADER   = settings.SYSTEM_AUTH_HEADER_NAME
PROTECTED = "/api/store/v1/catalog/products"


def _basic(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def _make_system(db: Session, code: str, status: str = "active") -> None:
    db.add(SYSTEM_MODEL(code=code, name=code, scope="internal", status_code=status))
    db.commit()


def _make_basic(db: Session, system: str, user: str, secret: str, status: str = "active", stored: str | None = None) -> None:
    db.add(CREDENTIAL_BASIC_MODEL(
        system_code=system, traffic_type="inbound", username=user,
        password=stored if stored is not None else hash_inbound_secret(secret), status_code=status,
    ))
    db.commit()


@pytest.fixture
def enforce(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_AUTH_MODE", "enforce")


# ── enforce mode ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_credential_rejected(enforce, client: AsyncClient) -> None:
    assert (await client.get(PROTECTED)).status_code == 401


@pytest.mark.asyncio
async def test_public_paths_stay_open(enforce, client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/api/docs")).status_code == 200


@pytest.mark.asyncio
async def test_valid_basic_credential_passes(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "web_store_front")
    _make_basic(db_session, "web_store_front", "web_store_front", "s3cret-value")
    resp = await client.get(PROTECTED, headers={HEADER: _basic("web_store_front", "s3cret-value")})
    assert resp.status_code != 401, resp.text


@pytest.mark.asyncio
async def test_wrong_secret_rejected(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "admin_front")
    _make_basic(db_session, "admin_front", "admin_front", "right")
    resp = await client.get(PROTECTED, headers={HEADER: _basic("admin_front", "wrong")})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_plaintext_stored_secret_is_never_accepted(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "legacy")
    _make_basic(db_session, "legacy", "legacy", "plain", stored="plain")  # legacy plaintext row
    resp = await client.get(PROTECTED, headers={HEADER: _basic("legacy", "plain")})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_revoked_credential_and_inactive_system_rejected(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "revoked_sys")
    _make_basic(db_session, "revoked_sys", "u1", "pw", status="inactive")
    _make_system(db_session, "dead_sys", status="inactive")
    _make_basic(db_session, "dead_sys", "u2", "pw")
    assert (await client.get(PROTECTED, headers={HEADER: _basic("u1", "pw")})).status_code == 401
    assert (await client.get(PROTECTED, headers={HEADER: _basic("u2", "pw")})).status_code == 401


@pytest.mark.asyncio
async def test_outbound_credentials_cannot_authenticate_inbound(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "aba")
    db_session.add(CREDENTIAL_BASIC_MODEL(
        system_code="aba", traffic_type="outbound", username="aba", password=hash_inbound_secret("pw"), status_code="active"))
    db_session.commit()
    assert (await client.get(PROTECTED, headers={HEADER: _basic("aba", "pw")})).status_code == 401


@pytest.mark.asyncio
async def test_bearer_credential(enforce, client: AsyncClient, db_session: Session) -> None:
    _make_system(db_session, "mobile")
    db_session.add(CREDENTIAL_BEARER_MODEL(
        system_code="mobile", traffic_type="inbound", header_name=HEADER, token_prefix="Bearer",
        token_value=hash_inbound_secret("tok-123"), status_code="active"))
    db_session.commit()
    assert (await client.get(PROTECTED, headers={HEADER: "Bearer tok-123"})).status_code != 401
    assert (await client.get(PROTECTED, headers={HEADER: "Bearer nope"})).status_code == 401


@pytest.mark.asyncio
async def test_api_key_with_client_id(enforce, client: AsyncClient, db_session: Session) -> None:
    db_session.add(SYSTEM_CLIENT_MODEL(code="erp", name="ERP", api_key_hash=hash_api_key("key-1"), status_code="active"))
    db_session.commit()
    ok  = await client.get(PROTECTED, headers={"X-API-KEY": "key-1", "X-CLIENT-ID": "erp"})
    bad = await client.get(PROTECTED, headers={"X-API-KEY": "key-2", "X-CLIENT-ID": "erp"})
    no_id = await client.get(PROTECTED, headers={"X-API-KEY": "key-1"})
    assert ok.status_code != 401
    assert bad.status_code == 401
    assert no_id.status_code == 401


@pytest.mark.asyncio
async def test_user_jwt_in_authorization_is_not_a_system_credential(enforce, client: AsyncClient) -> None:
    resp = await client.get(PROTECTED, headers={"Authorization": "Bearer some.user.jwt"})
    assert resp.status_code == 401  # still needs the system credential


# ── audit / off modes ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_audit_mode_never_blocks(monkeypatch, client: AsyncClient) -> None:
    monkeypatch.setattr(settings, "SYSTEM_AUTH_MODE", "audit")
    assert (await client.get(PROTECTED)).status_code != 401
    assert (await client.get(PROTECTED, headers={HEADER: _basic("x", "y")})).status_code != 401


@pytest.mark.asyncio
async def test_default_mode_is_enforce_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SYSTEM_AUTH_MODE", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    assert settings.system_auth_mode == "enforce"
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert settings.system_auth_mode == "audit"


# ── credential creation ──────────────────────────────────────────────────────

def test_inbound_credential_is_hashed_and_secret_shown_once(db_session: Session) -> None:
    _make_system(db_session, "cashier_front")
    out = SYSTEM_SERVICE.create_credential(db_session, SYSTEM_CREDENTIAL_CREATE_SCHEMA(
        system_code="cashier_front", traffic_type="inbound", auth_type_code="basic", username="cashier_front"))
    assert out.generated_secret and out.authorization_header_value.startswith("Basic ")
    row = db_session.query(CREDENTIAL_BASIC_MODEL).filter_by(system_code="cashier_front").one()
    assert row.password.startswith("sha256:") and out.generated_secret not in row.password

