from typing import AsyncGenerator, Generator, Optional
import uuid
from datetime import datetime

from sqlalchemy import create_engine, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, Mapped, mapped_column, synonym, declared_attr

from app.core.config import settings


def _resolve_dialect(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        try:
            import psycopg2  # noqa: F401
            return url
        except ImportError:
            return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return url


# ── Synchronous engine (for template services, Alembic migrations, and background jobs) ──
sync_engine = create_engine(
    _resolve_dialect(settings.DATABASE_URL)
    , pool_size     = 10
    , max_overflow  = 20
    , pool_timeout  = 10
    , pool_recycle  = 1800
    , pool_pre_ping = True
    , echo          = False
)

engine = sync_engine

SyncSessionLocal = sessionmaker(
    bind            = sync_engine
    , autoflush     = False
    , autocommit    = False
)

SessionLocal = SyncSessionLocal

# ── Async engine (for async FastAPI domain endpoints) ─────────────────────────
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL
    , pool_pre_ping = True
    , pool_size     = 10
    , max_overflow  = 20
    , echo          = False
)

AsyncSessionLocal = async_sessionmaker(
    async_engine
    , class_           = AsyncSession
    , expire_on_commit = False
    , autocommit       = False
    , autoflush        = False
)


# ── Declarative Base Model ────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class TEMPLATE_BASE_MODEL(Base):
    """Abstract base for enterprise template models with standardized audit columns."""

    __abstract__ = True

    created_datetime : Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=datetime.utcnow, server_default=func.now())
    deleted_datetime : Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    updated_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)
    deleted_by       : Mapped[Optional[str]]      = mapped_column(String(100), nullable=True)

    @declared_attr
    def created_at(cls):
        return synonym("created_datetime")

    @declared_attr
    def updated_at(cls):
        return synonym("updated_datetime")


class TIMESTAMP_MIXIN:
    """Legacy timestamp mixin (maps to created_datetime and updated_datetime)."""
    @declared_attr
    def created_at(cls):
        return synonym("created_datetime")

    @declared_attr
    def updated_at(cls):
        return synonym("updated_datetime")


class UUID_BASE_MODEL(TEMPLATE_BASE_MODEL):
    """Abstract base with UUID PK, status_code, and standardized audit columns."""

    __abstract__ = True

    id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True)
        , primary_key = True
        , default     = uuid.uuid4
    )
    status_code : Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    @declared_attr
    def status(cls):
        return synonym("status_code")

    @declared_attr
    def created_at(cls):
        return synonym("created_datetime")

    @declared_attr
    def updated_at(cls):
        return synonym("updated_datetime")


# Backward-compatible aliases
TimestampMixin = TIMESTAMP_MIXIN
UUIDBase       = UUID_BASE_MODEL


# ── Dependencies ──────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_db() -> Generator[Session, None, None]:
    """
    Dependency injection generator yielding an active synchronous SQLAlchemy DB session.
    Automatically closes session upon request completion.
    """
    db = SyncSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_static_session() -> Session:
    """
    Create a standalone SQLAlchemy session for background tasks, threads, or scripts.
    Caller is responsible for calling session.close().
    """
    return SyncSessionLocal()


getSession       = get_sync_db
getStaticSession = get_static_session
