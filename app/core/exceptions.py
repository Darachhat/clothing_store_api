from typing import List, Optional
from fastapi import HTTPException

from app.core.enum.response_enum import RESPONSE_CODE_ENUM, RESPONSE_MESSAGE_REGISTRY


class APP_EXCEPTION(HTTPException):
    """
    Base domain exception for application-level error handling.
    Inherits from HTTPException so FastAPI handlers and standard error listeners
    seamlessly capture status_code and detail.
    """
    def __init__(
        self
        , code        : RESPONSE_CODE_ENUM = RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR
        , message     : Optional[str]      = None
        , errors      : Optional[List[str]] = None
        , status_code : int                = 500
    ):
        self.code        = code
        self.message     = message or RESPONSE_MESSAGE_REGISTRY.get_message(code)
        self.errors      = errors or []
        super().__init__(status_code=status_code, detail=self.message)



class NOT_FOUND_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Resource not found"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.NOT_FOUND
            , message     = message
            , errors      = errors
            , status_code = 404
        )


class VALIDATION_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Validation failed"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.VALIDATION_ERROR
            , message     = message
            , errors      = errors
            , status_code = 422
        )


class UNAUTHORIZED_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Unauthorized access"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.UNAUTHORIZED
            , message     = message
            , errors      = errors
            , status_code = 401
        )


class FORBIDDEN_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Permission denied"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.FORBIDDEN
            , message     = message
            , errors      = errors
            , status_code = 403
        )


class BAD_REQUEST_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Bad request"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.BAD_REQUEST
            , message     = message
            , errors      = errors
            , status_code = 400
        )


class CONFLICT_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Resource conflict"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.CONFLICT
            , message     = message
            , errors      = errors
            , status_code = 409
        )


class SERVICE_UNAVAILABLE_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Service unavailable"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.SERVICE_UNAVAILABLE
            , message     = message
            , errors      = errors
            , status_code = 503
        )


class BAD_GATEWAY_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Bad gateway"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.SERVICE_UNAVAILABLE
            , message     = message
            , errors      = errors
            , status_code = 502
        )


class INTERNAL_SERVER_EXCEPTION(APP_EXCEPTION):
    def __init__(
        self
        , message : str                 = "Internal server error"
        , errors  : Optional[List[str]] = None
    ):
        super().__init__(
            code          = RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR
            , message     = message
            , errors      = errors
            , status_code = 500
        )


