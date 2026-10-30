from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps.database import get_db
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
from app.schemas.base_schema import RESPONSE_ENVELOPE
from app.services.system_service import SYSTEM_SERVICE

router = APIRouter(prefix="/systems", tags=["System & Endpoint Management"])


@router.get(
    ""
    , response_model = RESPONSE_ENVELOPE[SYSTEM_LIST_OUT_SCHEMA]
)
def list_systems(
    search        : Optional[str] = Query(default=None, description="Search by code, name, or description")
    , status_code : Optional[str] = Query(default=None, description="Filter by status_code")
    , page        : int           = Query(default=1, ge=1)
    , size        : int           = Query(default=50, ge=1, le=200)
    , sort_by     : str           = Query(default="created_datetime")
    , sort_order  : str           = Query(default="desc")
    , db          : Session       = Depends(get_db)
):
    data = SYSTEM_SERVICE.list_systems(
        db            = db
        , search      = search
        , status_code = status_code
        , page        = page
        , size        = size
        , sort_by     = sort_by
        , sort_order  = sort_order
    )
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "Systems retrieved successfully."
    )


@router.get(
    "/{code}"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_RESPONSE_SCHEMA]
)
def get_system(
    code : str
    , db : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.get_system(db=db, code=code)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System retrieved successfully."
    )


@router.post(
    ""
    , response_model = RESPONSE_ENVELOPE[SYSTEM_RESPONSE_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
)
def create_system(
    body : SYSTEM_CREATE_SCHEMA
    , db : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.create_system(db=db, data=body)
    return RESPONSE_ENVELOPE.created(
        data      = data
        , message = "System created successfully."
    )


@router.put(
    "/{code}"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_RESPONSE_SCHEMA]
)
def update_system(
    code   : str
    , body : SYSTEM_UPDATE_SCHEMA
    , db   : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.update_system(db=db, code=code, data=body)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System updated successfully."
    )


@router.delete(
    "/{code}"
    , status_code = status.HTTP_204_NO_CONTENT
)
def delete_system(
    code : str
    , db : Session = Depends(get_db)
):
    SYSTEM_SERVICE.delete_system(db=db, code=code)


# ── System Endpoints Sub-Resource ─────────────────────────────────────────────

@router.get(
    "/{code}/endpoints"
    , response_model = RESPONSE_ENVELOPE[List[SYSTEM_ENDPOINT_RESPONSE_SCHEMA]]
)
def list_system_endpoints(
    code : str
    , db : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.list_endpoints(db=db, system_code=code)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System endpoints retrieved successfully."
    )


@router.post(
    "/{code}/endpoints"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_ENDPOINT_RESPONSE_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
)
def create_system_endpoint(
    code   : str
    , body : SYSTEM_ENDPOINT_CREATE_SCHEMA
    , db   : Session = Depends(get_db)
):
    payload = body.model_copy(update={"system_code": code})
    data    = SYSTEM_SERVICE.create_endpoint(db=db, data=payload)
    return RESPONSE_ENVELOPE.created(
        data      = data
        , message = "System endpoint created successfully."
    )


@router.put(
    "/endpoints/{endpoint_id}"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_ENDPOINT_RESPONSE_SCHEMA]
)
def update_system_endpoint(
    endpoint_id : str
    , body      : SYSTEM_ENDPOINT_UPDATE_SCHEMA
    , db        : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.update_endpoint(db=db, endpoint_id=endpoint_id, data=body)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System endpoint updated successfully."
    )


@router.delete(
    "/endpoints/{endpoint_id}"
    , status_code = status.HTTP_204_NO_CONTENT
)
def delete_system_endpoint(
    endpoint_id : str
    , db        : Session = Depends(get_db)
):
    SYSTEM_SERVICE.delete_endpoint(db=db, endpoint_id=endpoint_id)


# ── System Credentials Sub-Resource ───────────────────────────────────────────

@router.get(
    "/{code}/credentials"
    , response_model = RESPONSE_ENVELOPE[List[SYSTEM_CREDENTIAL_RESPONSE_SCHEMA]]
)
def list_system_credentials(
    code : str
    , db : Session = Depends(get_db)
):
    data = SYSTEM_SERVICE.list_credentials(db=db, system_code=code)
    return RESPONSE_ENVELOPE.success(
        data      = data
        , message = "System credentials retrieved successfully."
    )


@router.post(
    "/{code}/credentials"
    , response_model = RESPONSE_ENVELOPE[SYSTEM_CREDENTIAL_RESPONSE_SCHEMA]
    , status_code    = status.HTTP_201_CREATED
)
def create_system_credential(
    code   : str
    , body : SYSTEM_CREDENTIAL_CREATE_SCHEMA
    , db   : Session = Depends(get_db)
):
    payload = body.model_copy(update={"system_code": code})
    data    = SYSTEM_SERVICE.create_credential(db=db, data=payload)
    return RESPONSE_ENVELOPE.created(
        data      = data
        , message = "System credential created successfully."
    )

