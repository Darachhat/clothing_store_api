"""Product API endpoints — re-exported from product_handler."""
from app.api.v1.handlers.product_handler import router, variant_router

__all__ = ["router", "variant_router"]
