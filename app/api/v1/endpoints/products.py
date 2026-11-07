"""Product API endpoints — re-exported from product_handler."""
from app.api.v1.handlers.product_handler import public_variant_media_router, router, variant_router

__all__ = ["router", "variant_router", "public_variant_media_router"]
