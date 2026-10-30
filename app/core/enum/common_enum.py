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

