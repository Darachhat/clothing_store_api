"""User and Role Administration API endpoints."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.security import hash_password
from app.core.utils.phone_utils import normalize_phone_number
from app.models import AuditLog, Permission, Role, User
from app.repositories.user_repository import (
    PermissionRepository,
    RefreshTokenRepository,
    RoleRepository,
    UserRepository,
)
from app.schemas.audit_schema import AUDIT_LOG_RESPONSE_SCHEMA
from app.schemas.auth_schema import (
    PERMISSION_RESPONSE_SCHEMA,
    ROLE_CREATE_SCHEMA,
    ROLE_RESPONSE_SCHEMA,
    ROLE_UPDATE_SCHEMA,
    USER_CREATE_SCHEMA,
    USER_RESPONSE_SCHEMA,
    USER_UPDATE_SCHEMA,
)
from app.services.audit_service import AUDIT_SERVICE

users_router = APIRouter(prefix="/users", tags=["User Administration"])
roles_router = APIRouter(prefix="/roles", tags=["Role & Permission Administration"])


# ── User Endpoints ────────────────────────────────────────────────────────────
@users_router.get("", response_model=list[USER_RESPONSE_SCHEMA], include_in_schema=False)
@users_router.get("/", response_model=list[USER_RESPONSE_SCHEMA])
async def list_users(
    branch_id: UUID | None = None,
    user_status: str | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Search by name, username, email, phone, or Telegram ID"),
    role: str | None = Query(None, description="Filter by role name"),
    telegram_linked: bool | None = Query(None, description="Filter by Telegram linked status"),
    phone_verified: bool | None = Query(None, description="Filter by phone verification status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> list[User]:
    repo = UserRepository(db)
    users = await repo.list_users(
        skip=skip,
        limit=limit,
        branch_id=branch_id,
        status=user_status,
        search=search,
        role=role,
        telegram_linked=telegram_linked,
        phone_verified=phone_verified,
    )
    return users


@users_router.post("", response_model=USER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@users_router.post("/", response_model=USER_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: USER_CREATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    if await repo.username_exists(payload.username.lower().strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    if await repo.email_exists(payload.email.lower().strip()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    normalized_phone: str | None = None
    if payload.phone_number and payload.phone_number.strip():
        try:
            normalized_phone = normalize_phone_number(payload.phone_number)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if normalized_phone and await repo.phone_number_exists(normalized_phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number is already linked to another user account",
            )

    # Fetch assigned roles
    roles: list[Role] = []
    if payload.role_ids:
        role_stmt = select(Role).where(Role.id.in_(payload.role_ids))
        roles_result = await db.execute(role_stmt)
        roles = list(roles_result.scalars().all())

    caller_role_names = {r.name for r in (current_user.roles or [])}
    if any(r.name == "ADMIN" for r in roles) and "ADMIN" not in caller_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN users can assign the ADMIN role",
        )

    user = User(
        username=payload.username.lower().strip(),
        email=payload.email.lower().strip(),
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        employee_code=payload.employee_code,
        branch_id=payload.branch_id,
        phone_number=normalized_phone,
        phone_verified_at=datetime.now(UTC) if (normalized_phone and payload.phone_verified) else None,
        status=payload.status_code.upper() if payload.status_code else "ACTIVE",
        roles=roles,
    )
    db.add(user)
    await db.flush()
    await AUDIT_SERVICE.record(
        db,
        action="USER_CREATED",
        entity_type="user",
        entity_id=user.id,
        user_id=current_user.id,
        new_data={
            "username": user.username,
            "roles": [r.name for r in roles],
            "phone_number": user.phone_number,
            "phone_verified": user.phone_verified,
        },
    )
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


@users_router.get("/{user_id}/role-history", response_model=list[AUDIT_LOG_RESPONSE_SCHEMA])
async def get_user_role_history(
    user_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("user.manage")),
) -> list[AUDIT_LOG_RESPONSE_SCHEMA]:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    stmt = (
        select(AuditLog)
        .where(
            AuditLog.entity_type == "user",
            AuditLog.entity_id == user_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = list(res.scalars().all())
    return [AUDIT_LOG_RESPONSE_SCHEMA.model_validate(item) for item in logs]


@users_router.patch("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
@users_router.put("/{user_id}", response_model=USER_RESPONSE_SCHEMA)
async def update_user(
    user_id: UUID,
    payload: USER_UPDATE_SCHEMA,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    caller_role_names = {r.name for r in (current_user.roles or [])}
    old_status = user.status
    old_roles = [r.name for r in (user.roles or [])]
    old_role_ids = {r.id for r in (user.roles or [])}
    old_phone = user.phone_number
    old_telegram_id = user.telegram_id

    if "ADMIN" in old_roles and "ADMIN" not in caller_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN users can modify an ADMIN account",
        )

    if current_user.id == user_id and payload.status is not None and payload.status.upper() != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    if payload.email and payload.email.lower().strip() != user.email:
        if await repo.email_exists(payload.email.lower().strip(), exclude_user_id=user.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")
        user.email = payload.email.lower().strip()

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.employee_code is not None:
        user.employee_code = payload.employee_code
    if payload.branch_id is not None:
        user.branch_id = payload.branch_id
    if payload.status is not None:
        user.status = payload.status.upper()
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    # Phone number management
    if payload.unlink_phone:
        user.phone_number = None
        user.phone_verified_at = None
    elif payload.phone_number is not None:
        raw_phone = payload.phone_number.strip()
        if not raw_phone:
            user.phone_number = None
            user.phone_verified_at = None
        else:
            try:
                norm_phone = normalize_phone_number(raw_phone)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            if norm_phone and await repo.phone_number_exists(norm_phone, exclude_user_id=user.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number is already linked to another user account",
                )
            phone_changed = norm_phone != user.phone_number
            user.phone_number = norm_phone
            if payload.phone_verified is True:
                user.phone_verified_at = user.phone_verified_at or datetime.now(UTC)
            elif payload.phone_verified is False or phone_changed:
                user.phone_verified_at = None
    elif payload.phone_verified is not None and user.phone_number:
        user.phone_verified_at = (user.phone_verified_at or datetime.now(UTC)) if payload.phone_verified else None

    # Telegram unlinking
    if payload.unlink_telegram:
        user.telegram_id = None
        user.telegram_username = None
        user.telegram_photo_url = None
        user.telegram_linked_at = None

    # Role assignments
    roles_changed = False
    if payload.role_ids is not None:
        requested_role_ids = set(payload.role_ids)
        if current_user.id == user_id and requested_role_ids != old_role_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Users cannot modify their own role assignments",
            )
        if payload.role_ids:
            role_stmt = select(Role).where(Role.id.in_(payload.role_ids))
            roles_result = await db.execute(role_stmt)
            new_roles = list(roles_result.scalars().all())
        else:
            new_roles = []

        new_role_names = {r.name for r in new_roles}
        if ("ADMIN" in new_role_names or "ADMIN" in old_roles) and "ADMIN" not in caller_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only ADMIN users can assign or revoke the ADMIN role",
            )

        if requested_role_ids != old_role_ids:
            roles_changed = True
            user.roles = new_roles

    new_roles_list = [r.name for r in (user.roles or [])]

    # Revoke active refresh tokens whenever roles change or account is deactivated
    if roles_changed or user.status != "ACTIVE":
        await RefreshTokenRepository(db).revoke_all_for_user(user.id)

    if roles_changed:
        added_roles = [r for r in new_roles_list if r not in old_roles]
        revoked_roles = [r for r in old_roles if r not in new_roles_list]
        await AUDIT_SERVICE.record(
            db,
            action="USER_ROLES_UPDATED",
            entity_type="user",
            entity_id=user.id,
            user_id=current_user.id,
            old_data={"roles": old_roles},
            new_data={
                "roles": new_roles_list,
                "added_roles": added_roles,
                "revoked_roles": revoked_roles,
            },
        )

    if old_status != user.status:
        status_action = "USER_ACTIVATED" if user.status == "ACTIVE" else "USER_DEACTIVATED"
        await AUDIT_SERVICE.record(
            db,
            action=status_action,
            entity_type="user",
            entity_id=user.id,
            user_id=current_user.id,
            old_data={"status": old_status},
            new_data={"status": user.status, "username": user.username},
        )

    await AUDIT_SERVICE.record(
        db,
        action="USER_UPDATED",
        entity_type="user",
        entity_id=user.id,
        user_id=current_user.id,
        old_data={
            "status": old_status,
            "roles": old_roles,
            "phone_number": old_phone,
            "telegram_id": old_telegram_id,
        },
        new_data={
            "status": user.status,
            "roles": new_roles_list,
            "phone_number": user.phone_number,
            "phone_verified": user.phone_verified,
            "telegram_id": user.telegram_id,
        },
    )
    await db.commit()
    return await repo.get_by_id(user.id)


@users_router.post("/{user_id}/activate", response_model=USER_RESPONSE_SCHEMA)
async def activate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("user.manage")),
) -> User:
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_status = user.status
    user.status = "ACTIVE"
    await AUDIT_SERVICE.record(
        db,
        action="USER_ACTIVATED",
        entity_type="user",
        entity_id=user.id,
        user_id=current_user.id,
        old_data={"status": old_status},
        new_data={"status": "ACTIVE", "username": user.username},
    )
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

    caller_role_names = {r.name for r in (current_user.roles or [])}
    target_role_names = {r.name for r in (user.roles or [])}
    if "ADMIN" in target_role_names and "ADMIN" not in caller_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN users can deactivate an ADMIN account",
        )

    old_status = user.status
    user.status = "INACTIVE"
    await RefreshTokenRepository(db).revoke_all_for_user(user.id)
    await AUDIT_SERVICE.record(
        db,
        action="USER_DEACTIVATED",
        entity_type="user",
        entity_id=user.id,
        user_id=current_user.id,
        old_data={"status": old_status},
        new_data={"status": "INACTIVE", "username": user.username},
    )
    await db.commit()
    return await repo.get_by_id(user.id)


# ── Role Endpoints ────────────────────────────────────────────────────────────
@roles_router.get("", response_model=list[ROLE_RESPONSE_SCHEMA], include_in_schema=False)
@roles_router.get("/", response_model=list[ROLE_RESPONSE_SCHEMA])
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


@roles_router.post("", response_model=ROLE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@roles_router.post("/", response_model=ROLE_RESPONSE_SCHEMA, status_code=status.HTTP_201_CREATED)
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
    current_user: User = Depends(require_permission("user.manage")),
) -> Role:
    repo = RoleRepository(db)
    role = await repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role.is_system and payload.name and payload.name.upper() != role.name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rename system role")

    old_perms = [p.code for p in (role.permissions or [])]
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

    await AUDIT_SERVICE.record(
        db,
        action="ROLE_UPDATED",
        entity_type="role",
        entity_id=role.id,
        user_id=current_user.id,
        old_data={"name": role.name, "permissions": old_perms},
        new_data={"name": role.name, "permissions": [p.code for p in (role.permissions or [])]},
    )
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
