from enum import Enum
from typing import Any, Dict, List


class RESPONSE_CODE_ENUM(str, Enum):
    SUCCESS                   = "SUCCESS"
    CREATED                   = "CREATED"
    BAD_REQUEST               = "BAD_REQUEST"
    UNAUTHORIZED              = "UNAUTHORIZED"
    FORBIDDEN                 = "FORBIDDEN"
    NOT_FOUND                 = "NOT_FOUND"
    CONFLICT                  = "CONFLICT"
    VALIDATION_ERROR          = "VALIDATION_ERROR"
    INTERNAL_SERVER_ERROR     = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE       = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT           = "GATEWAY_TIMEOUT"
    TELEGRAM_BOT_NOT_FOUND    = "TELEGRAM_BOT_NOT_FOUND"
    TELEGRAM_CHAT_NOT_FOUND   = "TELEGRAM_CHAT_NOT_FOUND"
    SYSTEM_NOT_FOUND          = "SYSTEM_NOT_FOUND"
    SYSTEM_ENDPOINT_NOT_FOUND = "SYSTEM_ENDPOINT_NOT_FOUND"
    INSUFFICIENT_STOCK        = "INSUFFICIENT_STOCK"
    SALE_ALREADY_COMPLETED    = "SALE_ALREADY_COMPLETED"
    PAYMENT_FAILED            = "PAYMENT_FAILED"
    COUPON_INVALID            = "COUPON_INVALID"


class RESPONSE_MESSAGE_REGISTRY:
    MESSAGES : Dict[RESPONSE_CODE_ENUM, str] = {
        RESPONSE_CODE_ENUM.SUCCESS                     : "Operation completed successfully."
        , RESPONSE_CODE_ENUM.CREATED                   : "Resource created successfully."
        , RESPONSE_CODE_ENUM.BAD_REQUEST               : "Invalid request payload or parameters."
        , RESPONSE_CODE_ENUM.UNAUTHORIZED              : "Authentication credentials were missing or invalid."
        , RESPONSE_CODE_ENUM.FORBIDDEN                 : "You do not have permission to perform this action."
        , RESPONSE_CODE_ENUM.NOT_FOUND                 : "The requested resource was not found."
        , RESPONSE_CODE_ENUM.CONFLICT                  : "Resource conflict or duplicate identifier."
        , RESPONSE_CODE_ENUM.VALIDATION_ERROR          : "Request validation failed."
        , RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR     : "An unexpected error occurred on the server."
        , RESPONSE_CODE_ENUM.SERVICE_UNAVAILABLE       : "Upstream service is currently unavailable."
        , RESPONSE_CODE_ENUM.GATEWAY_TIMEOUT           : "Upstream service timed out."
        , RESPONSE_CODE_ENUM.TELEGRAM_BOT_NOT_FOUND    : "Telegram bot was not found."
        , RESPONSE_CODE_ENUM.TELEGRAM_CHAT_NOT_FOUND   : "Telegram chat was not found."
        , RESPONSE_CODE_ENUM.SYSTEM_NOT_FOUND          : "Target system was not found."
        , RESPONSE_CODE_ENUM.SYSTEM_ENDPOINT_NOT_FOUND : "System endpoint configuration was not found."
        , RESPONSE_CODE_ENUM.INSUFFICIENT_STOCK        : "Insufficient inventory stock for requested operation."
        , RESPONSE_CODE_ENUM.SALE_ALREADY_COMPLETED    : "Sale has already been completed or cancelled."
        , RESPONSE_CODE_ENUM.PAYMENT_FAILED            : "Payment processing failed."
        , RESPONSE_CODE_ENUM.COUPON_INVALID            : "Promotion or coupon code is invalid or expired."
    }

    HTTP_STATUS_MAP : Dict[RESPONSE_CODE_ENUM, int] = {
        RESPONSE_CODE_ENUM.SUCCESS                     : 200
        , RESPONSE_CODE_ENUM.CREATED                   : 201
        , RESPONSE_CODE_ENUM.BAD_REQUEST               : 400
        , RESPONSE_CODE_ENUM.UNAUTHORIZED              : 401
        , RESPONSE_CODE_ENUM.FORBIDDEN                 : 403
        , RESPONSE_CODE_ENUM.NOT_FOUND                 : 404
        , RESPONSE_CODE_ENUM.CONFLICT                  : 409
        , RESPONSE_CODE_ENUM.VALIDATION_ERROR          : 422
        , RESPONSE_CODE_ENUM.INTERNAL_SERVER_ERROR     : 500
        , RESPONSE_CODE_ENUM.SERVICE_UNAVAILABLE       : 503
        , RESPONSE_CODE_ENUM.GATEWAY_TIMEOUT           : 504
        , RESPONSE_CODE_ENUM.TELEGRAM_BOT_NOT_FOUND    : 404
        , RESPONSE_CODE_ENUM.TELEGRAM_CHAT_NOT_FOUND   : 404
        , RESPONSE_CODE_ENUM.SYSTEM_NOT_FOUND          : 404
        , RESPONSE_CODE_ENUM.SYSTEM_ENDPOINT_NOT_FOUND : 404
        , RESPONSE_CODE_ENUM.INSUFFICIENT_STOCK        : 400
        , RESPONSE_CODE_ENUM.SALE_ALREADY_COMPLETED    : 409
        , RESPONSE_CODE_ENUM.PAYMENT_FAILED            : 502
        , RESPONSE_CODE_ENUM.COUPON_INVALID            : 400
    }

    @classmethod
    def get_message(cls, code: RESPONSE_CODE_ENUM, default_msg: str = "") -> str:
        return cls.MESSAGES.get(code, default_msg or "An error occurred.")

    @classmethod
    def get_http_status(cls, code: RESPONSE_CODE_ENUM, default_status: int = 500) -> int:
        return cls.HTTP_STATUS_MAP.get(code, default_status)

    @classmethod
    def list_all(cls) -> List[Dict[str, Any]]:
        return [
            {
                "code"          : item.value
                , "http_status" : cls.get_http_status(item)
                , "message"     : cls.get_message(item)
            }
            for item in RESPONSE_CODE_ENUM
        ]

