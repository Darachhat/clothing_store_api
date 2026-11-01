"""User repository with authentication-specific queries."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import RefreshToken, Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db) -> None:
        super().__init__(User, db)

    async def get_by_id(self, id: UUID) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.id == id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.username == username)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def username_exists(self, username: str) -> bool:
        result = await self.db.execute(
            select(User.id).where(User.username == username)
        )
        return result.scalar_one_or_none() is not None

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(
            select(User.id).where(User.email == email)
        )
        return result.scalar_one_or_none() is not None

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        branch_id: UUID | None = None,
        status: str | None = None,
    ) -> list[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .order_by(User.created_at.desc())
        )
        if branch_id:
            stmt = stmt.where(User.branch_id == branch_id)
        if status:
            stmt = stmt.where(User.status == status)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_users(
        self,
        *,
        branch_id: UUID | None = None,
        status: str | None = None,
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(User)
        if branch_id:
            stmt = stmt.where(User.branch_id == branch_id)
        if status:
            stmt = stmt.where(User.status == status)

        result = await self.db.execute(stmt)
        return result.scalar_one()


class RoleRepository(BaseRepository[Role]):
    def __init__(self, db) -> None:
        super().__init__(Role, db)

    async def get_by_id(self, id: UUID) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.id == id)
            .options(selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.name == name)
            .options(selectinload(Role.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_roles(self) -> list[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class PermissionRepository(BaseRepository):
    def __init__(self, db) -> None:
        from app.models import Permission
        super().__init__(Permission, db)

    async def get_all_permissions(self):
        from app.models import Permission
        stmt = select(Permission).order_by(Permission.module, Permission.code)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, db) -> None:
        super().__init__(RefreshToken, db)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        from sqlalchemy import update
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True)
        )

