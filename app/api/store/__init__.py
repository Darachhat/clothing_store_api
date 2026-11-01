"""Web Store API lane — /api/store/v1/

Public-facing API for the customer web storefront.
  - /auth/**    — customer registration, login, token refresh
  - /catalog/** — public product catalog (no auth needed)

Future: orders, cart, account management.
"""
from fastapi import APIRouter

from app.api.store.endpoints.auth import router as store_auth_router
from app.api.store.endpoints.catalog import router as store_catalog_router
from app.api.store.endpoints.orders import router as store_orders_router

# Root lane router
store_router = APIRouter(prefix="/api/store/v1", tags=["[Store Lane]"])

store_router.include_router(store_auth_router)
store_router.include_router(store_catalog_router)
store_router.include_router(store_orders_router)
