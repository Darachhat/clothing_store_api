import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.enum.common_enum import AUTH_TYPE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.exceptions import CONFLICT_EXCEPTION, NOT_FOUND_EXCEPTION
from app.core.utils.crypto_utils import build_basic_auth
from app.core.utils.http_client import HTTP_CLIENT
from app.models.auth_model import (
    CREDENTIAL_API_KEY_MODEL
    , CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , CREDENTIAL_OAUTH2_MODEL
    , SYSTEM_CREDENTIAL_MODEL
    , SYSTEM_ENDPOINT_MODEL
    , SYSTEM_MODEL
)
from app.schemas.auth_schema import (
    SYSTEM_CREATE_SCHEMA
    , SYSTEM_CREDENTIAL_CREATE_SCHEMA
    , SYSTEM_CREDENTIAL_RESPONSE_SCHEMA
    , SYSTEM_ENDPOINT_CREATE_SCHEMA
    , SYSTEM_ENDPOINT_RESPONSE_SCHEMA
    , SYSTEM_ENDPOINT_UPDATE_SCHEMA
    , SYSTEM_LIST_OUT_SCHEMA
    , SYSTEM_RESPONSE_SCHEMA
    , SYSTEM_UPDATE_SCHEMA
)
from app.schemas.base_schema import STATS_SUMMARY_SCHEMA


def _parse_uuid(raw_id: str, label: str = "Resource") -> uuid.UUID:
    if isinstance(raw_id, uuid.UUID):
        return raw_id
    try:
        return uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        raise NOT_FOUND_EXCEPTION(f"{label} '{raw_id}' was not found.")


class SYSTEM_SERVICE:
    """
    Service managing external/internal Systems (auth.system), Endpoints (auth.system_endpoint),
    Credentials (auth.system_credential + credential_* tables), and outbound endpoint invocations.
    """

    @staticmethod
    def list_systems(
        db            : Session
        , search      : Optional[str] = None
        , status_code : Optional[str] = None
        , page        : int           = 1
        , size        : int           = 50
        , sort_by     : str           = "created_datetime"
        , sort_order  : str           = "desc"
    ) -> SYSTEM_LIST_OUT_SCHEMA:
        base_query = db.query(SYSTEM_MODEL).filter(
            SYSTEM_MODEL.deleted_datetime.is_(None)
        )

        total_cnt  = base_query.count()
        active_cnt = base_query.filter(SYSTEM_MODEL.status_code.in_(["active", "ACTIVE"])).count()

        query = base_query
        if search:
            like  = f"%{search}%"
            query = query.filter(
                SYSTEM_MODEL.code.ilike(like)
                | SYSTEM_MODEL.name.ilike(like)
                | SYSTEM_MODEL.description.ilike(like)
            )
        if status_code:
            query = query.filter(SYSTEM_MODEL.status_code == status_code)

        col_map = {
            "code"               : SYSTEM_MODEL.code
            , "name"             : SYSTEM_MODEL.name
            , "status_code"      : SYSTEM_MODEL.status_code
            , "created_datetime" : SYSTEM_MODEL.created_datetime
        }
        sort_col = col_map.get(sort_by, SYSTEM_MODEL.created_datetime)
        query    = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        filtered_total = query.count()
        rows           = query.offset((page - 1) * size).limit(size).all()

        return SYSTEM_LIST_OUT_SCHEMA(
            items   = [SYSTEM_RESPONSE_SCHEMA.model_validate(r) for r in rows]
            , total = filtered_total
            , page  = page
            , size  = size
            , stats = STATS_SUMMARY_SCHEMA(
                total      = total_cnt
                , active   = active_cnt
                , inactive = max(0, total_cnt - active_cnt)
            )
        )

    @staticmethod
    def get_system(
        db     : Session
        , code : str
    ) -> SYSTEM_RESPONSE_SCHEMA:
        row = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"System '{code}' was not found.")
        return SYSTEM_RESPONSE_SCHEMA.model_validate(row)

    @staticmethod
    def create_system(
        db     : Session
        , data : SYSTEM_CREATE_SCHEMA
    ) -> SYSTEM_RESPONSE_SCHEMA:
        existing = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == data.code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if existing:
            raise CONFLICT_EXCEPTION(f"System with code '{data.code}' already exists.")

        row = SYSTEM_MODEL(
            code                = data.code
            , name              = data.name
            , description       = data.description
            , base_url          = data.base_url
            , scope             = data.scope
            , is_encrypted_body = data.is_encrypted_body
            , status_code       = data.status_code
            , created_by        = "admin"
            , updated_by        = "admin"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return SYSTEM_RESPONSE_SCHEMA.model_validate(row)

    @staticmethod
    def update_system(
        db     : Session
        , code : str
        , data : SYSTEM_UPDATE_SCHEMA
    ) -> SYSTEM_RESPONSE_SCHEMA:
        row = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"System '{code}' was not found.")

        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                setattr(row, field, value)

        row.updated_datetime = datetime.now(timezone.utc)
        row.updated_by       = "admin"
        db.commit()
        db.refresh(row)
        return SYSTEM_RESPONSE_SCHEMA.model_validate(row)

    @staticmethod
    def delete_system(
        db     : Session
        , code : str
    ) -> None:
        row = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"System '{code}' was not found.")

        row.deleted_datetime = datetime.now(timezone.utc)
        row.deleted_by       = "admin"
        row.status_code      = "deleted"
        db.commit()

    @staticmethod
    def list_endpoints(
        db            : Session
        , system_code : Optional[str] = None
    ) -> List[SYSTEM_ENDPOINT_RESPONSE_SCHEMA]:
        query = db.query(SYSTEM_ENDPOINT_MODEL).filter(
            SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
        )
        if system_code:
            query = query.filter(SYSTEM_ENDPOINT_MODEL.system_code == system_code)
        rows = query.order_by(SYSTEM_ENDPOINT_MODEL.created_datetime.desc()).all()
        return [SYSTEM_ENDPOINT_RESPONSE_SCHEMA.model_validate(r) for r in rows]

    @staticmethod
    def create_endpoint(
        db     : Session
        , data : SYSTEM_ENDPOINT_CREATE_SCHEMA
    ) -> SYSTEM_ENDPOINT_RESPONSE_SCHEMA:
        existing = (
            db.query(SYSTEM_ENDPOINT_MODEL)
            .filter(
                SYSTEM_ENDPOINT_MODEL.system_code == data.system_code
                , SYSTEM_ENDPOINT_MODEL.code == data.code
                , SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if existing:
            raise CONFLICT_EXCEPTION(
                f"Endpoint '{data.code}' already exists for system '{data.system_code}'."
            )

        row = SYSTEM_ENDPOINT_MODEL(
            system_code       = data.system_code
            , code            = data.code
            , name            = data.name
            , operation_type  = data.operation_type
            , endpoint        = data.endpoint
            , http_method     = data.http_method.upper()
            , traffic_type    = data.traffic_type
            , request_timeout = data.request_timeout
            , headers_config  = data.headers_config
            , query_config    = data.query_config
            , description     = data.description
            , status_code     = data.status_code
            , created_by      = "admin"
            , updated_by      = "admin"
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return SYSTEM_ENDPOINT_RESPONSE_SCHEMA.model_validate(row)

    @staticmethod
    def update_endpoint(
        db            : Session
        , endpoint_id : str
        , data        : SYSTEM_ENDPOINT_UPDATE_SCHEMA
    ) -> SYSTEM_ENDPOINT_RESPONSE_SCHEMA:
        ep_uuid = _parse_uuid(endpoint_id, "System endpoint")
        row = (
            db.query(SYSTEM_ENDPOINT_MODEL)
            .filter(
                SYSTEM_ENDPOINT_MODEL.id == ep_uuid
                , SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"System endpoint '{endpoint_id}' was not found.")

        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                setattr(row, field, value)

        row.updated_datetime = datetime.now(timezone.utc)
        row.updated_by       = "admin"
        db.commit()
        db.refresh(row)
        return SYSTEM_ENDPOINT_RESPONSE_SCHEMA.model_validate(row)

    @staticmethod
    def delete_endpoint(
        db            : Session
        , endpoint_id : str
    ) -> None:
        ep_uuid = _parse_uuid(endpoint_id, "System endpoint")
        row = (
            db.query(SYSTEM_ENDPOINT_MODEL)
            .filter(
                SYSTEM_ENDPOINT_MODEL.id == ep_uuid
                , SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
            )
            .first()
        )
        if not row:
            raise NOT_FOUND_EXCEPTION(f"System endpoint '{endpoint_id}' was not found.")

        row.deleted_datetime = datetime.now(timezone.utc)
        row.deleted_by       = "admin"
        row.status_code      = "deleted"
        db.commit()

    @staticmethod
    def list_credentials(
        db            : Session
        , system_code : Optional[str] = None
    ) -> List[SYSTEM_CREDENTIAL_RESPONSE_SCHEMA]:
        query = db.query(SYSTEM_CREDENTIAL_MODEL).filter(
            SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None)
        )
        if system_code:
            query = query.filter(SYSTEM_CREDENTIAL_MODEL.system_code == system_code)
        rows = query.order_by(SYSTEM_CREDENTIAL_MODEL.created_datetime.desc()).all()
        return [SYSTEM_CREDENTIAL_RESPONSE_SCHEMA.model_validate(r) for r in rows]

    @staticmethod
    def create_credential(
        db     : Session
        , data : SYSTEM_CREDENTIAL_CREATE_SCHEMA
    ) -> SYSTEM_CREDENTIAL_RESPONSE_SCHEMA:
        cred = SYSTEM_CREDENTIAL_MODEL(
            system_code      = data.system_code
            , traffic_type   = data.traffic_type
            , auth_type_code = data.auth_type_code
            , description    = data.description
            , status_code    = data.status_code
            , created_by     = "admin"
            , updated_by     = "admin"
        )
        db.add(cred)

        auth_type = data.auth_type_code.lower()
        if auth_type == AUTH_TYPE_ENUM.BASIC.value and data.username and data.password is not None:
            db.add(
                CREDENTIAL_BASIC_MODEL(
                    system_code    = data.system_code
                    , traffic_type = data.traffic_type
                    , username     = data.username
                    , password     = data.password
                    , description  = data.description
                    , status_code  = data.status_code
                    , created_by   = "admin"
                )
            )
        elif auth_type == AUTH_TYPE_ENUM.BEARER.value and data.token_value:
            db.add(
                CREDENTIAL_BEARER_MODEL(
                    system_code    = data.system_code
                    , traffic_type = data.traffic_type
                    , header_name  = data.header_name or "Authorization"
                    , token_prefix = data.token_prefix or "Bearer"
                    , token_value  = data.token_value
                    , description  = data.description
                    , status_code  = data.status_code
                    , created_by   = "admin"
                )
            )
        elif auth_type == AUTH_TYPE_ENUM.API_KEY.value and data.key_name and data.key_value:
            db.add(
                CREDENTIAL_API_KEY_MODEL(
                    system_code    = data.system_code
                    , traffic_type = data.traffic_type
                    , key_location = data.key_location or "header"
                    , key_name     = data.key_name
                    , key_value    = data.key_value
                    , description  = data.description
                    , status_code  = data.status_code
                    , created_by   = "admin"
                )
            )
        elif auth_type == AUTH_TYPE_ENUM.OAUTH2.value:
            db.add(
                CREDENTIAL_OAUTH2_MODEL(
                    system_code     = data.system_code
                    , traffic_type  = data.traffic_type
                    , token_url     = data.token_url
                    , grant_type    = data.grant_type
                    , client_id     = data.client_id
                    , client_secret = data.client_secret
                    , username      = data.username
                    , password      = data.password
                    , description   = data.description
                    , status_code   = data.status_code
                    , created_by    = "admin"
                )
            )

        db.commit()
        db.refresh(cred)
        return SYSTEM_CREDENTIAL_RESPONSE_SCHEMA.model_validate(cred)

    @staticmethod
    def build_outbound_auth(
        db            : Session
        , system_code : str
    ) -> Tuple[Dict[str, str], Dict[str, Any]]:
        headers      : Dict[str, str] = {}
        query_params : Dict[str, Any] = {}

        mapping = (
            db.query(SYSTEM_CREDENTIAL_MODEL)
            .filter(
                SYSTEM_CREDENTIAL_MODEL.system_code == system_code
                , SYSTEM_CREDENTIAL_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                , SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None)
                , SYSTEM_CREDENTIAL_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )
        if not mapping:
            return headers, query_params

        auth_type = mapping.auth_type_code.lower()
        if auth_type == AUTH_TYPE_ENUM.BASIC.value:
            basic = (
                db.query(CREDENTIAL_BASIC_MODEL)
                .filter(
                    CREDENTIAL_BASIC_MODEL.system_code == system_code
                    , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                    , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
                    , CREDENTIAL_BASIC_MODEL.status_code.in_(["active", "ACTIVE"])
                )
                .first()
            )
            if basic:
                headers["Authorization"] = build_basic_auth(basic.username, basic.password)

        elif auth_type == AUTH_TYPE_ENUM.BEARER.value:
            bearer = (
                db.query(CREDENTIAL_BEARER_MODEL)
                .filter(
                    CREDENTIAL_BEARER_MODEL.system_code == system_code
                    , CREDENTIAL_BEARER_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                    , CREDENTIAL_BEARER_MODEL.deleted_datetime.is_(None)
                    , CREDENTIAL_BEARER_MODEL.status_code.in_(["active", "ACTIVE"])
                )
                .first()
            )
            if bearer:
                prefix = f"{bearer.token_prefix} " if bearer.token_prefix else ""
                headers[bearer.header_name or "Authorization"] = f"{prefix}{bearer.token_value}"

        elif auth_type == AUTH_TYPE_ENUM.API_KEY.value:
            api_key_cred = (
                db.query(CREDENTIAL_API_KEY_MODEL)
                .filter(
                    CREDENTIAL_API_KEY_MODEL.system_code == system_code
                    , CREDENTIAL_API_KEY_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                    , CREDENTIAL_API_KEY_MODEL.deleted_datetime.is_(None)
                    , CREDENTIAL_API_KEY_MODEL.status_code.in_(["active", "ACTIVE"])
                )
                .first()
            )
            if api_key_cred:
                if (api_key_cred.key_location or "header").lower() == "query":
                    query_params[api_key_cred.key_name] = api_key_cred.key_value
                else:
                    headers[api_key_cred.key_name] = api_key_cred.key_value

        return headers, query_params

    @staticmethod
    async def call_endpoint(
        db              : Session
        , system_code   : str
        , endpoint_code : str
        , json_data     : Optional[Dict[str, Any]] = None
        , params        : Optional[Dict[str, Any]] = None
        , headers       : Optional[Dict[str, str]] = None
        , request_id    : Optional[str]            = None
    ) -> Dict[str, Any]:
        system = (
            db.query(SYSTEM_MODEL)
            .filter(
                SYSTEM_MODEL.code == system_code
                , SYSTEM_MODEL.deleted_datetime.is_(None)
                , SYSTEM_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )
        if not system:
            raise NOT_FOUND_EXCEPTION(f"Active system '{system_code}' was not found.")

        ep = (
            db.query(SYSTEM_ENDPOINT_MODEL)
            .filter(
                SYSTEM_ENDPOINT_MODEL.system_code == system_code
                , SYSTEM_ENDPOINT_MODEL.code == endpoint_code
                , SYSTEM_ENDPOINT_MODEL.deleted_datetime.is_(None)
                , SYSTEM_ENDPOINT_MODEL.status_code.in_(["active", "ACTIVE"])
            )
            .first()
        )
        if not ep:
            raise NOT_FOUND_EXCEPTION(
                f"Active endpoint '{endpoint_code}' for system '{system_code}' was not found."
            )

        base_url = (system.base_url or "").rstrip("/")
        path     = ep.endpoint if ep.endpoint.startswith("http") else f"{base_url}/{ep.endpoint.lstrip('/')}"

        merged_headers : Dict[str, str] = {}
        if isinstance(ep.headers_config, dict):
            merged_headers.update({str(k): str(v) for k, v in ep.headers_config.items()})

        merged_params : Dict[str, Any] = {}
        if isinstance(ep.query_config, dict):
            merged_params.update(ep.query_config)

        auth_headers, auth_params = SYSTEM_SERVICE.build_outbound_auth(db=db, system_code=system_code)
        merged_headers.update(auth_headers)
        merged_params.update(auth_params)

        if headers:
            merged_headers.update(headers)
        if params:
            merged_params.update(params)

        return await HTTP_CLIENT.request(
            method        = ep.http_method
            , url         = path
            , params      = merged_params or None
            , json_data   = json_data
            , headers     = merged_headers or None
            , timeout     = ep.request_timeout
            , system_code = system_code
            , request_id  = request_id
        )

