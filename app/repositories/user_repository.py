"""User repository with authentication-specific queries."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

from app.core.utils.phone_utils import get_equivalent_phone_formats, normalize_phone_number
from app.models import PERMISSION_MODEL, RefreshToken, ROLE_MODEL, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db) -> None:
        super().__init__(User, db)

    async def get_by_id(self, id: UUID) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.id == id)
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.username == username)
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_id(self, telegram_id: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(User.telegram_id == str(telegram_id).strip())
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_phone_number(self, phone_number: str) -> User | None:
        try:
            variants = get_equivalent_phone_formats(phone_number)
        except ValueError:
            variants = [phone_number.strip()]
        result = await self.db.execute(
            select(User)
            .where(User.phone_number.in_(variants))
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
        )
        return result.scalar_one_or_none()

    async def username_exists(self, username: str) -> bool:
        result = await self.db.execute(
            select(User.id).where(User.username == username)
        )
        return result.scalar_one_or_none() is not None

    async def email_exists(self, email: str, exclude_user_id: UUID | None = None) -> bool:
        stmt = select(User.id).where(User.email == email)
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def telegram_id_exists(self, telegram_id: str, exclude_user_id: UUID | None = None) -> bool:
        stmt = select(User.id).where(User.telegram_id == str(telegram_id).strip())
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def phone_number_exists(self, phone_number: str, exclude_user_id: UUID | None = None) -> bool:
        try:
            variants = get_equivalent_phone_formats(phone_number)
        except ValueError:
            variants = [phone_number.strip()]
        stmt = select(User.id).where(User.phone_number.in_(variants))
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _apply_filters(
        self,
        stmt,
        *,
        branch_id: UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        role: str | None = None,
        telegram_linked: bool | None = None,
        phone_verified: bool | None = None,
    ):
        if branch_id:
            stmt = stmt.where(User.branch_id == branch_id)
        if status:
            stmt = stmt.where(User.status == status.upper())
        if role:
            stmt = stmt.where(User.roles.any(ROLE_MODEL.name == role.upper().strip()))
        if telegram_linked is True:
            stmt = stmt.where(User.telegram_id.is_not(None))
        elif telegram_linked is False:
            stmt = stmt.where(User.telegram_id.is_(None))
        if phone_verified is True:
            stmt = stmt.where(User.phone_verified_at.is_not(None))
        elif phone_verified is False:
            stmt = stmt.where(User.phone_verified_at.is_(None))
        if search and search.strip():
            term = search.strip()
            pattern = f"%{term}%"
            clauses = [
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
                User.employee_code.ilike(pattern),
                User.phone_number.ilike(pattern),
                User.telegram_username.ilike(pattern),
                User.telegram_id.ilike(pattern),
            ]
            try:
                norm_phone = normalize_phone_number(term)
                if norm_phone:
                    clauses.append(User.phone_number == norm_phone)
            except ValueError:
                pass
            stmt = stmt.where(or_(*clauses))
        return stmt

    async def list_users(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        branch_id: UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        role: str | None = None,
        telegram_linked: bool | None = None,
        phone_verified: bool | None = None,
    ) -> list[User]:
        stmt = (
            select(User)
            .options(selectinload(User.roles).selectinload(ROLE_MODEL.permissions))
            .order_by(User.created_at.desc())
        )
        stmt = self._apply_filters(
            stmt,
            branch_id=branch_id,
            status=status,
            search=search,
            role=role,
            telegram_linked=telegram_linked,
            phone_verified=phone_verified,
        )
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_users(
        self,
        *,
        branch_id: UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        role: str | None = None,
        telegram_linked: bool | None = None,
        phone_verified: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(User)
        stmt = self._apply_filters(
            stmt,
            branch_id=branch_id,
            status=status,
            search=search,
            role=role,
            telegram_linked=telegram_linked,
            phone_verified=phone_verified,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()


class RoleRepository(BaseRepository[ROLE_MODEL]):
    def __init__(self, db) -> None:
        super().__init__(ROLE_MODEL, db)

    async def get_by_id(self, id: UUID) -> ROLE_MODEL | None:
        stmt = (
            select(ROLE_MODEL)
            .where(ROLE_MODEL.id == id)
            .options(selectinload(ROLE_MODEL.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> ROLE_MODEL | None:
        stmt = (
            select(ROLE_MODEL)
            .where(ROLE_MODEL.name == name)
            .options(selectinload(ROLE_MODEL.permissions))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_roles(self) -> list[ROLE_MODEL]:
        stmt = select(ROLE_MODEL).options(selectinload(ROLE_MODEL.permissions)).order_by(ROLE_MODEL.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class PermissionRepository(BaseRepository):
    def __init__(self, db) -> None:
        super().__init__(PERMISSION_MODEL, db)

    async def get_all_permissions(self):
        stmt = select(PERMISSION_MODEL).order_by(PERMISSION_MODEL.module, PERMISSION_MODEL.code)
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
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True)
        )
