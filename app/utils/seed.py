"""
Development seed script — populates the database with realistic clothing retail sample data.
WARNING: For development use only. Do NOT run in production.

Usage:
    python -m app.utils.seed
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from loguru import logger
from slugify import slugify
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.branch import Branch, Warehouse
from app.models.customer import Customer, LoyaltyAccount
from app.models.inventory import InventoryStock
from app.models.misc import ExpenseCategory
from app.models.product import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.models.user import Permission, Role, User

if settings.ENVIRONMENT == "production":
    logger.error("⛔ Seed script cannot be run in production!")
    sys.exit(1)


PERMISSIONS = [
    ("product.read", "View Products", "products"),
    ("product.create", "Create Products", "products"),
    ("product.update", "Update Products", "products"),
    ("product.delete", "Delete Products", "products"),
    ("inventory.read", "View Inventory", "inventory"),
    ("inventory.adjust", "Adjust Stock", "inventory"),
    ("inventory.transfer", "Transfer Stock", "inventory"),
    ("sale.read", "View Sales", "sales"),
    ("sale.create", "Create Sales", "sales"),
    ("sale.refund", "Process Refunds", "sales"),
    ("purchase.read", "View Purchases", "purchases"),
    ("purchase.receive", "Receive Goods", "purchases"),
    ("customer.read", "View Customers", "customers"),
    ("customer.create", "Create Customers", "customers"),
    ("customer.update", "Update Customers", "customers"),
    ("report.read", "View Reports", "reports"),
    ("user.manage", "Manage Users", "users"),
    ("settings.manage", "Manage Settings", "settings"),
]

ROLES = {
    "ADMIN": [p[0] for p in PERMISSIONS],
    "MANAGER": [
        "product.read", "product.create", "product.update",
        "inventory.read", "inventory.adjust", "inventory.transfer",
        "sale.read", "sale.create", "sale.refund",
        "purchase.read", "purchase.receive",
        "customer.read", "customer.create", "customer.update",
        "report.read",
    ],
    "CASHIER": [
        "product.read",
        "inventory.read",
        "sale.read", "sale.create",
        "customer.read", "customer.create",
    ],
    "WAREHOUSE": [
        "product.read",
        "inventory.read", "inventory.adjust", "inventory.transfer",
        "purchase.read", "purchase.receive",
    ],
}

CATEGORIES = [
    ("T-Shirts", "Classic, graphic, and premium tees"),
    ("Jeans", "Slim, straight, relaxed, and wide-leg denim"),
    ("Hoodies", "Pullover, zip-up, oversized, and graphic fleece"),
    ("Jackets", "Denim, bomber, varsity, and windbreaker outerwear"),
    ("Dresses", "Casual midi, summer, sweater, and floral dresses"),
    ("Shoes", "Sneakers, running shoes, casual shoes, and loafers"),
    ("Accessories", "Caps, backpacks, belts, and sunglasses"),
    ("Shorts", "Casual and athletic shorts"),
]

BRANDS = [
    "FashionX",
    "UrbanWear",
    "ComfortStyle",
    "TrendSetters",
    "StreetMode",
    "EssentialWear",
    "ModernFit",
]

COLORS = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Navy", "#001F5B"),
    ("Gray", "#808080"),
    ("Charcoal", "#36454F"),
    ("Red", "#DC2626"),
    ("Blue", "#2563EB"),
    ("Light Blue", "#7DD3FC"),
    ("Green", "#16A34A"),
    ("Olive", "#556B2F"),
    ("Beige", "#F5F5DC"),
    ("Brown", "#8B4513"),
    ("Hot Pink", "#FF69B4"),
    ("Deep Purple", "#4B0082"),
]

SIZES = [
    ("XS", "LETTER", 0),
    ("S", "LETTER", 1),
    ("M", "LETTER", 2),
    ("L", "LETTER", 3),
    ("XL", "LETTER", 4),
    ("XXL", "LETTER", 5),
    ("28", "NUMERIC", 10),
    ("30", "NUMERIC", 11),
    ("32", "NUMERIC", 12),
    ("34", "NUMERIC", 13),
    ("36", "NUMERIC", 14),
    ("40", "NUMERIC", 20),
    ("41", "NUMERIC", 21),
    ("42", "NUMERIC", 22),
    ("43", "NUMERIC", 23),
    ("44", "NUMERIC", 24),
    ("ONE SIZE", "CUSTOM", 99),
]

CATALOG_PRODUCTS = [
    # ── T-Shirts ──
    {
        "code": "PROD-00001",
        "name": "Premium Cotton T-Shirt",
        "category": "T-Shirts",
        "brand": "FashionX",
        "prefix": "PCT",
        "description": "Ultra-soft 100% combed ring-spun cotton tee with tailored fit and durable ribbed collar.",
        "colors": ["Black", "White", "Navy", "Gray"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 6.50,
        "price": 19.99,
        "image_file": "premium-cotton-t-shirt.jpg",
        "stock_plan": {"Black/M": 24, "Black/L": 18, "Black/XL": 7, "White/M": 15, "White/L": 0},
    },
    {
        "code": "PROD-00002",
        "name": "Oversized Graphic Tee",
        "category": "T-Shirts",
        "brand": "StreetMode",
        "prefix": "OGT",
        "description": "Heavyweight 240 GSM streetwear tee with drop-shoulder silhouette and vintage fade wash.",
        "colors": ["Black", "White", "Charcoal"],
        "sizes": ["M", "L", "XL"],
        "cost": 8.00,
        "price": 24.99,
        "image_file": "oversized-graphic-tee.jpg",
    },
    {
        "code": "PROD-00003",
        "name": "Basic Crew Neck Tee",
        "category": "T-Shirts",
        "brand": "EssentialWear",
        "prefix": "BCN",
        "description": "Everyday casual crew neck essentials made from breathable organic cotton blend.",
        "colors": ["Black", "White", "Gray", "Navy"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 4.50,
        "price": 14.99,
        "image_file": "basic-crew-neck-tee.jpg",
    },
    {
        "code": "PROD-00004",
        "name": "Polo Shirt",
        "category": "T-Shirts",
        "brand": "ModernFit",
        "prefix": "POLO",
        "description": "Classic piqued cotton polo with two-button placket and vented hem for smart-casual wear.",
        "colors": ["Navy", "White", "Black", "Red"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 9.00,
        "price": 28.00,
        "image_file": "polo-shirt.jpg",
    },

    # ── Jeans ──
    {
        "code": "PROD-00005",
        "name": "Slim Fit Jeans",
        "category": "Jeans",
        "brand": "UrbanWear",
        "prefix": "SFJ",
        "description": "Tailored slim-fit stretch denim with mid-rise waist, 5-pocket styling, and whiskered wash.",
        "colors": ["Navy", "Black", "Blue"],
        "sizes": ["28", "30", "32", "34"],
        "cost": 14.00,
        "price": 39.99,
        "image_file": "slim-fit-jeans.jpg",
        "stock_plan": {"Navy/30": 18, "Navy/32": 12, "Black/30": 3, "Black/32": 0},
    },
    {
        "code": "PROD-00006",
        "name": "Straight Leg Jeans",
        "category": "Jeans",
        "brand": "ComfortStyle",
        "prefix": "SLJ",
        "description": "Authentic regular-fit straight cut crafted from non-stretch ring-spun cotton denim.",
        "colors": ["Blue", "Black"],
        "sizes": ["30", "32", "34", "36"],
        "cost": 15.00,
        "price": 42.00,
        "image_file": "straight-leg-jeans.jpg",
    },
    {
        "code": "PROD-00007",
        "name": "Relaxed Jeans",
        "category": "Jeans",
        "brand": "TrendSetters",
        "prefix": "RLXJ",
        "description": "Relaxed loose-fit skate jeans with roomy thigh room and gentle ankle taper.",
        "colors": ["Blue", "Light Blue", "Black"],
        "sizes": ["30", "32", "34"],
        "cost": 16.50,
        "price": 45.00,
        "image_file": "relaxed-jeans.jpg",
    },
    {
        "code": "PROD-00008",
        "name": "Wide Leg Jeans",
        "category": "Jeans",
        "brand": "StreetMode",
        "prefix": "WLJ",
        "description": "90s inspired high-waisted wide leg denim with relaxed draping and stonewashed finish.",
        "colors": ["Blue", "Black"],
        "sizes": ["28", "30", "32", "34"],
        "cost": 17.00,
        "price": 48.00,
        "image_file": "wide-leg-jeans.jpg",
    },

    # ── Hoodies ──
    {
        "code": "PROD-00009",
        "name": "Basic Pullover Hoodie",
        "category": "Hoodies",
        "brand": "EssentialWear",
        "prefix": "BPH",
        "description": "Plush fleece-lined pullover hoodie with pouch pocket, matching drawstrings, and ribbed cuffs.",
        "colors": ["Black", "Gray", "Navy"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 12.00,
        "price": 34.99,
        "image_file": "basic-pullover-hoodie.jpg",
    },
    {
        "code": "PROD-00010",
        "name": "Oversized Hoodie",
        "category": "Hoodies",
        "brand": "TrendSetters",
        "prefix": "OSH",
        "description": "Boxy oversized streetwear hoodie made from 380 GSM heavyweight French terry cotton.",
        "colors": ["Beige", "Black", "Olive"],
        "sizes": ["M", "L", "XL"],
        "cost": 15.00,
        "price": 44.99,
        "image_file": "oversized-hoodie.jpg",
    },
    {
        "code": "PROD-00011",
        "name": "Zip-Up Hoodie",
        "category": "Hoodies",
        "brand": "ModernFit",
        "prefix": "ZUH",
        "description": "Full-zip athletic hoodie featuring YKK metal zipper, split kangaroo pocket, and double hood.",
        "colors": ["Gray", "Black", "Navy"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 14.00,
        "price": 38.00,
        "image_file": "zip-up-hoodie.jpg",
    },
    {
        "code": "PROD-00012",
        "name": "Graphic Hoodie",
        "category": "Hoodies",
        "brand": "StreetMode",
        "prefix": "GHD",
        "description": "Statement graphic hoodie printed with high-density screenprint ink on premium cotton fleece.",
        "colors": ["Black", "White"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 16.00,
        "price": 42.00,
        "image_file": "graphic-hoodie.jpg",
    },

    # ── Jackets ──
    {
        "code": "PROD-00013",
        "name": "Denim Jacket",
        "category": "Jackets",
        "brand": "FashionX",
        "prefix": "DNJ",
        "description": "Timeless trucker jacket with button-flap chest pockets and adjustable waist tabs.",
        "colors": ["Blue", "Black"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 22.00,
        "price": 59.99,
        "image_file": "denim-jacket.jpg",
    },
    {
        "code": "PROD-00014",
        "name": "Bomber Jacket",
        "category": "Jackets",
        "brand": "UrbanWear",
        "prefix": "BMJ",
        "description": "Classic flight bomber with satin nylon shell, ribbed knit collar, and utility sleeve pocket.",
        "colors": ["Black", "Olive"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 24.00,
        "price": 64.99,
        "image_file": "bomber-jacket.jpg",
    },
    {
        "code": "PROD-00015",
        "name": "Varsity Jacket",
        "category": "Jackets",
        "brand": "TrendSetters",
        "prefix": "VSJ",
        "description": "Retro collegiate jacket with wool blend body, contrast faux leather sleeves, and snap buttons.",
        "colors": ["Navy", "Black", "Green"],
        "sizes": ["M", "L", "XL"],
        "cost": 28.00,
        "price": 75.00,
        "image_file": "varsity-jacket.jpg",
    },
    {
        "code": "PROD-00016",
        "name": "Lightweight Jacket",
        "category": "Jackets",
        "brand": "EssentialWear",
        "prefix": "LWJ",
        "description": "Water-resistant windbreaker jacket with packable hood, mesh lining, and zippered pockets.",
        "colors": ["Black", "Navy", "Olive"],
        "sizes": ["S", "M", "L", "XL"],
        "cost": 18.00,
        "price": 49.99,
        "image_file": "lightweight-jacket.jpg",
    },

    # ── Dresses ──
    {
        "code": "PROD-00017",
        "name": "Casual Midi Dress",
        "category": "Dresses",
        "brand": "ComfortStyle",
        "prefix": "CMD",
        "description": "Flowy A-line midi dress with breathable viscose weave, side slit, and adjustable waist tie.",
        "colors": ["Red", "Black", "Navy"],
        "sizes": ["XS", "S", "M", "L"],
        "cost": 14.00,
        "price": 38.00,
        "image_file": "casual-midi-dress.jpg",
    },
    {
        "code": "PROD-00018",
        "name": "Summer Dress",
        "category": "Dresses",
        "brand": "TrendSetters",
        "prefix": "SMD",
        "description": "Light and breezy sleeveless summer slip dress in tiered silhouette with ruffled hem.",
        "colors": ["White", "Beige", "Red"],
        "sizes": ["S", "M", "L"],
        "cost": 12.00,
        "price": 32.00,
        "image_file": "summer-dress.jpg",
    },
    {
        "code": "PROD-00019",
        "name": "Long Sleeve Dress",
        "category": "Dresses",
        "brand": "ModernFit",
        "prefix": "LSD",
        "description": "Elegant ribbed knit long sleeve sweater dress with flattering bodycon fit and mock neck.",
        "colors": ["Green", "Black", "Brown"],
        "sizes": ["S", "M", "L"],
        "cost": 18.00,
        "price": 48.00,
        "image_file": "long-sleeve-dress.jpg",
    },
    {
        "code": "PROD-00020",
        "name": "Floral Dress",
        "category": "Dresses",
        "brand": "FashionX",
        "prefix": "FLD",
        "description": "Charming floral chiffon wrap dress with fluttering sleeves and delicate waist sash.",
        "colors": ["Red", "Blue", "White"],
        "sizes": ["XS", "S", "M", "L"],
        "cost": 16.00,
        "price": 42.00,
        "image_file": "floral-dress.jpg",
    },

    # ── Shoes ──
    {
        "code": "PROD-00021",
        "name": "Sneakers",
        "category": "Shoes",
        "brand": "UrbanWear",
        "prefix": "SNK",
        "description": "Low-top lifestyle sneakers with genuine leather overlays, cushioned insole, and rubber cupsole.",
        "colors": ["White", "Black"],
        "sizes": ["40", "41", "42", "43", "44"],
        "cost": 25.00,
        "price": 69.99,
        "image_file": "sneakers.jpg",
    },
    {
        "code": "PROD-00022",
        "name": "Running Shoes",
        "category": "Shoes",
        "brand": "EssentialWear",
        "prefix": "RNS",
        "description": "High-performance road running shoes with responsive EVA foam midsole and breathable mesh upper.",
        "colors": ["Red", "Black", "Blue"],
        "sizes": ["40", "41", "42", "43"],
        "cost": 30.00,
        "price": 79.99,
        "image_file": "running-shoes.jpg",
    },
    {
        "code": "PROD-00023",
        "name": "Casual Shoes",
        "category": "Shoes",
        "brand": "StreetMode",
        "prefix": "CSH",
        "description": "Classic canvas skate slip-ons with vulcanized waffle outsole and padded collar.",
        "colors": ["Black", "Navy"],
        "sizes": ["40", "41", "42", "43"],
        "cost": 18.00,
        "price": 49.99,
        "image_file": "casual-shoes.jpg",
    },
    {
        "code": "PROD-00024",
        "name": "Loafers",
        "category": "Shoes",
        "brand": "ModernFit",
        "prefix": "LFR",
        "description": "Hand-stitched leather penny loafers with comfortable stacked heel and durable leather lining.",
        "colors": ["Brown", "Black"],
        "sizes": ["40", "41", "42", "43", "44"],
        "cost": 35.00,
        "price": 89.99,
        "image_file": "loafers.jpg",
    },

    # ── Accessories ──
    {
        "code": "PROD-00025",
        "name": "Cap",
        "category": "Accessories",
        "brand": "StreetMode",
        "prefix": "CAP",
        "description": "Structured 6-panel cotton twill dad cap with curved brim and brass metal buckle closure.",
        "colors": ["Black", "Navy", "Beige"],
        "sizes": ["ONE SIZE"],
        "cost": 5.00,
        "price": 16.00,
        "image_file": "cap.jpg",
    },
    {
        "code": "PROD-00026",
        "name": "Backpack",
        "category": "Accessories",
        "brand": "UrbanWear",
        "prefix": "BPK",
        "description": "Durable 22L everyday commute backpack with padded 15-inch laptop sleeve and water bottle pockets.",
        "colors": ["Black", "Brown", "Gray"],
        "sizes": ["ONE SIZE"],
        "cost": 18.00,
        "price": 49.99,
        "image_file": "backpack.jpg",
    },
    {
        "code": "PROD-00027",
        "name": "Belt",
        "category": "Accessories",
        "brand": "FashionX",
        "prefix": "BLT",
        "description": "Full-grain genuine Italian leather dress belt with brushed nickel single-prong buckle.",
        "colors": ["Brown", "Black"],
        "sizes": ["ONE SIZE"],
        "cost": 8.00,
        "price": 24.00,
        "image_file": "belt.jpg",
    },
    {
        "code": "PROD-00028",
        "name": "Sunglasses",
        "category": "Accessories",
        "brand": "TrendSetters",
        "prefix": "SGL",
        "description": "Polarized UV400 classic wayfarer sunglasses with lightweight acetate frame and glare reduction.",
        "colors": ["Black", "Brown"],
        "sizes": ["ONE SIZE"],
        "cost": 10.00,
        "price": 29.99,
        "image_file": "sunglasses.jpg",
    },
]

EXPENSE_CATEGORIES = [
    ("RENT", "Rent & Lease"),
    ("SALARY", "Salaries & Wages"),
    ("ELECTRICITY", "Electricity & Utilities"),
    ("INTERNET", "Internet & Telecom"),
    ("DELIVERY", "Delivery & Shipping"),
    ("MARKETING", "Marketing & Advertising"),
    ("MAINTENANCE", "Maintenance & Repairs"),
    ("OTHER", "Other Expenses"),
]


async def create_sequences(db) -> None:
    """Create all PostgreSQL sequences for business identifiers."""
    sequences = [
        "qr_reference_seq",
        "invoice_number_seq",
        "po_number_seq",
        "gr_number_seq",
        "transfer_number_seq",
        "return_number_seq",
        "expense_number_seq",
        "customer_code_seq",
        "supplier_code_seq",
    ]
    for seq in sequences:
        await db.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1 INCREMENT 1"))


async def get_or_create(db, model, filter_by: dict, defaults: dict = None):
    """Idempotently fetch or create an entity."""
    stmt = select(model).filter_by(**filter_by)
    res = await db.execute(stmt)
    instance = res.scalar_one_or_none()
    if instance:
        if defaults:
            for k, v in defaults.items():
                setattr(instance, k, v)
        return instance, False
    params = {**filter_by, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    await db.flush()
    return instance, True


async def seed() -> None:
    from app.core.database import Base, sync_engine

    Base.metadata.create_all(bind=sync_engine)

    async with AsyncSessionLocal() as db:
        logger.info("🌱 Starting idempotent retail POS seed...")

        await create_sequences(db)

        # ── 1. Branch & Warehouse ──────────────────────────────────────────
        branch, _ = await get_or_create(
            db, Branch, {"code": "HQ"}, {"name": "Main Branch", "status": "ACTIVE"}
        )
        warehouse, _ = await get_or_create(
            db,
            Warehouse,
            {"branch_id": branch.id, "name": "Main Warehouse"},
            {"is_default": True, "status": "ACTIVE"},
        )
        logger.info(f"✅ Branch ({branch.name}) & Warehouse ({warehouse.name}) ready")

        # ── 2. Permissions & Roles ────────────────────────────────────────
        perm_map: dict[str, Permission] = {}
        for code, name, module in PERMISSIONS:
            p, _ = await get_or_create(db, Permission, {"code": code}, {"name": name, "module": module})
            perm_map[code] = p

        role_map: dict[str, Role] = {}
        for role_name, perm_codes in ROLES.items():
            role, _ = await get_or_create(
                db,
                Role,
                {"name": role_name},
                {"is_system": True, "description": f"System {role_name} role"},
            )
            role.permissions = [perm_map[code] for code in perm_codes if code in perm_map]
            role_map[role_name] = role
        await db.flush()
        logger.info("✅ Permissions & System Roles ready")

        # ── 3. Users (admin / manager / cashier) ───────────────────────────
        admin, _ = await get_or_create(
            db,
            User,
            {"username": "admin"},
            {
                "email": settings.SEED_ADMIN_EMAIL,
                "full_name": "System Administrator",
                "hashed_password": hash_password(settings.SEED_ADMIN_PASSWORD),
                "branch_id": branch.id,
                "status": "ACTIVE",
                "employee_code": "EMP-001",
            },
        )
        admin.roles = [role_map["ADMIN"]]

        manager, _ = await get_or_create(
            db,
            User,
            {"username": "manager"},
            {
                "email": "manager@example.com",
                "full_name": "Store Manager",
                "hashed_password": hash_password("manager123"),
                "branch_id": branch.id,
                "status": "ACTIVE",
                "employee_code": "EMP-002",
            },
        )
        manager.roles = [role_map["MANAGER"]]

        cashier, _ = await get_or_create(
            db,
            User,
            {"username": "cashier"},
            {
                "email": "cashier@example.com",
                "full_name": "Front Cashier",
                "hashed_password": hash_password("cashier123"),
                "branch_id": branch.id,
                "status": "ACTIVE",
                "employee_code": "EMP-003",
            },
        )
        cashier.roles = [role_map["CASHIER"]]
        await db.flush()
        logger.info("✅ Seed user credentials verified (admin / manager / cashier)")

        # ── 4. Categories ─────────────────────────────────────────────────
        cat_map: dict[str, Category] = {}
        for cat_name, cat_desc in CATEGORIES:
            slug = slugify(cat_name)
            cat, _ = await get_or_create(
                db, Category, {"name": cat_name}, {"slug": slug, "description": cat_desc, "status": "ACTIVE"}
            )
            cat_map[cat_name] = cat
        logger.info(f"✅ {len(cat_map)} Categories ready")

        # ── 5. Brands ────────────────────────────────────────────────────
        brand_map: dict[str, Brand] = {}
        for brand_name in BRANDS:
            slug = slugify(brand_name)
            brand, _ = await get_or_create(
                db, Brand, {"name": brand_name}, {"slug": slug, "status": "ACTIVE"}
            )
            brand_map[brand_name] = brand
        logger.info(f"✅ {len(brand_map)} Brands ready")

        # ── 6. Colors ────────────────────────────────────────────────────
        color_map: dict[str, Color] = {}
        for color_name, hex_code in COLORS:
            c, _ = await get_or_create(
                db, Color, {"name": color_name}, {"hex_code": hex_code, "status": "ACTIVE"}
            )
            color_map[color_name] = c
        logger.info(f"✅ {len(color_map)} Colors ready")

        # ── 7. Sizes ─────────────────────────────────────────────────────
        size_map: dict[str, Size] = {}
        for size_name, size_type, sort_order in SIZES:
            s, _ = await get_or_create(
                db, Size, {"name": size_name}, {"type": size_type, "sort_order": sort_order, "status": "ACTIVE"}
            )
            size_map[size_name] = s
        logger.info(f"✅ {len(size_map)} Sizes ready")

        # ── 8. Supplier ──────────────────────────────────────────────────
        supplier, _ = await get_or_create(
            db,
            Supplier,
            {"code": "SUPP-000001"},
            {
                "name": "Global Apparel Wholesale",
                "phone": "+855 12 888 999",
                "email": "orders@globalapparel.com",
                "contact_person": "Supply Manager",
                "status": "ACTIVE",
            },
        )
        logger.info("✅ Supplier ready")

        # ── 9. Products & Sellable Variants ──────────────────────────────
        total_products_seeded = 0
        total_variants_seeded = 0

        for p_idx, p_data in enumerate(CATALOG_PRODUCTS):
            image_url = f"/uploads/products/{p_data['image_file']}"

            product, _ = await get_or_create(
                db,
                Product,
                {"code": p_data["code"]},
                {
                    "name": p_data["name"],
                    "slug": slugify(p_data["name"]),
                    "description": p_data["description"],
                    "category_id": cat_map[p_data["category"]].id,
                    "brand_id": brand_map[p_data["brand"]].id,
                    "supplier_id": supplier.id,
                    "image_url": image_url,
                    "status": "ACTIVE",
                },
            )
            total_products_seeded += 1

            variant_counter = 0
            stock_plan = p_data.get("stock_plan", {})

            for color_name in p_data["colors"]:
                for size_name in p_data["sizes"]:
                    variant_counter += 1
                    col_code = color_name[:3].upper()
                    sz_code = size_name.replace(" ", "")

                    # Clean predictable SKU, e.g. PCT-BLK-M or SFJ-NVY-30
                    sku = f"{p_data['prefix']}-{col_code}-{sz_code}"

                    # Unique 12-digit barcode: e.g. 890001000101
                    barcode = f"890{p_idx + 1:03d}{variant_counter:04d}01"

                    # Stable deterministic QR ref
                    qr_ref = f"QR-{p_data['prefix']}-{variant_counter:03d}"

                    variant, _ = await get_or_create(
                        db,
                        ProductVariant,
                        {"product_id": product.id, "color_id": color_map[color_name].id, "size_id": size_map[size_name].id},
                        {
                            "sku": sku,
                            "barcode": barcode,
                            "qr_reference": qr_ref,
                            "cost_price": Decimal(str(p_data["cost"])),
                            "selling_price": Decimal(str(p_data["price"])),
                            "image_url": image_url,
                            "status": "ACTIVE",
                        },
                    )
                    total_variants_seeded += 1

                    # Determine stock quantity
                    key = f"{color_name}/{size_name}"
                    if key in stock_plan:
                        qty = stock_plan[key]
                    else:
                        # Realistic distribution: mostly in-stock (20..50), some low-stock (3..7)
                        qty = 35 if variant_counter % 5 != 0 else 5

                    stock_entry, _ = await get_or_create(
                        db,
                        InventoryStock,
                        {"variant_id": variant.id, "warehouse_id": warehouse.id},
                        {"quantity": qty, "reorder_level": 10},
                    )

        await db.flush()
        logger.info(
            f"✅ Seeded {total_products_seeded} Products & {total_variants_seeded} Variants with inventory stocks"
        )

        # ── 10. Customers ─────────────────────────────────────────────────
        customers_data = [
            ("Sophea Chan", "+855 12 111 222", "sophea@example.com"),
            ("Rithy Kim", "+855 12 333 444", "rithy@example.com"),
            ("Bopha Sok", "+855 12 555 666", "bopha@example.com"),
            ("Dara Meas", "+855 12 777 888", "dara@example.com"),
        ]
        for i, (name, phone, email) in enumerate(customers_data):
            code = f"CUST-{i + 1:06d}"
            c, _ = await get_or_create(
                db,
                Customer,
                {"customer_code": code},
                {"name": name, "phone": phone, "email": email, "status": "ACTIVE"},
            )
            await get_or_create(
                db,
                LoyaltyAccount,
                {"customer_id": c.id},
                {
                    "points_balance": 250,
                    "total_points_earned": 250,
                    "total_points_redeemed": 0,
                    "tier": "SILVER" if i == 0 else "BRONZE",
                },
            )

        # ── 11. Expense Categories ─────────────────────────────────────────
        for code, name in EXPENSE_CATEGORIES:
            await get_or_create(db, ExpenseCategory, {"code": code}, {"name": name, "is_system": True})

        await db.commit()
        logger.success("🎉 Seed completed idempotently with 0 errors!")
        logger.info("")
        logger.info("Demo Cashier credentials:")
        logger.info("  cashier / cashier123")
        logger.info(f"Total Products: {total_products_seeded}")
        logger.info(f"Total Variants: {total_variants_seeded}")


if __name__ == "__main__":
    asyncio.run(seed())
