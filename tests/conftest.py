"""Pytest configuration and shared fixtures supporting both AsyncSession (domain) and Session (template)."""
from __future__ import annotations

import inspect
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.database as db_module
from app.api.deps.database import get_db as get_sync_db
from app.core.config import settings
from app.core.database import Base, get_db as get_async_db
from app.main import app

# Disable external background audit side-effects unless explicitly tested
settings.ENV                     = "testing"
settings.ENABLE_ACCESS_AUDIT_LOG = False


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(36)"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# ── 1. Synchronous SQLite In-Memory Engine (Template Models & Sync Endpoints) ─
SYNC_TEST_DATABASE_URL = "sqlite:///:memory:"

sync_test_engine = create_engine(
    SYNC_TEST_DATABASE_URL
    , connect_args = {"check_same_thread": False}
    , poolclass    = StaticPool
)

SyncTestingSessionLocal = sessionmaker(
    bind         = sync_test_engine
    , autocommit = False
    , autoflush  = False
)


@event.listens_for(sync_test_engine, "connect")
def attach_sync_sqlite_schemas(dbapi_connection, connection_record):
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS auth")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS base_data")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS track")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS public")


# ── 2. Async SQLite In-Memory Engine (Clothing Store Domain Async Endpoints) ──
ASYNC_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    ASYNC_TEST_DATABASE_URL
    , echo         = False
    , connect_args = {"check_same_thread": False}
    , poolclass    = StaticPool
)

TestSessionLocal = async_sessionmaker(
    test_engine
    , class_           = AsyncSession
    , expire_on_commit = False
)


@event.listens_for(test_engine.sync_engine, "connect")
def attach_async_sqlite_schemas(dbapi_connection, connection_record):
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS auth")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS base_data")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS track")
    dbapi_connection.execute("ATTACH DATABASE ':memory:' AS public")


@pytest.fixture(scope="session", autouse=True)
def setup_sync_test_db():
    Base.metadata.create_all(bind=sync_test_engine)
    yield
    Base.metadata.drop_all(bind=sync_test_engine)


@pytest.fixture
def db_session() -> Session:
    connection  = sync_test_engine.connect()
    transaction = connection.begin()
    session     = SyncTestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class _NoCloseSessionProxy:
    def __init__(self, real_session):
        self._session = real_session

    def __getattr__(self, name):
        if name == "close":
            return lambda: None
        return getattr(self._session, name)


@pytest.fixture
def sync_client(db_session: Session, monkeypatch):
    def _override_get_sync_db():
        yield db_session

    monkeypatch.setattr(db_module, "get_static_session", lambda: _NoCloseSessionProxy(db_session))
    monkeypatch.setattr("app.middleware.access.get_static_session", lambda: _NoCloseSessionProxy(db_session))

    app.dependency_overrides[get_sync_db] = _override_get_sync_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession, db_session: Session, monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_async_db():
        yield db

    def override_get_sync_db():
        yield db_session

    monkeypatch.setattr(db_module, "get_static_session", lambda: _NoCloseSessionProxy(db_session))
    monkeypatch.setattr("app.middleware.access.get_static_session", lambda: _NoCloseSessionProxy(db_session))

    app.dependency_overrides[get_async_db] = override_get_async_db
    app.dependency_overrides[get_sync_db]  = override_get_sync_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
