from typing import Final, Set

DEFAULT_TIMEZONE                : Final[str]      = "Asia/Phnom_Penh"
DATETIME_FORMAT                 : Final[str]      = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT                     : Final[str]      = "%Y-%m-%d"
TIME_FORMAT                     : Final[str]      = "%H:%M:%S"

DEFAULT_PAGE_SIZE               : Final[int]      = 20
MAX_PAGE_SIZE                   : Final[int]      = 200

HTTP_TIMEOUT_SECONDS            : Final[int]      = 30
HTTP_CONNECT_TIMEOUT_SECONDS    : Final[int]      = 10
MAX_RETRIES                     : Final[int]      = 3

TELEGRAM_API_BASE_URL           : Final[str]      = "https://api.telegram.org"

SENSITIVE_HEADER_KEYS           : Final[Set[str]] = {
    "authorization"
    , "cookie"
    , "set-cookie"
    , "x-api-key"
    , "x-secret"
    , "token"
    , "proxy-authorization"
}

