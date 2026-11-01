"""
Database Schema Migration Script:
1. Creates schemas 'data' and 'base_data' if they don't exist.
2. Moves tables from 'public' to 'base_data' or 'data'.
3. Standardizes columns across all tables in 'base_data' and 'data':
   - status_code
   - created_datetime
   - updated_datetime
   - deleted_datetime
   - created_by
   - updated_by
   - deleted_by
4. Configures default search_path to 'data, base_data, auth, track, public'.
"""

import sys
sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from app.core.config import settings

url = (
    f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
engine = create_engine(url)

BASE_DATA_TABLES = [
    "roles",
    "permissions",
    "role_permissions",
    "categories",
    "brands",
    "colors",
    "sizes",
    "expense_categories",
    "label_templates",
]

DATA_TABLES = [
    "users",
    "user_roles",
    "refresh_tokens",
    "branches",
    "warehouses",
    "suppliers",
    "products",
    "product_variants",
    "inventory_stocks",
    "inventory_movements",
    "stock_transfers",
    "stock_transfer_items",
    "purchase_orders",
    "purchase_items",
    "goods_receipts",
    "goods_receipt_items",
    "sales",
    "sale_items",
    "sale_payments",
    "returns",
    "return_items",
    "return_payments",
    "customers",
    "loyalty_accounts",
    "loyalty_transactions",
    "payment_transactions",
    "expenses",
    "promotions",
    "catalog_versions",
    "audit_logs",
    "notification_settings",
]


def table_exists(conn, schema, tbl):
    res = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = :schema AND table_name = :tbl
    """), {"schema": schema, "tbl": tbl}).scalar()
    return res is not None


def column_exists(conn, schema, tbl, col):
    res = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :tbl AND column_name = :col
    """), {"schema": schema, "tbl": tbl, "col": col}).scalar()
    return res is not None


def run_migration():
    with engine.begin() as conn:
        print("[+] Creating schemas if not exist...")
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS data;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS base_data;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS track;"))

        # ── 1. Move base_data tables ──────────────────────────────────────────
        for tbl in BASE_DATA_TABLES:
            if table_exists(conn, "public", tbl):
                print(f"[-] Moving public.{tbl} -> base_data.{tbl}")
                conn.execute(text(f'ALTER TABLE public."{tbl}" SET SCHEMA base_data;'))
            elif table_exists(conn, "base_data", tbl):
                print(f"[=] Table base_data.{tbl} already in base_data")

        # ── 2. Move data tables ───────────────────────────────────────────────
        for tbl in DATA_TABLES:
            if table_exists(conn, "public", tbl):
                print(f"[-] Moving public.{tbl} -> data.{tbl}")
                conn.execute(text(f'ALTER TABLE public."{tbl}" SET SCHEMA data;'))
            elif table_exists(conn, "data", tbl):
                print(f"[=] Table data.{tbl} already in data")

        # ── 3. Standardize columns on all base_data and data tables ───────────
        all_targets = [("base_data", t) for t in BASE_DATA_TABLES] + [("data", t) for t in DATA_TABLES]
        
        # Also include any existing tables in base_data (e.g. auth_type, currency, language, status, translate)
        existing_base_rows = conn.execute(text("""
            SELECT table_name FROM information_schema.tables WHERE table_schema = 'base_data'
        """)).fetchall()
        for (t,) in existing_base_rows:
            if ("base_data", t) not in all_targets:
                all_targets.append(("base_data", t))

        for schema, tbl in all_targets:
            if not table_exists(conn, schema, tbl):
                continue

            # a) status / status_code
            has_status = column_exists(conn, schema, tbl, "status")
            has_status_code = column_exists(conn, schema, tbl, "status_code")
            if has_status and not has_status_code:
                print(f"  [{schema}.{tbl}] RENAME COLUMN status -> status_code")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" RENAME COLUMN "status" TO "status_code";'))
            elif not has_status and not has_status_code:
                print(f"  [{schema}.{tbl}] ADD COLUMN status_code")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "status_code" VARCHAR(50) DEFAULT \'active\' NOT NULL;'))

            # b) created_at / created_datetime
            has_created_at = column_exists(conn, schema, tbl, "created_at")
            has_created_dt = column_exists(conn, schema, tbl, "created_datetime")
            if has_created_at and not has_created_dt:
                print(f"  [{schema}.{tbl}] RENAME COLUMN created_at -> created_datetime")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" RENAME COLUMN "created_at" TO "created_datetime";'))
            elif not has_created_at and not has_created_dt:
                print(f"  [{schema}.{tbl}] ADD COLUMN created_datetime")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "created_datetime" TIMESTAMP DEFAULT now();'))

            # c) updated_at / updated_datetime
            has_updated_at = column_exists(conn, schema, tbl, "updated_at")
            has_updated_dt = column_exists(conn, schema, tbl, "updated_datetime")
            if has_updated_at and not has_updated_dt:
                print(f"  [{schema}.{tbl}] RENAME COLUMN updated_at -> updated_datetime")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" RENAME COLUMN "updated_at" TO "updated_datetime";'))
            elif not has_updated_at and not has_updated_dt:
                print(f"  [{schema}.{tbl}] ADD COLUMN updated_datetime")
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "updated_datetime" TIMESTAMP DEFAULT now();'))

            # d) deleted_datetime
            if not column_exists(conn, schema, tbl, "deleted_datetime"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "deleted_datetime" TIMESTAMP NULL;'))

            # e) created_by, updated_by, deleted_by
            if not column_exists(conn, schema, tbl, "created_by"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "created_by" VARCHAR(100) NULL;'))
            if not column_exists(conn, schema, tbl, "updated_by"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "updated_by" VARCHAR(100) NULL;'))
            if not column_exists(conn, schema, tbl, "deleted_by"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{tbl}" ADD COLUMN "deleted_by" VARCHAR(100) NULL;'))

        # ── 4. Set search_path ────────────────────────────────────────────────
        print("[+] Updating search_path for user and database...")
        conn.execute(text("ALTER USER dever SET search_path TO data, base_data, auth, track, public;"))
        conn.execute(text(f"ALTER DATABASE {settings.POSTGRES_DB} SET search_path TO data, base_data, auth, track, public;"))

    print("\n✅ Schema migration and column standardization completed successfully!")


if __name__ == "__main__":
    run_migration()

