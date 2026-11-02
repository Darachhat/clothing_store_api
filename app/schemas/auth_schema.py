"""Authentication and authorization schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import AliasChoices, BaseModel, EmailStr, Field, model_validator

from app.schemas.base_schema import STATS_SUMMARY_SCHEMA


# ── System Client Schemas ─────────────────────────────────────────────────────

class SYSTEM_CLIENT_CREATE_SCHEMA(BaseModel):
    code        : str           = Field(..., max_length=100, examples=["moi_api"])
    name        : str           = Field(..., max_length=255, examples=["Ministry of Interior API Client"])
    description : Optional[str] = Field(None)


class SYSTEM_CLIENT_RESPONSE_SCHEMA(BaseModel):
    id          : uuid.UUID
    code        : str
    name        : str
    status_code : str
    description : Optional[str] = None

    model_config = {"from_attributes": True}


class API_KEY_CREATED_SCHEMA(BaseModel):
    code        : str
    raw_api_key : str = Field(..., description="Copy this API key immediately; it will not be shown again.")


# ── System (auth.system) Schemas ──────────────────────────────────────────────

class SYSTEM_CREATE_SCHEMA(BaseModel):
    code              : str           = Field(..., max_length=100, examples=["owsm_api"])
    name              : str           = Field(..., max_length=255, examples=["Ministry of Interior API"])
    description       : Optional[str] = Field(default=None)
    base_url          : Optional[str] = Field(default=None, max_length=500)
    scope             : str           = Field(default="external", max_length=50)
    is_encrypted_body : bool          = Field(default=False)
    status_code       : str           = Field(default="active", max_length=10)


class SYSTEM_UPDATE_SCHEMA(BaseModel):
    name              : Optional[str]  = Field(default=None, max_length=255)
    description       : Optional[str]  = Field(default=None)
    base_url          : Optional[str]  = Field(default=None, max_length=500)
    scope             : Optional[str]  = Field(default=None, max_length=50)
    is_encrypted_body : Optional[bool] = Field(default=None)
    status_code       : Optional[str]  = Field(default=None, max_length=10)


class SYSTEM_RESPONSE_SCHEMA(BaseModel):
    id                : uuid.UUID
    code              : str
    name              : str
    description       : Optional[str]      = None
    base_url          : Optional[str]      = None
    scope             : str
    is_encrypted_body : bool
    status_code       : str
    created_datetime  : Optional[datetime] = None
    updated_datetime  : Optional[datetime] = None

    model_config = {"from_attributes": True}


class SYSTEM_LIST_OUT_SCHEMA(BaseModel):
    items : List[SYSTEM_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int
    stats : STATS_SUMMARY_SCHEMA


# ── System Credential Schemas ─────────────────────────────────────────────────

class SYSTEM_CREDENTIAL_CREATE_SCHEMA(BaseModel):
    traffic_type   : str                      = Field(..., examples=["inbound", "outbound"])
    auth_type_code : str                      = Field(..., examples=["basic", "bearer", "api_key", "oauth2"])
    status_code    : str                      = Field(default="active", max_length=10)
    system_code    : Optional[str]            = None
    username       : Optional[str]            = None
    password       : Optional[str]            = None
    secret         : Optional[str]            = None
    token          : Optional[str]            = None
    api_key        : Optional[str]            = None
    description    : Optional[str]            = None
    details        : Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _gather_extra_details(cls, data: Any) -> Any:
        if isinstance(data, dict):
            out = dict(data)
            auth_t = out.get("auth_type_code") or out.get("auth_type")
            if auth_t:
                out["auth_type_code"] = auth_t
                out["auth_type"] = auth_t
            details = dict(out.get("details") or {})
            for k in ("username", "password", "secret", "token", "api_key", "client_id", "client_secret"):
                if k in out and out[k] is not None:
                    details[k] = out[k]
            out["details"] = details
            return out
        return data

    @property
    def auth_type(self) -> str:
        return self.auth_type_code


class SYSTEM_CREDENTIAL_RESPONSE_SCHEMA(BaseModel):
    id                         : uuid.UUID
    system_code                : str
    traffic_type               : str
    auth_type                  : Optional[str]            = None
    auth_type_code             : Optional[str]            = None
    status_code                : str
    details                    : Optional[Dict[str, Any]] = None
    generated_secret           : Optional[str]            = None
    header_value               : Optional[str]            = None
    authorization_header_value : Optional[str]            = None
    created_datetime           : Optional[datetime]       = None
    updated_datetime           : Optional[datetime]       = None

    model_config = {"from_attributes": True, "extra": "allow"}

    def model_post_init(self, __context: Any) -> None:
        if not self.auth_type and self.auth_type_code:
            self.auth_type = self.auth_type_code
        elif not self.auth_type_code and self.auth_type:
            self.auth_type_code = self.auth_type


class SYSTEM_CREDENTIAL_LIST_OUT_SCHEMA(BaseModel):
    items : List[SYSTEM_CREDENTIAL_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int
    stats : STATS_SUMMARY_SCHEMA


# ── System Endpoint Schemas ───────────────────────────────────────────────────

class SYSTEM_ENDPOINT_CREATE_SCHEMA(BaseModel):
    code              : str                 = Field(..., max_length=100, examples=["get_user_info"])
    name              : str                 = Field(..., max_length=255, examples=["Get User Info"])
    endpoint          : str                 = Field(..., max_length=500, examples=["/api/v1/users"])
    system_code       : Optional[str]       = None
    http_method       : str                 = Field(default="GET", max_length=10)
    operation_type    : Optional[str]       = Field(default=None, max_length=50)
    traffic_type      : Optional[str]       = Field(default="outbound", max_length=20)
    request_timeout   : Optional[int]       = 30
    auth_type         : Optional[str]       = Field(default=None, max_length=50)
    headers_config    : Optional[Any]       = None
    query_config      : Optional[Any]       = None
    description       : Optional[str]       = Field(default=None)
    is_encrypted_body : bool                = Field(default=False)
    status_code       : str                 = Field(default="active", max_length=10)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _normalize_endpoint(cls, data: Any) -> Any:
        if isinstance(data, dict):
            out = dict(data)
            if "endpoint_url" in out and "endpoint" not in out:
                out["endpoint"] = out["endpoint_url"]
            elif "endpoint" in out and "endpoint_url" not in out:
                out["endpoint_url"] = out["endpoint"]
            return out
        return data

    @property
    def endpoint_url(self) -> str:
        return self.endpoint


class SYSTEM_ENDPOINT_UPDATE_SCHEMA(BaseModel):
    name              : Optional[str]  = Field(default=None, max_length=255)
    endpoint          : Optional[str]  = Field(default=None, max_length=500)
    endpoint_url      : Optional[str]  = Field(default=None, max_length=500)
    http_method       : Optional[str]  = Field(default=None, max_length=10)
    traffic_type      : Optional[str]  = Field(default=None, max_length=20)
    operation_type    : Optional[str]  = Field(default=None, max_length=50)
    request_timeout   : Optional[int]  = None
    auth_type         : Optional[str]  = Field(default=None, max_length=50)
    headers_config    : Optional[Any]  = None
    query_config      : Optional[Any]  = None
    description       : Optional[str]  = Field(default=None)
    is_encrypted_body : Optional[bool] = Field(default=None)
    status_code       : Optional[str]  = Field(default=None, max_length=10)

    model_config = {"from_attributes": True, "extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _normalize_endpoint(cls, data: Any) -> Any:
        if isinstance(data, dict):
            out = dict(data)
            if "endpoint_url" in out and "endpoint" not in out:
                out["endpoint"] = out["endpoint_url"]
            elif "endpoint" in out and "endpoint_url" not in out:
                out["endpoint_url"] = out["endpoint"]
            return out
        return data


class SYSTEM_ENDPOINT_RESPONSE_SCHEMA(BaseModel):
    id                : uuid.UUID
    system_code       : str
    code              : str
    name              : str
    endpoint          : Optional[str]      = None
    endpoint_url      : Optional[str]      = None
    http_method       : str
    auth_type         : Optional[str]      = None
    description       : Optional[str]      = None
    is_encrypted_body : bool               = False
    traffic_type      : Optional[str]      = None
    operation_type    : Optional[str]      = None
    request_timeout   : Optional[int]      = 30
    headers_config    : Optional[Any]      = None
    query_config      : Optional[Any]      = None
    status_code       : str
    created_datetime  : Optional[datetime] = None
    updated_datetime  : Optional[datetime] = None

    model_config = {"from_attributes": True, "extra": "allow"}

    def model_post_init(self, __context: Any) -> None:
        if not self.endpoint and self.endpoint_url:
            self.endpoint = self.endpoint_url
        elif not self.endpoint_url and self.endpoint:
            self.endpoint_url = self.endpoint


class SYSTEM_ENDPOINT_LIST_OUT_SCHEMA(BaseModel):
    items : List[SYSTEM_ENDPOINT_RESPONSE_SCHEMA]
    total : int
    page  : int
    size  : int
    stats : STATS_SUMMARY_SCHEMA


# ── User & Role Authentication Schemas ────────────────────────────────────────

class LOGIN_REQUEST_SCHEMA(BaseModel):
    username : str
    password : str

    model_config = {"from_attributes": True}


class REFRESH_REQUEST_SCHEMA(BaseModel):
    refresh_token : str

    model_config = {"from_attributes": True}


class LOGOUT_REQUEST_SCHEMA(BaseModel):
    refresh_token : str

    model_config = {"from_attributes": True}


class CHANGE_PASSWORD_REQUEST_SCHEMA(BaseModel):
    current_password : str
    new_password     : str = Field(min_length=8)

    model_config = {"from_attributes": True}


class TOKEN_RESPONSE_SCHEMA(BaseModel):
    access_token  : str
    refresh_token : str
    token_type    : str = "bearer"

    model_config = {"from_attributes": True}


class PERMISSION_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    code             : str
    name             : str
    module           : str
    status_code      : str                = "ACTIVE"
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None

    model_config = {"from_attributes": True}


class ROLE_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    name             : str
    description      : Optional[str]                         = None
    status_code      : str                                   = "ACTIVE"
    permissions      : List[PERMISSION_RESPONSE_SCHEMA]      = []
    created_datetime : Optional[datetime]                    = None
    updated_datetime : Optional[datetime]                    = None

    model_config = {"from_attributes": True}


class USER_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    username         : str
    email            : str
    full_name        : str
    employee_code    : Optional[str]              = None
    branch_id        : Optional[uuid.UUID]        = None
    status           : str                        = "ACTIVE"
    status_code      : str                        = "ACTIVE"
    roles            : List[ROLE_RESPONSE_SCHEMA] = []
    created_datetime : Optional[datetime]         = None
    updated_datetime : Optional[datetime]         = None
    created_at       : Optional[datetime]         = None
    updated_at       : Optional[datetime]         = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status

        if self.created_datetime and not self.created_at:
            self.created_at = self.created_datetime
        elif self.created_at and not self.created_datetime:
            self.created_datetime = self.created_at

        if self.updated_datetime and not self.updated_at:
            self.updated_at = self.updated_datetime
        elif self.updated_at and not self.updated_datetime:
            self.updated_datetime = self.updated_at


class LOGIN_RESPONSE_SCHEMA(TOKEN_RESPONSE_SCHEMA):
    user : USER_RESPONSE_SCHEMA


class USER_CREATE_SCHEMA(BaseModel):
    username      : str                 = Field(min_length=3, max_length=100)
    email         : EmailStr
    full_name     : str
    password      : str                 = Field(min_length=8)
    employee_code : Optional[str]       = None
    branch_id     : Optional[uuid.UUID] = None
    role_ids      : List[uuid.UUID]     = []
    status_code   : str                 = "ACTIVE"

    model_config = {"from_attributes": True}


class USER_UPDATE_SCHEMA(BaseModel):
    full_name     : Optional[str]             = None
    email         : Optional[EmailStr]        = None
    employee_code : Optional[str]             = None
    branch_id     : Optional[uuid.UUID]       = None
    status        : Optional[str]             = None
    status_code   : Optional[str]             = None
    password      : Optional[str]             = Field(default=None, min_length=8)
    role_ids      : Optional[List[uuid.UUID]] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        if not self.status and self.status_code:
            self.status = self.status_code
        elif not self.status_code and self.status:
            self.status_code = self.status


class ROLE_CREATE_SCHEMA(BaseModel):
    name           : str
    description    : Optional[str]   = None
    permission_ids : List[uuid.UUID] = []
    status_code    : str             = "ACTIVE"

    model_config = {"from_attributes": True}


class ROLE_UPDATE_SCHEMA(BaseModel):
    name           : Optional[str]             = None
    description    : Optional[str]             = None
    permission_ids : Optional[List[uuid.UUID]] = None
    status_code    : Optional[str]             = None

    model_config = {"from_attributes": True}


__all__ = [
    "SYSTEM_CLIENT_CREATE_SCHEMA",
    "SYSTEM_CLIENT_RESPONSE_SCHEMA",
    "API_KEY_CREATED_SCHEMA",
    "SYSTEM_CREATE_SCHEMA",
    "SYSTEM_UPDATE_SCHEMA",
    "SYSTEM_RESPONSE_SCHEMA",
    "SYSTEM_LIST_OUT_SCHEMA",
    "SYSTEM_CREDENTIAL_CREATE_SCHEMA",
    "SYSTEM_CREDENTIAL_RESPONSE_SCHEMA",
    "SYSTEM_CREDENTIAL_LIST_OUT_SCHEMA",
    "SYSTEM_ENDPOINT_CREATE_SCHEMA",
    "SYSTEM_ENDPOINT_UPDATE_SCHEMA",
    "SYSTEM_ENDPOINT_RESPONSE_SCHEMA",
    "SYSTEM_ENDPOINT_LIST_OUT_SCHEMA",
    "LOGIN_REQUEST_SCHEMA",
    "REFRESH_REQUEST_SCHEMA",
    "LOGOUT_REQUEST_SCHEMA",
    "CHANGE_PASSWORD_REQUEST_SCHEMA",
    "TOKEN_RESPONSE_SCHEMA",
    "PERMISSION_RESPONSE_SCHEMA",
    "ROLE_RESPONSE_SCHEMA",
    "USER_RESPONSE_SCHEMA",
    "LOGIN_RESPONSE_SCHEMA",
    "USER_CREATE_SCHEMA",
    "USER_UPDATE_SCHEMA",
    "ROLE_CREATE_SCHEMA",
    "ROLE_UPDATE_SCHEMA",
]
