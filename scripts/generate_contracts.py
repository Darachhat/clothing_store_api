#!/usr/bin/env python3
"""
Automated API Contract Generator: FastAPI OpenAPI -> TypeScript -> All Frontends.

This script:
1. Extracts the authoritative OpenAPI 3.1 specification from FastAPI backend.
2. Validates OpenAPI structure and saves shared-api/openapi.json.
3. Generates comprehensive TypeScript type definitions (schemas, enums, domain entities, response envelopes).
4. Distributes the generated contracts to all four frontends:
   - admin_front/app/types/api.generated.ts
   - stock_manager_front/app/types/api.generated.ts
   - cashier_front/app/types/api.generated.ts
   - web_store_front/app/types/api.generated.ts
5. Supports CI/CD verification via --check to prevent accidental contract drift.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

# Root and project directory discovery
ROOT_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name == "scripts" else Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
SHARED_API_DIR = ROOT_DIR / "shared-api"
GENERATED_DIR = SHARED_API_DIR / "generated"

FRONTEND_TARGETS = [
    ROOT_DIR / "admin_front" / "app" / "types" / "api.generated.ts",
    ROOT_DIR / "stock_manager_front" / "app" / "types" / "api.generated.ts",
    ROOT_DIR / "cashier_front" / "app" / "types" / "api.generated.ts",
    ROOT_DIR / "web_store_front" / "app" / "types" / "api.generated.ts",
]


def load_backend_openapi() -> Dict[str, Any]:
    """Import backend FastAPI app and retrieve raw OpenAPI specification."""
    sys.path.insert(0, str(BACKEND_DIR))
    # Provide safe fallback environment variables for offline schema generation
    os.environ.setdefault("ENV", "testing")
    os.environ.setdefault("PORT", "8000")
    os.environ.setdefault("DB_NAME", "clothing_store")
    os.environ.setdefault("DB_USER", "postgres")
    os.environ.setdefault("DB_PASSWORD", "postgres")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("SECRET_KEY", "temporary-secret-key-for-openapi-generation-only-32bytes")

    try:
        from app.main import app
        schema = app.openapi()
        if not schema or "components" not in schema:
            raise ValueError("Retrieved empty or invalid OpenAPI specification from FastAPI app.")
        return schema
    except Exception as exc:
        print(f"[ERROR] Failed to load FastAPI app OpenAPI: {exc}", file=sys.stderr)
        raise


def resolve_ref(ref_str: str) -> str:
    """Extract component name from a $ref path."""
    return ref_str.split("/")[-1]


def escape_string_literal(val: str) -> str:
    """Escape and quote string value for TypeScript string union."""
    escaped = val.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def schema_to_typescript(prop_schema: Dict[str, Any], indent_level: int = 2) -> str:
    """Convert an OpenAPI property schema or subschema to a TypeScript type string."""
    if "$ref" in prop_schema:
        return resolve_ref(prop_schema["$ref"])

    if "anyOf" in prop_schema:
        sub_types = [schema_to_typescript(sub, indent_level) for sub in prop_schema["anyOf"]]
        # deduplicate while preserving order
        unique_types: List[str] = []
        for st in sub_types:
            if st not in unique_types:
                unique_types.append(st)
        return " | ".join(unique_types)

    if "oneOf" in prop_schema:
        sub_types = [schema_to_typescript(sub, indent_level) for sub in prop_schema["oneOf"]]
        unique_types = []
        for st in sub_types:
            if st not in unique_types:
                unique_types.append(st)
        return " | ".join(unique_types)

    schema_type = prop_schema.get("type")

    if schema_type == "string":
        if "enum" in prop_schema:
            return " | ".join(escape_string_literal(str(e)) for e in prop_schema["enum"])
        return "string"

    if schema_type in ("integer", "number"):
        return "number"

    if schema_type == "boolean":
        return "boolean"

    if schema_type == "null":
        return "null"

    if schema_type == "array":
        items = prop_schema.get("items", {})
        item_type = schema_to_typescript(items, indent_level)
        if " | " in item_type and not (item_type.startswith("(") and item_type.endswith(")")):
            return f"({item_type})[]"
        return f"{item_type}[]"

    if schema_type == "object":
        properties = prop_schema.get("properties", {})
        additional = prop_schema.get("additionalProperties")
        if not properties:
            if isinstance(additional, dict):
                val_type = schema_to_typescript(additional, indent_level)
                return f"Record<string, {val_type}>"
            return "Record<string, unknown>"

        lines = ["{"]
        required_fields = set(prop_schema.get("required", []))
        indent_str = " " * indent_level
        for name, sub_prop in properties.items():
            is_required = name in required_fields
            opt_mark = "" if is_required else "?"
            ts_type = schema_to_typescript(sub_prop, indent_level + 2)
            desc = sub_prop.get("description")
            if desc:
                clean_desc = desc.replace("*/", "* /")
                lines.append(f"{indent_str}/** {clean_desc} */")
            lines.append(f"{indent_str}{name}{opt_mark}: {ts_type};")
        lines.append(" " * (indent_level - 2) + "}")
        return "\n".join(lines)

    return "unknown"


def generate_typescript_code(openapi: Dict[str, Any]) -> str:
    """Generate complete TypeScript definition file from OpenAPI dictionary."""
    schemas: Dict[str, Any] = openapi.get("components", {}).get("schemas", {})
    paths: Dict[str, Any] = openapi.get("paths", {})

    buffer: List[str] = [
        "/**",
        " * AUTO-GENERATED API CONTRACT DEFINITIONS",
        " * Source: FastAPI OpenAPI Specification",
        " * Repository: Clothing Store Management System",
        " *",
        " * DO NOT EDIT DIRECTLY. Regenerate using:",
        " *   python scripts/generate_contracts.py",
        " * Or run from any frontend workspace:",
        " *   npm run generate:contracts",
        " */",
        "",
        "/* eslint-disable */",
        "// @ts-nocheck",
        "",
    ]

    # 1. Enums and Simple String Unions
    buffer.append("// ============================================================================")
    buffer.append("// 1. SYSTEM ENUMS")
    buffer.append("// ============================================================================")
    buffer.append("")

    for name in sorted(schemas.keys()):
        schema = schemas[name]
        if schema.get("type") == "string" and "enum" in schema:
            desc = schema.get("description", "")
            if desc:
                buffer.append(f"/** {desc.replace('*/', '* /')} */")
            enum_values = " | ".join(escape_string_literal(str(v)) for v in schema["enum"])
            buffer.append(f"export type {name} = {enum_values};")
            buffer.append("")

    # 2. Schema Interfaces
    buffer.append("// ============================================================================")
    buffer.append("// 2. COMPONENT SCHEMAS")
    buffer.append("// ============================================================================")
    buffer.append("")

    for name in sorted(schemas.keys()):
        schema = schemas[name]
        if schema.get("type") == "string" and "enum" in schema:
            continue

        desc = schema.get("description", "")
        if desc:
            buffer.append(f"/** {desc.replace('*/', '* /')} */")

        properties = schema.get("properties", {})
        required_fields: Set[str] = set(schema.get("required", []))
        additional = schema.get("additionalProperties")

        if not properties and additional:
            if isinstance(additional, dict):
                val_type = schema_to_typescript(additional, 2)
                buffer.append(f"export type {name} = Record<string, {val_type}>;")
            else:
                buffer.append(f"export type {name} = Record<string, unknown>;")
            buffer.append("")
            continue

        buffer.append(f"export interface {name} {{")
        for prop_name, prop_def in properties.items():
            is_req = prop_name in required_fields
            opt = "" if is_req else "?"
            ts_type = schema_to_typescript(prop_def, 4)
            prop_desc = prop_def.get("description")
            if prop_desc:
                clean_pdesc = prop_desc.replace("*/", "* /")
                buffer.append(f"  /** {clean_pdesc} */")
            buffer.append(f"  {prop_name}{opt}: {ts_type};")

        buffer.append("}")
        buffer.append("")

    # 3. Canonical Domain Entity Contracts
    buffer.append("// ============================================================================")
    buffer.append("// 3. CANONICAL DOMAIN ENTITY CONTRACTS (SHARED ACROSS ALL 4 FRONTENDS)")
    buffer.append("// ============================================================================")
    buffer.append("")
    buffer.append("/** Standard JSON Response Envelope */")
    buffer.append("export interface ApiResponse<T = unknown> {")
    buffer.append("  code: RESPONSE_CODE_ENUM | string;")
    buffer.append("  message: string;")
    buffer.append("  data?: T | null;")
    buffer.append("  errors?: string[] | null;")
    buffer.append("  request_id?: string | null;")
    buffer.append("}")
    buffer.append("")
    buffer.append("/** Standard Pagination Metadata */")
    buffer.append("export type Pagination = PAGINATION_METADATA_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Error Response */")
    buffer.append("export interface ErrorResponse {")
    buffer.append("  code: RESPONSE_CODE_ENUM | string;")
    buffer.append("  message: string;")
    buffer.append("  errors?: string[] | null;")
    buffer.append("  request_id?: string | null;")
    buffer.append("  detail?: string | Array<{ loc?: (string | number)[]; msg?: string; type?: string }>;")
    buffer.append("}")
    buffer.append("")
    buffer.append("/** Canonical Product Entity */")
    buffer.append("export type Product = PRODUCT_WITH_VARIANTS_SCHEMA;")
    buffer.append("export type ProductBase = PRODUCT_RESPONSE_SCHEMA;")
    buffer.append("export type ProductWithVariants = PRODUCT_WITH_VARIANTS_SCHEMA;")
    buffer.append("export type ProductCreate = PRODUCT_CREATE_SCHEMA;")
    buffer.append("export type ProductUpdate = PRODUCT_UPDATE_SCHEMA;")
    buffer.append("export type ProductPagination = PRODUCT_PAGINATION_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Product Variant Entity */")
    buffer.append("export type ProductVariant = PRODUCT_VARIANT_RESPONSE_SCHEMA;")
    buffer.append("export type ProductVariantCreate = PRODUCT_VARIANT_CREATE_SCHEMA;")
    buffer.append("export type ProductVariantUpdate = PRODUCT_VARIANT_UPDATE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Customer Entity */")
    buffer.append("export type Customer = CUSTOMER_RESPONSE_SCHEMA;")
    buffer.append("export type CustomerCreate = CUSTOMER_CREATE_SCHEMA;")
    buffer.append("export type CustomerUpdate = CUSTOMER_UPDATE_SCHEMA;")
    buffer.append("export type CustomerListOut = CUSTOMER_LIST_OUT_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Sale & Order Entity */")
    buffer.append("export type Sale = SALE_RESPONSE_SCHEMA;")
    buffer.append("export type SaleCreate = SALE_CREATE_SCHEMA;")
    buffer.append("export type SaleItem = SALE_ITEM_RESPONSE_SCHEMA;")
    buffer.append("export type SaleItemCreate = SALE_ITEM_CREATE_SCHEMA;")
    buffer.append("export type SalePayment = SALE_PAYMENT_RESPONSE_SCHEMA;")
    buffer.append("export type SalePaymentCreate = SALE_PAYMENT_CREATE_SCHEMA;")
    buffer.append("export type Invoice = SALE_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Inventory Stock & Movement Entities */")
    buffer.append("export type InventoryStock = INVENTORY_STOCK_RESPONSE_SCHEMA;")
    buffer.append("export type InventoryMovement = INVENTORY_MOVEMENT_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Warehouse & Branch Entities */")
    buffer.append("export type Warehouse = WarehouseOut;")
    buffer.append("export type WarehouseCreate = BranchCreate;")
    buffer.append("export type Branch = BranchOut;")
    buffer.append("export type BranchCreateInput = BranchCreate;")
    buffer.append("export type BranchUpdateInput = BranchUpdate;")
    buffer.append("")
    buffer.append("/** Canonical Purchase Order Entity */")
    buffer.append("export type PurchaseOrder = PURCHASE_ORDER_RESPONSE_SCHEMA;")
    buffer.append("export type PurchaseItem = PURCHASE_ITEM_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Payment Entities */")
    buffer.append("export type PaymentTransaction = PAYMENT_TRANSACTION_RESPONSE_SCHEMA;")
    buffer.append("export type KhqrPaymentRequest = PAYMENT_KHQR_CREATE_REQUEST_SCHEMA;")
    buffer.append("export type PurchaseFormRequest = PAYMENT_PURCHASE_FORM_REQUEST_SCHEMA;")
    buffer.append("export type PurchaseFormResponse = PAYMENT_PURCHASE_FORM_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Catalog Entities */")
    buffer.append("export type Category = CATEGORY_RESPONSE_SCHEMA;")
    buffer.append("export type CategoryCreate = CATEGORY_CREATE_SCHEMA;")
    buffer.append("export type CategoryUpdate = CATEGORY_UPDATE_SCHEMA;")
    buffer.append("export type Brand = BRAND_RESPONSE_SCHEMA;")
    buffer.append("export type BrandCreate = BRAND_CREATE_SCHEMA;")
    buffer.append("export type BrandUpdate = BRAND_UPDATE_SCHEMA;")
    buffer.append("export type Color = COLOR_RESPONSE_SCHEMA;")
    buffer.append("export type ColorCreate = COLOR_CREATE_SCHEMA;")
    buffer.append("export type ColorUpdate = COLOR_UPDATE_SCHEMA;")
    buffer.append("export type Size = SIZE_RESPONSE_SCHEMA;")
    buffer.append("export type Supplier = SUPPLIER_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical Promotion & Coupon Entities */")
    buffer.append("export type Promotion = PROMOTION_RESPONSE_SCHEMA;")
    buffer.append("export type CouponValidationRequest = COUPON_VALIDATION_REQUEST_SCHEMA;")
    buffer.append("export type CouponValidationResponse = COUPON_VALIDATION_RESPONSE_SCHEMA;")
    buffer.append("")
    buffer.append("/** Canonical User, Role & Auth Entities */")
    buffer.append("export type User = USER_RESPONSE_SCHEMA;")
    buffer.append("export type Role = ROLE_RESPONSE_SCHEMA;")
    buffer.append("export type Permission = PERMISSION_RESPONSE_SCHEMA;")
    buffer.append("export type TokenResponse = TOKEN_RESPONSE_SCHEMA;")
    buffer.append("export type LoginResponse = LOGIN_RESPONSE_SCHEMA;")
    buffer.append("")

    return "\n".join(buffer)


def write_file_if_changed(target_path: Path, content: str, dry_run: bool = False) -> bool:
    """Write content to target_path only if changed, returning True if content differs."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        existing = target_path.read_text(encoding="utf-8")
        if existing == content:
            return False

    if not dry_run:
        target_path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Centralized OpenAPI Contract Generator for All Frontends")
    parser.add_argument("--check", action="store_true", help="CI/CD verification: check if generated contracts match repository files")
    args = parser.parse_args()

    print("[CONTRACT] Loading OpenAPI specification from FastAPI app...")
    openapi = load_backend_openapi()

    openapi_json_str = json.dumps(openapi, indent=2, ensure_ascii=False) + "\n"
    ts_code_str = generate_typescript_code(openapi) + "\n"

    openapi_path = SHARED_API_DIR / "openapi.json"
    shared_ts_path = GENERATED_DIR / "types.ts"

    changes_detected = False

    # Check/write openapi.json
    if write_file_if_changed(openapi_path, openapi_json_str, dry_run=args.check):
        print(f"[DIFF] {openapi_path} has differences.")
        changes_detected = True
    else:
        print(f"[OK] {openapi_path} is in sync.")

    # Check/write shared-api/generated/types.ts
    if write_file_if_changed(shared_ts_path, ts_code_str, dry_run=args.check):
        print(f"[DIFF] {shared_ts_path} has differences.")
        changes_detected = True
    else:
        print(f"[OK] {shared_ts_path} is in sync.")

    # Check/write to all 4 frontends
    for fe_target in FRONTEND_TARGETS:
        if write_file_if_changed(fe_target, ts_code_str, dry_run=args.check):
            print(f"[DIFF] {fe_target} has differences.")
            changes_detected = True
        else:
            print(f"[OK] {fe_target} is in sync.")

    if args.check:
        if changes_detected:
            print("[ERROR] Contract drift detected in CI check mode! Run `python scripts/generate_contracts.py` to regenerate.", file=sys.stderr)
            return 1
        print("[SUCCESS] All API contracts are verified and up-to-date!")
        return 0

    print("[SUCCESS] API contracts successfully generated and synchronized to all 4 frontends!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
