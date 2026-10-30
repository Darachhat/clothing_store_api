"""Auth schemas."""
from __future__ import annotations

from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.base import BaseSchema, UUIDSchema


class LoginRequest(BaseSchema):
    username: str
    password: str


class RefreshRequest(BaseSchema):
    refresh_token: str


class LogoutRequest(BaseSchema):
    refresh_token: str


class ChangePasswordRequest(BaseSchema):
    current_password: str
    new_password: str = Field(min_length=8)


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PermissionOut(BaseSchema):
    id: UUID
    code: str
    name: str
    module: str


class RoleOut(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    permissions: list[PermissionOut] = []


class UserOut(UUIDSchema):
    username: str
    email: str
    full_name: str
    employee_code: str | None = None
    branch_id: UUID | None = None
    status: str
    roles: list[RoleOut] = []


class LoginResponse(TokenResponse):
    user: UserOut


class UserCreate(BaseSchema):
    username: str = Field(min_length=3, max_length=100)
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    employee_code: str | None = None
    branch_id: UUID | None = None
    role_ids: list[UUID] = []


class UserUpdate(BaseSchema):
    full_name: str | None = None
    email: EmailStr | None = None
    employee_code: str | None = None
    branch_id: UUID | None = None
    status: str | None = None


class RoleCreate(BaseSchema):
    name: str
    description: str | None = None
    permission_ids: list[UUID] = []


class RoleUpdate(BaseSchema):
    name: str | None = None
    description: str | None = None
