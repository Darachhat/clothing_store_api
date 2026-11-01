"""
Public Schema Models: system infrastructure, Alembic tracking, or global public entities.
Schema: public
"""
from __future__ import annotations

from sqlalchemy import Column, String
from app.core.database import Base


class AlembicVersion(Base):
    """Reflects the alembic_version table maintained by Alembic in schema 'public'."""
    __tablename__ = "alembic_version"
    __table_args__ = {"schema": "public"}

    version_num = Column(String(32), primary_key=True)


ALEMBIC_VERSION_MODEL = AlembicVersion

