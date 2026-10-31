"""Import all models so Alembic and SQLAlchemy metadata can detect them."""
from app.models.auth_model import (  # noqa: F401
    CREDENTIAL_API_KEY_MODEL
    , CREDENTIAL_BASIC_MODEL
    , CREDENTIAL_BEARER_MODEL
    , CREDENTIAL_OAUTH2_MODEL
    , SYSTEM_CLIENT_MODEL
    , SYSTEM_CREDENTIAL_MODEL
    , SYSTEM_ENDPOINT_MODEL
    , SYSTEM_MODEL
    , TELEGRAM_BOT_MODEL
    , TELEGRAM_CHAT_MODEL
)
from app.models.base import (  # noqa: F401
    Base
    , TEMPLATE_BASE_MODEL
    , TIMESTAMP_MIXIN
    , UUID_BASE_MODEL
    , UUIDBase
)
from app.models.base_data_model import (  # noqa: F401
    AUTH_TYPE_MODEL
    , CURRENCY_MODEL
    , LANGUAGE_MODEL
    , STATUS_MODEL
    , TRANSLATE_MODEL
)
from app.models.branch import Branch, Warehouse  # noqa: F401
from app.models.customer import Customer, LoyaltyAccount, LoyaltyTransaction  # noqa: F401
from app.models.inventory import (  # noqa: F401
    InventoryMovement
    , InventoryStock
    , StockTransfer
    , StockTransferItem
)
from app.models.misc import (  # noqa: F401
    AuditLog
    , Expense
    , ExpenseCategory
    , LabelTemplate
    , NotificationSetting
    , Promotion
)
from app.models.payment import PaymentTransaction  # noqa: F401
from app.models.product import (  # noqa: F401
    Brand
    , CatalogVersion
    , Category
    , Color
    , Product
    , ProductVariant
    , Size
    , Supplier
)
from app.models.purchase import (  # noqa: F401
    GoodsReceipt
    , GoodsReceiptItem
    , PurchaseItem
    , PurchaseOrder
)
from app.models.sale import (  # noqa: F401
    Return
    , ReturnItem
    , ReturnPayment
    , Sale
    , SaleItem
    , SalePayment
)
from app.models.track_model import (  # noqa: F401
    SYSTEM_LOG_MODEL
    , TELEGRAM_OUTBOUND_MODEL
)
from app.models.user import Permission, RefreshToken, Role, User  # noqa: F401

# Template UPPERCASE_SNAKE_CASE Model Aliases
BRANCH_MODEL               = Branch
WAREHOUSE_MODEL            = Warehouse
CUSTOMER_MODEL             = Customer
LOYALTY_ACCOUNT_MODEL      = LoyaltyAccount
LOYALTY_TRANSACTION_MODEL  = LoyaltyTransaction
INVENTORY_MOVEMENT_MODEL   = InventoryMovement
INVENTORY_STOCK_MODEL      = InventoryStock
STOCK_TRANSFER_MODEL       = StockTransfer
STOCK_TRANSFER_ITEM_MODEL  = StockTransferItem
AUDIT_LOG_MODEL            = AuditLog
EXPENSE_MODEL              = Expense
EXPENSE_CATEGORY_MODEL     = ExpenseCategory
LABEL_TEMPLATE_MODEL       = LabelTemplate
NOTIFICATION_SETTING_MODEL = NotificationSetting
PROMOTION_MODEL            = Promotion
PAYMENT_TRANSACTION_MODEL  = PaymentTransaction
BRAND_MODEL                = Brand
CATALOG_VERSION_MODEL      = CatalogVersion
CATEGORY_MODEL             = Category
COLOR_MODEL                = Color
PRODUCT_MODEL              = Product
PRODUCT_VARIANT_MODEL      = ProductVariant
SIZE_MODEL                 = Size
SUPPLIER_MODEL             = Supplier
GOODS_RECEIPT_MODEL        = GoodsReceipt
GOODS_RECEIPT_ITEM_MODEL   = GoodsReceiptItem
PURCHASE_ITEM_MODEL        = PurchaseItem
PURCHASE_ORDER_MODEL       = PurchaseOrder
RETURN_MODEL               = Return
RETURN_ITEM_MODEL          = ReturnItem
RETURN_PAYMENT_MODEL       = ReturnPayment
SALE_MODEL                 = Sale
SALE_ITEM_MODEL            = SaleItem
SALE_PAYMENT_MODEL         = SalePayment
PERMISSION_MODEL           = Permission
REFRESH_TOKEN_MODEL        = RefreshToken
ROLE_MODEL                 = Role
USER_MODEL                 = User

