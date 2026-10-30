"""Generic cache utilities: parameter normalization, hashing, and key builders."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.core.config import settings


class CacheService:
    """Base cache helper providing deterministic hashing and namespaced key generation."""

    @classmethod
    def normalize_query_params(cls, params: dict[str, Any]) -> dict[str, Any]:
        """
        Deterministically normalize query parameters:
        - Omit or normalize empty strings and null values
        - Lowercase search strings, categories, brands, sort directions
        - Enforce standard default values
        - Sort dictionary keys alphabetically
        """
        normalized: dict[str, Any] = {}

        # 1. Page and Page Size
        page = params.get("page")
        skip = params.get("skip")
        limit = params.get("limit") or params.get("page_size")

        if page is not None:
            try:
                page_val = int(page)
                normalized["page"] = max(1, page_val)
            except (ValueError, TypeError):
                normalized["page"] = 1
        elif skip is not None and limit is not None:
            try:
                s_val = int(skip)
                l_val = max(1, int(limit))
                normalized["page"] = (s_val // l_val) + 1
            except (ValueError, TypeError):
                normalized["page"] = 1
        else:
            normalized["page"] = 1

        if limit is not None:
            try:
                ps_val = int(limit)
                normalized["page_size"] = max(1, min(100, ps_val))
            except (ValueError, TypeError):
                normalized["page_size"] = 24
        else:
            normalized["page_size"] = 24

        # 2. Search query (search or q)
        search_val = params.get("search") or params.get("q")
        if search_val:
            s_clean = str(search_val).strip()
            if s_clean:
                normalized["search"] = s_clean.lower()

        # 3. Category (id or slug/name)
        cat_id = params.get("category_id")
        if cat_id:
            normalized["category_id"] = str(cat_id).strip().lower()

        cat_val = params.get("category")
        if cat_val:
            c_clean = str(cat_val).strip()
            if c_clean and c_clean.lower() != "all":
                normalized["category"] = c_clean.lower()

        # 4. Brand (id or slug/name)
        brand_id = params.get("brand_id")
        if brand_id:
            normalized["brand_id"] = str(brand_id).strip().lower()

        brand_val = params.get("brand")
        if brand_val:
            b_clean = str(brand_val).strip()
            if b_clean and b_clean.lower() != "all":
                normalized["brand"] = b_clean.lower()

        # 5. Status
        status_val = params.get("status")
        if status_val:
            st_clean = str(status_val).strip().upper()
            if st_clean and st_clean != "ALL":
                normalized["status"] = st_clean
            elif st_clean == "ALL":
                normalized["status"] = "ALL"
        else:
            normalized["status"] = "ACTIVE"

        # 6. Sorting
        sort_val = params.get("sort")
        if sort_val:
            normalized["sort"] = str(sort_val).strip().lower()
        else:
            normalized["sort"] = "created_at"

        sort_dir = params.get("sort_direction")
        if sort_dir:
            sd_clean = str(sort_dir).strip().lower()
            normalized["sort_direction"] = "asc" if sd_clean == "asc" else "desc"
        else:
            normalized["sort_direction"] = "desc"

        # 7. Branch & Warehouse
        branch_id = params.get("branch_id")
        if branch_id:
            normalized["branch_id"] = str(branch_id).strip().lower()

        warehouse_id = params.get("warehouse_id")
        if warehouse_id:
            normalized["warehouse_id"] = str(warehouse_id).strip().lower()

        # 8. Include Stock flag
        inc_stock = params.get("include_stock")
        if inc_stock is not None:
            if isinstance(inc_stock, str):
                normalized["include_stock"] = inc_stock.lower() in ("true", "1", "yes")
            else:
                normalized["include_stock"] = bool(inc_stock)
        else:
            normalized["include_stock"] = False

        # 9. Include Variants flag
        inc_variants = params.get("include_variants")
        if inc_variants is not None:
            if isinstance(inc_variants, str):
                normalized["include_variants"] = inc_variants.lower() in ("true", "1", "yes")
            else:
                normalized["include_variants"] = bool(inc_variants)
        else:
            normalized["include_variants"] = False

        # Return dict sorted deterministically by keys
        return dict(sorted(normalized.items()))

    @classmethod
    def generate_query_hash(cls, normalized_params: dict[str, Any]) -> str:
        """
        Generate deterministic 16-character SHA-256 hash of normalized parameters.
        Independent of parameter order.
        """
        canonical_json = json.dumps(normalized_params, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def build_cache_key(cls, namespace: str, query_hash: str) -> str:
        """
        Build namespaced cache key:
        {prefix}:{namespace}:data:{query_hash}
        """
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:{namespace}:data:{query_hash}"

    @classmethod
    def build_lock_key(cls, namespace: str, query_hash: str) -> str:
        """
        Build namespaced lock key:
        {prefix}:lock:{namespace}:{query_hash}
        """
        prefix = getattr(settings, "REDIS_CACHE_PREFIX", "clothing_store")
        return f"{prefix}:lock:{namespace}:{query_hash}"
