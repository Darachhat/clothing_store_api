"""User and Role Administration API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.security import hash_password
from app.models import Permission, Role, User
from app.repositories.user_repository import PermissionRepository, RoleRepository, UserRepository
from app.schemas.auth_schema import (
    PERMISSION_RESPONSE_SCHEMA,
    ROLE_CREATE_SCHEMA,
    ROLE_RESPONSE_SCHEMA,
    ROLE_UPDATE_SCHEMA,
    USER_CREATE_SCHEMA,
    USER_RESPONSE_SCHEMA,
    USER_UPDATE_SCHEMA,
)

users_router = APIRouter(prefix="/users", tags=["User Administration"])
roles_router = APIRouter(prefix="/roles", tags=["Role & Permission Administration"])


# ── User Endpoints ────────────────────────────────────────────────────────────
@users_router.get("", response_model=list[USER_RESPONSE_SCHEMA])
async def list_users(
    branch_id: UUID | None = None,
    user_status: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> list[User]:
    repo = UserRepository(db)
    users = await repo.list_users(skip=skip, limit=limit, branch_id=branch_id, status=user_status)
    return users


@users_router.post("", response_model=USER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: USER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    if await repo.username_exists(payload.username.lower().strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    if await repo.email_exists(payload.email.lower().strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    # Fetch assigned roles
    roles = []
    if payload.role_ids:
        role_stmt = select(Role).where(Role.id.in_(payload.role_ids))
        roles_result = await db.execute(role_stmt)
        roles = list(roles_result.scalars().all())

    user = User(
        username=payload.username.lower().strip(),
        email=payload.email.lower().strip(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        employee_code=payload.employee_code,
        branch_id=payload.branch_id,
        status="ACTIVE",
        roles=roles,
    )
    db.add(user)
    await db.commit()
    return await repo.get_by_id(user.id)


@users_router.get("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@users_router.patch("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
@users_router.put("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
async def update_user(
    user_id: UUID,
    payload: USER_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.email and payload.email.lower().strip() != user.email:
        if await repo.email_exists(payload.email.lower().strip()):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = payload.email.lower().strip()

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.employee_code is not None:
        user.employee_code = payload.employee_code
    if payload.branch_id is not None:
        user.branch_id = payload.branch_id
    if payload.status is not None:
        user.status = payload.status
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.role_ids is not None:
        if payload.role_ids:
            role_stmt = select(Role).where(Role.id.in_(payload.role_ids))
            roles_result = await db.execute(role_stmt)
            user.roles = list(roles_result.scalars().all())
        else:
            user.roles = []

    await db.commit()
    return await repo.get_by_id(user.id)


@users_router.delete("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
) -> User:
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.status = "INACTIVE"
    await db.commit()
    return await repo.get_by_id(user.id)



# ── Role Endpoints ────────────────────────────────────────────────────────────
@roles_router.get("", response_model=list[ROLE_RESPONSE_SCHEMA])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> list[Role]:
    repo = RoleRepository(db)
    return await repo.get_all_roles()


@roles_router.get("/permissions", response_model=list[PERMISSION_RESPONSE_SCHEMA])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> list[Permission]:
    repo = PermissionRepository(db)
    return await repo.get_all_permissions()


@roles_router.post("", response_model=ROLE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: ROLE_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Role:
    repo = RoleRepository(db)
    existing = await repo.get_by_name(payload.name.upper().strip())
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")

    perms = []
    if payload.permission_ids:
        stmt = select(Permission).where(Permission.id.in_(payload.permission_ids))
        res = await db.execute(stmt)
        perms = list(res.scalars().all())

    role = Role(
        name=payload.name.upper().strip(),
        description=payload.description,
        is_system=False,
        permissions=perms,
    )
    db.add(role)
    await db.commit()
    return await repo.get_by_id(role.id)


@roles_router.patch("/{role_id}", response_model=ROLE_RESPONSE_SCHEMA)
@roles_router.put("/{role_id}", response_model=ROLE_RESPONSE_SCHEMA)
async def update_role(
    role_id: UUID,
    payload: ROLE_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Role:
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system and payload.name and payload.name.upper() != role.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rename system role")

    if payload.name:
        role.name = payload.name.upper().strip()
    if payload.description is not None:
        role.description = payload.description
    if payload.permission_ids is not None:
        if payload.permission_ids:
            stmt = select(Permission).where(Permission.id.in_(payload.permission_ids))
            res = await db.execute(stmt)
            role.permissions = list(res.scalars().all())
        else:
            role.permissions = []

    await db.commit()
    return await repo.get_by_id(role.id)


@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_role(
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> Response:
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete system role")
    await repo.delete(role)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
