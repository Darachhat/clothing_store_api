"""Service layer exports with UPPERCASE_SNAKE_CASE template aliases."""
from app.services.auth_service import AUTH_SERVICE, AuthService
from app.services.base_service import BASE_SERVICE
from app.services.customer_service import CustomerService
from app.services.inventory_service import InventoryService
from app.services.log_service import LOG_SERVICE
from app.services.minio_service import MinioService, minio_service
from app.services.payment_service import PaymentService
from app.services.product_service import PRODUCT_SERVICE, ProductService
from app.services.purchase_service import PurchaseService
from app.services.sale_service import SaleService
from app.services.system_service import SYSTEM_SERVICE
from app.services.telegram_service import (
    TELEGRAM_BOT_SERVICE
    , TELEGRAM_CHAT_SERVICE
    , TELEGRAM_SERVICE
)

CUSTOMER_SERVICE  = CustomerService
INVENTORY_SERVICE = InventoryService
MINIO_SERVICE     = MinioService
PAYMENT_SERVICE   = PaymentService
PURCHASE_SERVICE  = PurchaseService
SALE_SERVICE      = SaleService

__all__ = [
    "AUTH_SERVICE"
    , "AuthService"
    , "BASE_SERVICE"
    , "CUSTOMER_SERVICE"
    , "CustomerService"
    , "INVENTORY_SERVICE"
    , "InventoryService"
    , "LOG_SERVICE"
    , "MINIO_SERVICE"
    , "MinioService"
    , "minio_service"
    , "PAYMENT_SERVICE"
    , "PaymentService"
    , "PRODUCT_SERVICE"
    , "ProductService"
    , "PURCHASE_SERVICE"
    , "PurchaseService"
    , "SALE_SERVICE"
    , "SaleService"
    , "SYSTEM_SERVICE"
    , "TELEGRAM_BOT_SERVICE"
    , "TELEGRAM_CHAT_SERVICE"
    , "TELEGRAM_SERVICE"
]

