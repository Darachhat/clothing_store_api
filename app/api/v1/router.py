from fastapi import APIRouter, Depends

from app.core.deps import require_system_admin
from app.api.v1.handlers.health_handler import router as health_router
from app.api.v1.handlers.auth_handler import router as auth_router
from app.api.v1.handlers.system_handler import router as system_router
from app.api.v1.handlers.telegram_handler import router as telegram_router
from app.api.v1.handlers.log_handler import router as log_router
from app.api.v1.handlers.product_handler import router as products_router, variant_router
from app.api.v1.handlers.attachment_handler import router as attachments_router, uploads_router
from app.api.v1.handlers.branch_handler import router as branches_router, warehouses_router
from app.api.v1.handlers.catalog_handler import (
    brands_router
    , categories_router
    , colors_router
    , sizes_router
    , suppliers_router
)
from app.api.v1.handlers.customer_handler import router as customers_router
from app.api.v1.handlers.expense_handler import router as expenses_router
from app.api.v1.handlers.inventory_handler import router as inventory_router, transfers_router
from app.api.v1.handlers.label_handler import router as labels_router
from app.api.v1.handlers.promotion_handler import router as promotions_router
from app.api.v1.handlers.purchase_handler import router as purchases_router
from app.api.v1.handlers.report_handler import router as reports_router
from app.api.v1.handlers.sale_handler import returns_router, router as sales_router
from app.api.v1.handlers.scanner_handler import router as scanner_router
from app.api.v1.handlers.user_handler import roles_router, users_router
from app.api.v1.handlers.audit_handler import router as audit_router

router = APIRouter()

# Core Template Handlers
router.include_router(health_router)
router.include_router(auth_router)
# System clients/credentials, Telegram bots/chats and system logs are infrastructure
# management surfaces: require the `settings.manage` permission (ADMIN).
_system_admin = [Depends(require_system_admin)]
router.include_router(system_router, dependencies=_system_admin)
router.include_router(telegram_router, dependencies=_system_admin)
router.include_router(log_router, dependencies=_system_admin)

# Domain Handlers
router.include_router(attachments_router)
router.include_router(uploads_router)
router.include_router(scanner_router)
router.include_router(products_router)
router.include_router(variant_router)
router.include_router(categories_router)
router.include_router(colors_router)
router.include_router(sizes_router)
router.include_router(brands_router)
router.include_router(suppliers_router)
router.include_router(purchases_router)
router.include_router(inventory_router)
router.include_router(transfers_router)
router.include_router(sales_router)
router.include_router(returns_router)
router.include_router(reports_router)
router.include_router(labels_router)
router.include_router(customers_router)
router.include_router(expenses_router)
router.include_router(promotions_router)
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(branches_router)
router.include_router(warehouses_router)
router.include_router(audit_router)
