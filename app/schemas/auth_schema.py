from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

from app.schemas.base_schema import STATS_SUMMARY_SCHEMA


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


# ── System Endpoint (auth.system_endpoint) Schemas ────────────────────────────

class SYSTEM_ENDPOINT_CREATE_SCHEMA(BaseModel):
    system_code     : str                      = Field(..., max_length=100)
    code            : str                      = Field(..., max_length=100)
    name            : str                      = Field(..., max_length=255)
    operation_type  : Optional[str]            = Field(default=None, max_length=50)
    endpoint        : str                      = Field(..., max_length=500)
    http_method     : str                      = Field(default="POST", max_length=10)
    traffic_type    : str                      = Field(default="outbound", max_length=20)
    request_timeout : int                      = Field(default=30, ge=1, le=300)
    headers_config  : Optional[Dict[str, Any]] = Field(default=None)
    query_config    : Optional[Dict[str, Any]] = Field(default=None)
    description     : Optional[str]            = Field(default=None)
    status_code     : str                      = Field(default="active", max_length=10)


class SYSTEM_ENDPOINT_UPDATE_SCHEMA(BaseModel):
    name            : Optional[str]            = Field(default=None, max_length=255)
    operation_type  : Optional[str]            = Field(default=None, max_length=50)
    endpoint        : Optional[str]            = Field(default=None, max_length=500)
    http_method     : Optional[str]            = Field(default=None, max_length=10)
    traffic_type    : Optional[str]            = Field(default=None, max_length=20)
    request_timeout : Optional[int]            = Field(default=None, ge=1, le=300)
    headers_config  : Optional[Dict[str, Any]] = Field(default=None)
    query_config    : Optional[Dict[str, Any]] = Field(default=None)
    description     : Optional[str]            = Field(default=None)
    status_code     : Optional[str]            = Field(default=None, max_length=10)


class SYSTEM_ENDPOINT_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    system_code      : str
    code             : str
    name             : str
    operation_type   : Optional[str]      = None
    endpoint         : str
    http_method      : str
    traffic_type     : str
    request_timeout  : int
    headers_config   : Optional[Any]      = None
    query_config     : Optional[Any]      = None
    description      : Optional[str]      = None
    status_code      : str
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── System Credential (auth.system_credential & sub-tables) Schemas ───────────

class SYSTEM_CREDENTIAL_CREATE_SCHEMA(BaseModel):
    system_code    : str           = Field(..., max_length=100)
    traffic_type   : str           = Field(default="outbound", max_length=20)
    auth_type_code : str           = Field(..., max_length=50, description="basic | bearer | api_key | oauth2")
    description    : Optional[str] = Field(default=None)
    status_code    : str           = Field(default="active", max_length=10)

    username       : Optional[str] = Field(default=None)
    password       : Optional[str] = Field(default=None)
    header_name    : Optional[str] = Field(default="Authorization")
    token_prefix   : Optional[str] = Field(default="Bearer")
    token_value    : Optional[str] = Field(default=None)
    key_location   : Optional[str] = Field(default="header")
    key_name       : Optional[str] = Field(default=None)
    key_value      : Optional[str] = Field(default=None)
    token_url      : Optional[str] = Field(default=None)
    grant_type     : Optional[str] = Field(default=None)
    client_id      : Optional[str] = Field(default=None)
    client_secret  : Optional[str] = Field(default=None)


class SYSTEM_CREDENTIAL_RESPONSE_SCHEMA(BaseModel):
    id               : uuid.UUID
    system_code      : str
    traffic_type     : str
    auth_type_code   : str
    description      : Optional[str]      = None
    status_code      : str
    created_datetime : Optional[datetime] = None
    updated_datetime : Optional[datetime] = None

    model_config = {"from_attributes": True}

