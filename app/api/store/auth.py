"""Store lane auth dependencies.

Two auth modes:
  - get_optional_customer  — soft auth, returns None if not authenticated
  - require_customer       — hard auth, raises 401 if not authenticated

Store customers authenticate with the same JWT system as staff but are
stored in the users table with the CUSTOMER role.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_access_token
from app.core.database import get_db
from app.models import User
from app.repositories.user_repository import UserRepository
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

bearer_scheme = HTTPBearer(auto_error=False)


async def get_optional_customer(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Returns the authenticated customer user, or None if not logged in."""
    if not credentials:
        return None
    payload = verify_access_token(credentials.credentials)
    if not payload:
        return None
    user_id: str | None = payload.get("sub")
    if not user_id:
        return None
    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    if not user or user.status != "ACTIVE":
        return None
    # Verify this user has CUSTOMER role
    role_names = {r.name for r in user.roles}
    if "CUSTOMER" not in role_names:
        return None
    return user


async def require_customer(
    customer: Annotated[User | None, Depends(get_optional_customer)],
) -> User:
    """Raises 401 if the request is not from an authenticated customer."""
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return customer
