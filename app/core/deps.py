from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate access token; return the authenticated user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise unauthorized

    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise unauthorized

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise unauthorized

    repo = UserRepository(db)
    user = await repo.get_by_id(UUID(user_id))
    if not user or user.status != "ACTIVE":
        raise unauthorized

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    return current_user


def require_permission(permission_code: str):
    """Dependency factory that checks if the current user has a specific permission."""

    async def _check(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        user_permissions = {
            perm.code
            for role in current_user.roles
            for perm in role.permissions
        }
        if permission_code not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires '{permission_code}'",
            )
        return current_user

    return _check
