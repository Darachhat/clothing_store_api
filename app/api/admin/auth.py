"""Admin lane — role-based auth dependency.

Enforces that only ADMIN or MANAGER roles can access admin-lane endpoints.
Wraps the shared get_current_user dependency from app.core.deps.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_active_user
from app.models.user import User

_ALLOWED_ROLES: frozenset[str] = frozenset({"ADMIN", "MANAGER"})


async def require_admin_or_manager(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Dependency: raise 403 unless the user holds ADMIN or MANAGER role."""
    user_role_names = {r.name for r in current_user.roles}
    if not (_ALLOWED_ROLES & user_role_names):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Manager role required to access this resource.",
        )
    return current_user
