"""
Schema-oriented model registry:
- auth_schema_model       (schema: auth)
- base_data_schema_model  (schema: base_data)
- data_schema_model       (schema: data)
- track_schema_model      (schema: track)
- public_schema_model     (schema: public)
"""
from app.core.database import (  # noqa: F401
    Base,
    BASE_MODEL,
    TIMESTAMP_MIXIN,
    UUID_BASE_MODEL,
    TimestampMixin,
    UUIDBase,
)
from app.models.auth_schema_model import (  # noqa: F401
    CREDENTIAL_API_KEY_MODEL,
    CREDENTIAL_BASIC_MODEL,
    CREDENTIAL_BEARER_MODEL,
    CREDENTIAL_OAUTH2_MODEL,
    PHONE_VERIFICATION_MODEL,
    SYSTEM_CLIENT_MODEL,
    SYSTEM_CREDENTIAL_MODEL,
    SYSTEM_ENDPOINT_MODEL,
    SYSTEM_MODEL,
    TELEGRAM_AUTH_REPLAY_MODEL,
    TELEGRAM_BOT_MODEL,
    TELEGRAM_CHAT_MODEL,
)
from app.models.base_data_schema_model import (  # noqa: F401
    AUTH_TYPE_MODEL,
    BRAND_MODEL,
    CATEGORY_MODEL,
    COLOR_MODEL,
    CURRENCY_MODEL,
    EXPENSE_CATEGORY_MODEL,
    LABEL_TEMPLATE_MODEL,
    LANGUAGE_MODEL,
    PERMISSION_MODEL,
    PRODUCT_ATTRIBUTE_MODEL,
    PRODUCT_ATTRIBUTE_VALUE_MODEL,
    ROLE_MODEL,
    SIZE_MODEL,
    STATUS_MODEL,
    SYSTEM_SETTING_MODEL,
    TRANSLATE_MODEL,
    role_permissions,
)
from app.models.data_schema_model import (  # noqa: F401
    AUDIT_LOG_MODEL,
    BRANCH_MODEL,
    CATALOG_VERSION_MODEL,
    CUSTOMER_MODEL,
    EXPENSE_MODEL,
    GOODS_RECEIPT_ITEM_MODEL,
    GOODS_RECEIPT_MODEL,
    INVENTORY_MOVEMENT_MODEL,
    INVENTORY_STOCK_MODEL,
    LOYALTY_ACCOUNT_MODEL,
    LOYALTY_TRANSACTION_MODEL,
    NOTIFICATION_SETTING_MODEL,
    PAYMENT_TRANSACTION_MODEL,
    POS_SHIFT_MODEL,
    POS_TERMINAL_MODEL,
    PRODUCT_ATTRIBUTE_ASSIGNMENT_MODEL,
    PRODUCT_IMAGE_MODEL,
    PRODUCT_MODEL,
    PRODUCT_VARIANT_MODEL,
    PROMOTION_MODEL,
    PURCHASE_ITEM_MODEL,
    PURCHASE_ORDER_MODEL,
    REFRESH_TOKEN_MODEL,
    RETURN_ITEM_MODEL,
    RETURN_MODEL,
    RETURN_PAYMENT_MODEL,
    SALE_ITEM_MODEL,
    SALE_MODEL,
    SALE_PAYMENT_MODEL,
    STOCK_TRANSFER_ITEM_MODEL,
    STOCK_TRANSFER_MODEL,
    SUPPLIER_MODEL,
    USER_MODEL,
    WAREHOUSE_MODEL,
    user_roles,
)
from app.models.track_schema_model import (  # noqa: F401
    SYSTEM_LOG_MODEL,
    TELEGRAM_OUTBOUND_MODEL,
)
from app.models.public_schema_model import (  # noqa: F401
    ALEMBIC_VERSION_MODEL,
    AlembicVersion,
)

Color               = COLOR_MODEL
Size                = SIZE_MODEL
ExpenseCategory     = EXPENSE_CATEGORY_MODEL
LabelTemplate       = LABEL_TEMPLATE_MODEL
SystemSetting       = SYSTEM_SETTING_MODEL
ProductAttribute    = PRODUCT_ATTRIBUTE_MODEL
ProductAttributeValue = PRODUCT_ATTRIBUTE_VALUE_MODEL

User                = USER_MODEL
RefreshToken        = REFRESH_TOKEN_MODEL
Branch              = BRANCH_MODEL
Warehouse           = WAREHOUSE_MODEL
PosTerminal         = POS_TERMINAL_MODEL
PosShift            = POS_SHIFT_MODEL
Supplier            = SUPPLIER_MODEL
Product             = PRODUCT_MODEL
ProductVariant      = PRODUCT_VARIANT_MODEL
ProductImage        = PRODUCT_IMAGE_MODEL
ProductAttributeAssignment = PRODUCT_ATTRIBUTE_ASSIGNMENT_MODEL
CatalogVersion      = CATALOG_VERSION_MODEL
InventoryStock      = INVENTORY_STOCK_MODEL
InventoryMovement   = INVENTORY_MOVEMENT_MODEL
StockTransfer       = STOCK_TRANSFER_MODEL
StockTransferItem   = STOCK_TRANSFER_ITEM_MODEL
PurchaseOrder       = PURCHASE_ORDER_MODEL
PurchaseItem        = PURCHASE_ITEM_MODEL
GoodsReceipt        = GOODS_RECEIPT_MODEL
GoodsReceiptItem    = GOODS_RECEIPT_ITEM_MODEL
Sale                = SALE_MODEL
SaleItem            = SALE_ITEM_MODEL
SalePayment         = SALE_PAYMENT_MODEL
Return              = RETURN_MODEL
ReturnItem          = RETURN_ITEM_MODEL
ReturnPayment       = RETURN_PAYMENT_MODEL
Customer            = CUSTOMER_MODEL
LoyaltyAccount      = LOYALTY_ACCOUNT_MODEL
LoyaltyTransaction  = LOYALTY_TRANSACTION_MODEL
PaymentTransaction  = PAYMENT_TRANSACTION_MODEL
Expense             = EXPENSE_MODEL
Promotion           = PROMOTION_MODEL
AuditLog            = AUDIT_LOG_MODEL
NotificationSetting = NOTIFICATION_SETTING_MODEL
TelegramAuthReplay  = TELEGRAM_AUTH_REPLAY_MODEL
PhoneVerification   = PHONE_VERIFICATION_MODEL

# Declarative class registry bindings for string references
for _alias, _model in [
    ("ROLE_MODEL", ROLE_MODEL),
    ("PERMISSION_MODEL", PERMISSION_MODEL),
    ("CATEGORY_MODEL", CATEGORY_MODEL),
    ("BRAND_MODEL", BRAND_MODEL),
    ("Color", COLOR_MODEL),
    ("Size", SIZE_MODEL),
    ("ExpenseCategory", EXPENSE_CATEGORY_MODEL),
    ("LabelTemplate", LABEL_TEMPLATE_MODEL),
    ("User", USER_MODEL),
    ("RefreshToken", REFRESH_TOKEN_MODEL),
    ("Branch", BRANCH_MODEL),
    ("Warehouse", WAREHOUSE_MODEL),
    ("Supplier", SUPPLIER_MODEL),
    ("Product", PRODUCT_MODEL),
    ("ProductVariant", PRODUCT_VARIANT_MODEL),
    ("ProductImage", PRODUCT_IMAGE_MODEL),
    ("ProductAttribute", PRODUCT_ATTRIBUTE_MODEL),
    ("ProductAttributeValue", PRODUCT_ATTRIBUTE_VALUE_MODEL),
    ("ProductAttributeAssignment", PRODUCT_ATTRIBUTE_ASSIGNMENT_MODEL),
    ("PRODUCT_IMAGE_MODEL", PRODUCT_IMAGE_MODEL),
    ("PRODUCT_ATTRIBUTE_MODEL", PRODUCT_ATTRIBUTE_MODEL),
    ("PRODUCT_ATTRIBUTE_VALUE_MODEL", PRODUCT_ATTRIBUTE_VALUE_MODEL),
    ("PRODUCT_ATTRIBUTE_ASSIGNMENT_MODEL", PRODUCT_ATTRIBUTE_ASSIGNMENT_MODEL),
    ("CatalogVersion", CATALOG_VERSION_MODEL),
    ("InventoryStock", INVENTORY_STOCK_MODEL),
    ("InventoryMovement", INVENTORY_MOVEMENT_MODEL),
    ("StockTransfer", STOCK_TRANSFER_MODEL),
    ("StockTransferItem", STOCK_TRANSFER_ITEM_MODEL),
    ("PurchaseOrder", PURCHASE_ORDER_MODEL),
    ("PurchaseItem", PURCHASE_ITEM_MODEL),
    ("GoodsReceipt", GOODS_RECEIPT_MODEL),
    ("GoodsReceiptItem", GOODS_RECEIPT_ITEM_MODEL),
    ("Sale", SALE_MODEL),
    ("SaleItem", SALE_ITEM_MODEL),
    ("SalePayment", SALE_PAYMENT_MODEL),
    ("Return", RETURN_MODEL),
    ("ReturnItem", RETURN_ITEM_MODEL),
    ("ReturnPayment", RETURN_PAYMENT_MODEL),
    ("Customer", CUSTOMER_MODEL),
    ("LoyaltyAccount", LOYALTY_ACCOUNT_MODEL),
    ("LoyaltyTransaction", LOYALTY_TRANSACTION_MODEL),
    ("PaymentTransaction", PAYMENT_TRANSACTION_MODEL),
    ("Expense", EXPENSE_MODEL),
    ("Promotion", PROMOTION_MODEL),
    ("AuditLog", AUDIT_LOG_MODEL),
    ("NotificationSetting", NOTIFICATION_SETTING_MODEL),
]:
    Base.registry._class_registry[_alias] = _model

__all__ = [
    "Base",
    "BASE_MODEL",
    "UUID_BASE_MODEL",
    "UUIDBase",
    "SYSTEM_MODEL",
    "SYSTEM_CLIENT_MODEL",
    "SYSTEM_CREDENTIAL_MODEL",
    "CREDENTIAL_BASIC_MODEL",
    "CREDENTIAL_BEARER_MODEL",
    "CREDENTIAL_API_KEY_MODEL",
    "CREDENTIAL_OAUTH2_MODEL",
    "TELEGRAM_BOT_MODEL",
    "TELEGRAM_CHAT_MODEL",
    "TELEGRAM_AUTH_REPLAY_MODEL",
    "TelegramAuthReplay",
    "PHONE_VERIFICATION_MODEL",
    "PhoneVerification",
    "SYSTEM_ENDPOINT_MODEL",
    "TRANSLATE_MODEL",
    "STATUS_MODEL",
    "AUTH_TYPE_MODEL",
    "LANGUAGE_MODEL",
    "CURRENCY_MODEL",
    "ROLE_MODEL",
    "ROLE_MODEL",
    "PERMISSION_MODEL",
    "PERMISSION_MODEL",
    "role_permissions",
    "CATEGORY_MODEL",
    "CATEGORY_MODEL",
    "BRAND_MODEL",
    "BRAND_MODEL",
    "Color",
    "COLOR_MODEL",
    "Size",
    "SIZE_MODEL",
    "ExpenseCategory",
    "EXPENSE_CATEGORY_MODEL",
    "LabelTemplate",
    "LABEL_TEMPLATE_MODEL",
    "SystemSetting",
    "SYSTEM_SETTING_MODEL",
    "User",
    "USER_MODEL",
    "user_roles",
    "RefreshToken",
    "REFRESH_TOKEN_MODEL",
    "Branch",
    "BRANCH_MODEL",
    "Warehouse",
    "WAREHOUSE_MODEL",
    "PosTerminal",
    "POS_TERMINAL_MODEL",
    "PosShift",
    "POS_SHIFT_MODEL",
    "Supplier",
    "SUPPLIER_MODEL",
    "Product",
    "PRODUCT_MODEL",
    "ProductVariant",
    "PRODUCT_VARIANT_MODEL",
    "CatalogVersion",
    "CATALOG_VERSION_MODEL",
    "InventoryStock",
    "INVENTORY_STOCK_MODEL",
    "InventoryMovement",
    "INVENTORY_MOVEMENT_MODEL",
    "StockTransfer",
    "STOCK_TRANSFER_MODEL",
    "StockTransferItem",
    "STOCK_TRANSFER_ITEM_MODEL",
    "PurchaseOrder",
    "PURCHASE_ORDER_MODEL",
    "PurchaseItem",
    "PURCHASE_ITEM_MODEL",
    "GoodsReceipt",
    "GOODS_RECEIPT_MODEL",
    "GoodsReceiptItem",
    "GOODS_RECEIPT_ITEM_MODEL",
    "Sale",
    "SALE_MODEL",
    "SaleItem",
    "SALE_ITEM_MODEL",
    "SalePayment",
    "SALE_PAYMENT_MODEL",
    "Return",
    "RETURN_MODEL",
    "ReturnItem",
    "RETURN_ITEM_MODEL",
    "ReturnPayment",
    "RETURN_PAYMENT_MODEL",
    "Customer",
    "CUSTOMER_MODEL",
    "LoyaltyAccount",
    "LOYALTY_ACCOUNT_MODEL",
    "LoyaltyTransaction",
    "LOYALTY_TRANSACTION_MODEL",
    "PaymentTransaction",
    "PAYMENT_TRANSACTION_MODEL",
    "Expense",
    "EXPENSE_MODEL",
    "Promotion",
    "PROMOTION_MODEL",
    "AuditLog",
    "AUDIT_LOG_MODEL",
    "NotificationSetting",
    "NOTIFICATION_SETTING_MODEL",
    "SYSTEM_LOG_MODEL",
    "TELEGRAM_OUTBOUND_MODEL",
    "AlembicVersion",
    "ALEMBIC_VERSION_MODEL",
]
