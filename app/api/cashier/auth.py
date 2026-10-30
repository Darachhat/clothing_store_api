"""Cashier lane auth dependency.

Only CASHIER role (plus ADMIN acting as cashier for testing) can access
cashier-lane endpoints.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_active_user
from app.models.user import User

_ALLOWED_ROLES: frozenset[str] = frozenset({"CASHIER", "ADMIN"})


async def require_cashier(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Dependency: raise 403 unless the user holds CASHIER or ADMIN role."""
    user_role_names = {r.name for r in current_user.roles}
    if not (_ALLOWED_ROLES & user_role_names):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cashier role required to access POS endpoints.",
        )
    return current_user
