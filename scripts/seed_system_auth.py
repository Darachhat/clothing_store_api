"""
Seed script — registers inbound system credentials for all four Nuxt frontends.
Run inside the backend container:

  docker exec -w /app -e PYTHONPATH=/app clothing_store-backend \
      python scripts/seed_system_auth.py

Each system is created (or skipped if already exists), then an inbound Basic
credential is created and the hashed secret is stored.  The plain-text secret
is logged exactly once here — it matches what is already written into each
frontend's NUXT_API_BASE_AUTH .env value.

Columns (from actual DB schema):
  auth.system            : id, code, name, description, status_code, created_datetime, updated_datetime
  auth.credential_basic  : id, system_code, traffic_type, username, password, status_code, created_datetime, updated_datetime
"""

import sys
sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.system_auth_service import hash_inbound_secret

FRONTENDS = [
    {
        "code":          "admin_front",
        "name":          "Admin Portal",
        "description":   "Clothing Store Admin & Management Portal",
        "client_secret": "YE2CZGYeISGYP2hW0mR5vR24iEHfhUI_lThZccne5Eg",
    },
    {
        "code":          "cashier_front",
        "name":          "Cashier POS Terminal",
        "description":   "Clothing Store Cashier Point-of-Sale",
        "client_secret": "EmOykZ1gP3zAyAsXi11eVghzLgpFbUEowzRuzR0s7Kw",
    },
    {
        "code":          "stock_manager_front",
        "name":          "Stock & Warehouse Manager",
        "description":   "Clothing Store Stock & Warehouse Operations",
        "client_secret": "hLaTNtOYFMKO-9u65c201P102Z9PW1dq7QHWM-QMVUs",
    },
    {
        "code":          "web_store_front",
        "name":          "Public Web Store",
        "description":   "Clothing Store Public E-Commerce Storefront",
        "client_secret": "Qjsq3KJUJ4IFVccAsbzXRFz2Y-KLyFQh7knEeIpnsPE",
    },
]


def get_engine():
    url = (
        f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    return create_engine(url)


def seed(db: Session):
    for fe in FRONTENDS:
        code   = fe["code"]
        secret = fe["client_secret"]

        # ── 1. Upsert auth.system (keyed on code) ────────────────────────────
        system = db.execute(
            text("SELECT id FROM auth.system WHERE code = :code AND deleted_datetime IS NULL"),
            {"code": code},
        ).fetchone()

        if system is None:
            db.execute(
                text("""
                    INSERT INTO auth.system
                        (code, name, description, status_code, created_datetime, updated_datetime)
                    VALUES
                        (:code, :name, :desc, 'active', now(), now())
                """),
                {"code": code, "name": fe["name"], "desc": fe["description"]},
            )
            db.flush()
            print(f"[+] Created system: {code}")
        else:
            print(f"[=] System already exists: {code}")

        # ── 2. Check for existing inbound basic credential ────────────────────
        existing = db.execute(
            text("""
                SELECT id FROM auth.credential_basic
                WHERE system_code = :code
                  AND traffic_type = 'inbound'
                  AND deleted_datetime IS NULL
            """),
            {"code": code},
        ).fetchone()

        if existing is not None:
            print(f"[=] Inbound credential already exists for {code}, skipping.")
            continue

        # ── 3. Hash the secret and insert credential ──────────────────────────
        # username = client code, password = sha256-hashed secret
        hashed = hash_inbound_secret(secret)
        db.execute(
            text("""
                INSERT INTO auth.credential_basic
                    (system_code, username, password, traffic_type, status_code, created_datetime, updated_datetime)
                VALUES
                    (:code, :username, :password, 'inbound', 'active', now(), now())
            """),
            {"code": code, "username": code, "password": hashed},
        )
        print(f"[+] Created inbound credential for {code}  (sha256 hash stored)")

    db.commit()
    print("\n✅  Seed complete.")


if __name__ == "__main__":
    engine = get_engine()
    with Session(engine) as db:
        seed(db)

