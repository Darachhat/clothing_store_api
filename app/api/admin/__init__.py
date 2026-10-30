"""Admin API lane — /api/admin/v1/

All routes require ADMIN or MANAGER role.
Auth endpoints (login/refresh/logout) are intentionally open within this lane.
"""
from fastapi import APIRouter, Depends

from app.api.admin.auth import require_admin_or_manager
from app.api.v1.endpoints.attachments import router as attachments_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.branches import router as branches_router
from app.api.v1.endpoints.catalog import (
    brands_router,
    categories_router,
    colors_router,
    sizes_router,
    suppliers_router,
)
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.expenses import router as expenses_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.inventory import transfers_router
from app.api.v1.endpoints.labels import router as labels_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.products import variant_router
from app.api.v1.endpoints.promotions import router as promotions_router
from app.api.v1.endpoints.purchases import router as purchases_router
from app.api.v1.endpoints.reports import router as reports_router
from app.api.v1.endpoints.sales import returns_router, router as sales_router
from app.api.v1.endpoints.users import roles_router, users_router

# Root lane router
admin_router = APIRouter(prefix="/api/admin/v1", tags=["[Admin Lane]"])

# ── Public within lane: auth (login/refresh/logout/me) ─────────────────────
admin_router.include_router(auth_router)

# ── Protected: all other endpoints require admin or manager role ───────────
_protected = APIRouter(dependencies=[Depends(require_admin_or_manager)])

_protected.include_router(products_router)
_protected.include_router(variant_router)
_protected.include_router(categories_router)
_protected.include_router(colors_router)
_protected.include_router(sizes_router)
_protected.include_router(brands_router)
_protected.include_router(suppliers_router)
_protected.include_router(purchases_router)
_protected.include_router(inventory_router)
_protected.include_router(transfers_router)
_protected.include_router(sales_router)
_protected.include_router(returns_router)
_protected.include_router(reports_router)
_protected.include_router(labels_router)
_protected.include_router(customers_router)
_protected.include_router(expenses_router)
_protected.include_router(promotions_router)
_protected.include_router(users_router)
_protected.include_router(roles_router)
_protected.include_router(branches_router)
_protected.include_router(attachments_router)

admin_router.include_router(_protected)
