from fastapi import APIRouter

from app.api.v1.handlers.health_handler import router as health_router
from app.api.v1.handlers.auth_handler import router as auth_router
from app.api.v1.handlers.system_handler import router as system_router
from app.api.v1.handlers.telegram_handler import router as telegram_router
from app.api.v1.handlers.log_handler import router as log_router
from app.api.v1.handlers.product_handler import router as products_router, variant_router

from app.api.v1.endpoints.attachments import router as attachments_router
from app.api.v1.endpoints.branches import router as branches_router
from app.api.v1.endpoints.catalog import (
    brands_router
    , categories_router
    , colors_router
    , sizes_router
    , suppliers_router
)
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.expenses import router as expenses_router
from app.api.v1.endpoints.inventory import router as inventory_router, transfers_router
from app.api.v1.endpoints.labels import router as labels_router
from app.api.v1.endpoints.promotions import router as promotions_router
from app.api.v1.endpoints.purchases import router as purchases_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.sales import returns_router, router as sales_router
from app.api.v1.endpoints.scanner import router as scanner_router
from app.api.v1.endpoints.users import roles_router, users_router

router = APIRouter()

# Core Template Handlers
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(system_router)
router.include_router(telegram_router)
router.include_router(log_router)

# Domain Handlers
router.include_router(attachments_router)
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

