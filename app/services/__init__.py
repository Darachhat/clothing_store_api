"""Service layer exports with UPPERCASE_SNAKE_CASE template classes and aliases."""
from app.services.audit_service import AUDIT_SERVICE
from app.services.auth_service import AUTH_SERVICE
from app.services.base_service import BASE_SERVICE
from app.services.customer_service import CUSTOMER_SERVICE
from app.services.inventory_service import INVENTORY_SERVICE
from app.services.log_service import LOG_SERVICE
from app.services.minio_service import MINIO_SERVICE
from app.services.misc_service import (
    EXPENSE_SERVICE
    , PROMOTION_SERVICE
)
from app.services.payment_service import PAYMENT_SERVICE
from app.services.product_service import PRODUCT_SERVICE
from app.services.purchase_service import PURCHASE_SERVICE
from app.services.sale_service import SALE_SERVICE
from app.services.system_auth_service import SYSTEM_AUTH_SERVICE
from app.services.system_service import SYSTEM_SERVICE
from app.services.telegram_service import (
    TELEGRAM_BOT_SERVICE
    , TELEGRAM_CHAT_SERVICE
    , TELEGRAM_SERVICE
)

__all__ = [
    "AUDIT_SERVICE"
    , "AUDIT_SERVICE"
    , "BASE_SERVICE"
    , "CUSTOMER_SERVICE"
    , "EXPENSE_SERVICE"
    , "INVENTORY_SERVICE"
    , "LOG_SERVICE"
    , "MINIO_SERVICE"
    , "PAYMENT_SERVICE"
    , "PRODUCT_SERVICE"
    , "PROMOTION_SERVICE"
    , "PURCHASE_SERVICE"
    , "SALE_SERVICE"
    , "SYSTEM_AUTH_SERVICE"
    , "SYSTEM_SERVICE"
    , "TELEGRAM_BOT_SERVICE"
    , "TELEGRAM_CHAT_SERVICE"
    , "TELEGRAM_SERVICE"
]
