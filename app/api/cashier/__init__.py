"""Cashier API lane — /api/cashier/v1/

Exposes a restricted surface of endpoints for the POS terminal:
  - Auth (login/refresh/logout/me) — open within lane
  - Scanner   — QR/barcode relay websocket + pairing
  - Products  — read-only product + variant lookup
  - Sales     — create sale, view own sales history
  - Returns   — create returns
  - Customers — quick lookup + create
  - Promotions — read-only (apply promos to cart)
  - Payments  — ABA PayWay KHQR (create, poll, cancel)

All non-auth endpoints require CASHIER (or ADMIN) role.
"""
from fastapi import APIRouter, Depends

from app.api.cashier.auth import require_cashier
from app.api.cashier.payments import router as payments_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.branches import router as branches_router
from app.api.v1.endpoints.catalog import (
    brands_router,
    categories_router,
    colors_router,
    sizes_router,
)
from app.api.v1.endpoints.customers import router as customers_router
from app.api.v1.endpoints.inventory import router as inventory_router
from app.api.v1.endpoints.labels import router as labels_router
from app.api.v1.endpoints.products import router as products_router
from app.api.v1.endpoints.products import variant_router
from app.api.v1.endpoints.promotions import router as promotions_router
from app.api.v1.endpoints.sales import returns_router, router as sales_router
from app.api.v1.endpoints.scanner import router as scanner_router

# Root lane router
cashier_router = APIRouter(prefix="/api/cashier/v1", tags=["[Cashier Lane]"])

# ── Public within lane: auth ───────────────────────────────────────────────
cashier_router.include_router(auth_router)

# ── Protected: CASHIER role required ──────────────────────────────────────
_protected = APIRouter(dependencies=[Depends(require_cashier)])

_protected.include_router(scanner_router)
_protected.include_router(products_router)
_protected.include_router(variant_router)
_protected.include_router(categories_router)
_protected.include_router(brands_router)
_protected.include_router(colors_router)
_protected.include_router(sizes_router)
_protected.include_router(inventory_router)
_protected.include_router(branches_router)
_protected.include_router(sales_router)
_protected.include_router(returns_router)
_protected.include_router(customers_router)
_protected.include_router(promotions_router)
_protected.include_router(payments_router)
_protected.include_router(labels_router)

cashier_router.include_router(_protected)

