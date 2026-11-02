from enum import Enum


class ENVIRONMENT_ENUM(str, Enum):
    DEVELOPMENT   = "development"
    STAGING       = "staging"
    PRODUCTION    = "production"
    TESTING       = "testing"


class EXECUTION_STRATEGY_ENUM(str, Enum):
    ASYNCIO       = "asyncio"
    CELERY        = "celery"
    SCHEDULER     = "scheduler"


class TASK_STATUS_ENUM(str, Enum):
    PENDING       = "PENDING"
    RUNNING       = "RUNNING"
    SUCCESS       = "SUCCESS"
    FAILED        = "FAILED"
    RETRYING      = "RETRYING"


class SYSTEM_CODE_ENUM(str, Enum):
    ADMIN_HUB     = "admin_hub"
    EXTERNAL_API  = "external_api"
    SYSTEM_CLIENT = "system_client"
    ABA_PAYWAY    = "aba_payway"
    TELEGRAM_API  = "telegram_api"


class TRAFFIC_TYPE_ENUM(str, Enum):
    INBOUND       = "inbound"
    OUTBOUND      = "outbound"


class AUTH_TYPE_ENUM(str, Enum):
    BASIC         = "basic"
    BEARER        = "bearer"
    API_KEY       = "api_key"
    OAUTH2        = "oauth2"


class STATUS_CODE_ENUM(str, Enum):
    ACTIVE        = "active"
    INACTIVE      = "inactive"
    PENDING       = "pending"
    DRAFT         = "draft"
    ARCHIVED      = "archived"
    DELETED       = "deleted"


class CHANNEL_ENUM(str, Enum):
    SYSTEM        = "SYSTEM"
    BANK          = "BANK"
    ADMIN         = "ADMIN"
    CASHIER       = "CASHIER"
    STORE         = "STORE"
    PUBLIC        = "PUBLIC"


class CHAT_TYPE_ENUM(str, Enum):
    CHANNEL       = "channel"
    GROUP         = "group"
    TOPIC         = "topic"


class SCOPE_ENUM(str, Enum):
    INTERNAL      = "internal"
    EXTERNAL      = "external"


class KEY_LOCATION_ENUM(str, Enum):
    HEADER        = "header"
    QUERY         = "query"


class COMMON_STATUS_ENUM(str, Enum):
    ACTIVE        = "ACTIVE"
    INACTIVE      = "INACTIVE"
    PENDING       = "PENDING"
    APPROVED      = "APPROVED"
    REJECTED      = "REJECTED"
    EXPIRED       = "EXPIRED"
    DRAFT         = "DRAFT"
    ARCHIVED      = "ARCHIVED"
    DELETED       = "DELETED"


class ROLE_ENUM(str, Enum):
    ADMIN         = "ADMIN"
    MANAGER       = "MANAGER"
    CASHIER       = "CASHIER"


class SIZE_TYPE_ENUM(str, Enum):
    LETTER        = "LETTER"
    NUMERIC       = "NUMERIC"
    CUSTOM        = "CUSTOM"


class CURRENCY_ENUM(str, Enum):
    USD           = "USD"
    KHR           = "KHR"


class LANGUAGE_ENUM(str, Enum):
    EN            = "en"
    KM            = "km"
    CN            = "cn"
    JP            = "jp"
    KR            = "kr"


class SALE_STATUS_ENUM(str, Enum):
    DRAFT         = "DRAFT"
    PENDING       = "PENDING"
    COMPLETED     = "COMPLETED"
    CANCELLED     = "CANCELLED"
    RETURNED      = "RETURNED"
    REFUNDED      = "REFUNDED"


class PAYMENT_STATUS_ENUM(str, Enum):
    PENDING            = "PENDING"
    PARTIAL            = "PARTIAL"
    PAID               = "PAID"
    REFUNDED           = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    FAILED             = "FAILED"


class PAYMENT_METHOD_ENUM(str, Enum):
    CASH          = "CASH"
    KHQR          = "KHQR"
    CARD          = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CREDIT        = "CREDIT"
    OTHER         = "OTHER"


class PAYMENT_PROVIDER_ENUM(str, Enum):
    ABA_PAYWAY    = "ABA_PAYWAY"
    MANUAL        = "MANUAL"


class PAYMENT_CHANNEL_ENUM(str, Enum):
    POS           = "POS"
    ONLINE        = "ONLINE"
    MOBILE        = "MOBILE"


class RETURN_TYPE_ENUM(str, Enum):
    FULL          = "FULL"
    PARTIAL       = "PARTIAL"
    EXCHANGE      = "EXCHANGE"


class RETURN_STATUS_ENUM(str, Enum):
    PENDING       = "PENDING"
    APPROVED      = "APPROVED"
    COMPLETED     = "COMPLETED"
    REJECTED      = "REJECTED"


class INVENTORY_MOVEMENT_TYPE_ENUM(str, Enum):
    INITIAL_STOCK = "INITIAL_STOCK"
    SALE          = "SALE"
    RETURN        = "RETURN"
    PURCHASE      = "PURCHASE"
    TRANSFER_IN   = "TRANSFER_IN"
    TRANSFER_OUT  = "TRANSFER_OUT"
    ADJUSTMENT    = "ADJUSTMENT"
    DAMAGE        = "DAMAGE"
    LOST          = "LOST"


class STOCK_TRANSFER_STATUS_ENUM(str, Enum):
    DRAFT         = "DRAFT"
    PENDING       = "PENDING"
    APPROVED      = "APPROVED"
    IN_TRANSIT    = "IN_TRANSIT"
    SENT          = "SENT"
    RECEIVED      = "RECEIVED"
    CANCELLED     = "CANCELLED"


class PURCHASE_STATUS_ENUM(str, Enum):
    DRAFT         = "DRAFT"
    ORDERED       = "ORDERED"
    PARTIAL       = "PARTIAL"
    RECEIVED      = "RECEIVED"
    CANCELLED     = "CANCELLED"


class GOODS_RECEIPT_STATUS_ENUM(str, Enum):
    RECEIVED      = "RECEIVED"
    COMPLETED     = "COMPLETED"
    CANCELLED     = "CANCELLED"


class LOYALTY_TIER_ENUM(str, Enum):
    BRONZE        = "BRONZE"
    SILVER        = "SILVER"
    GOLD          = "GOLD"
    PLATINUM      = "PLATINUM"


class LOYALTY_TRANSACTION_TYPE_ENUM(str, Enum):
    EARN          = "EARN"
    REDEEM        = "REDEEM"
    ADJUST        = "ADJUST"
    EXPIRED       = "EXPIRED"


class PROMOTION_TYPE_ENUM(str, Enum):
    PERCENTAGE    = "PERCENTAGE"
    FIXED         = "FIXED"
    COUPON        = "COUPON"
    CATEGORY      = "CATEGORY"
    PRODUCT       = "PRODUCT"


class PROMOTION_APPLIES_TO_ENUM(str, Enum):
    ALL           = "ALL"
    CATEGORY      = "CATEGORY"
    PRODUCT       = "PRODUCT"


class REFERENCE_TYPE_ENUM(str, Enum):
    SALE          = "sale"
    RETURN        = "return"
    PURCHASE      = "purchase"
    TRANSFER      = "transfer"
    MANUAL        = "manual"


