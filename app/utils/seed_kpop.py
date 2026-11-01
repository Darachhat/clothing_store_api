"""Seed Blackpink and BTS merchandise assets, products, variants, and stocks."""
import asyncio
from decimal import Decimal
from slugify import slugify
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Warehouse
from app.models import Brand, Category, Color, Product, ProductVariant, Size, Supplier
from app.models import InventoryStock
from app.utils.generators import generate_qr_reference, generate_sku


async def main():
    async with AsyncSessionLocal() as db:
        # Check warehouse
        wh_res = await db.execute(select(Warehouse).where(Warehouse.status == "ACTIVE"))
        wh = wh_res.scalars().first()
        if not wh:
            print("No active warehouse found!")
            return

        # Check supplier
        supp_res = await db.execute(select(Supplier).limit(1))
        supplier = supp_res.scalars().first()
        if not supplier:
            supplier = Supplier(
                code="SUPP-000001",
                name="K-Merch Global Wholesale",
                status="ACTIVE",
            )
            db.add(supplier)
            await db.flush()

        # ── Categories ──
        categories = ["T-Shirts", "Hoodies", "Jeans", "Jackets", "Accessories"]
        cat_map = {}
        for cname in categories:
            res = await db.execute(select(Category).where(Category.name == cname))
            cat = res.scalars().first()
            if not cat:
                cat = Category(name=cname, slug=slugify(cname), status="ACTIVE")
                db.add(cat)
                await db.flush()
            cat_map[cname] = cat

        # ── Colors ──
        colors_data = [
            ("Black", "#111111"),
            ("White", "#FFFFFF"),
            ("Hot Pink", "#FF2D78"),
            ("Deep Purple", "#5E2D91"),
            ("Gold", "#D4AF37"),
            ("Navy", "#0B1B3D"),
        ]
        color_map = {}
        for cname, chex in colors_data:
            res = await db.execute(select(Color).where(Color.name == cname))
            c = res.scalars().first()
            if not c:
                c = Color(name=cname, hex_code=chex, status="ACTIVE")
                db.add(c)
                await db.flush()
            color_map[cname] = c

        # ── Sizes ──
        sizes_data = ["XS", "S", "M", "L", "XL", "XXL"]
        size_map = {}
        for i, sname in enumerate(sizes_data):
            res = await db.execute(select(Size).where(Size.name == sname))
            s = res.scalars().first()
            if not s:
                s = Size(name=sname, type="LETTER", sort_order=i, status="ACTIVE")
                db.add(s)
                await db.flush()
            size_map[sname] = s

        # ── Brands ──
        brands_data = [
            ("BLACKPINK", "blackpink", "/uploads/brands/blackpink-logo.jpg", "Official BLACKPINK YG Entertainment Merchandise Collection"),
            ("BTS", "bts", "/uploads/brands/bts-logo.jpg", "Official BTS BigHit Music Streetwear & Tour Collection"),
        ]
        brand_map = {}
        for bname, bslug, blogo, bdesc in brands_data:
            res = await db.execute(select(Brand).where(Brand.name == bname))
            b = res.scalars().first()
            if not b:
                b = Brand(name=bname, slug=bslug, logo_url=blogo, description=bdesc, status="ACTIVE")
                db.add(b)
                await db.flush()
            else:
                b.logo_url = blogo
                b.description = bdesc
            brand_map[bname] = b

        # ── Products & Variants ──
        products_to_seed = [
            {
                "code": "PROD-BP001",
                "name": "BLACKPINK World Tour Signature Tee",
                "category": "T-Shirts",
                "brand": "BLACKPINK",
                "image_url": "/uploads/products/blackpink-tshirt.jpg",
                "description": "Premium 240gsm heavyweight combed cotton tee with hot pink diamond typography print on chest.",
                "variants": [
                    {"color": "Black", "size": "S", "cost": 10.00, "price": 28.00, "barcode": "880963456001", "stock": 45},
                    {"color": "Black", "size": "M", "cost": 10.00, "price": 28.00, "barcode": "880963456002", "stock": 60},
                    {"color": "Black", "size": "L", "cost": 10.00, "price": 28.00, "barcode": "880963456003", "stock": 50},
                    {"color": "Black", "size": "XL", "cost": 10.00, "price": 28.00, "barcode": "880963456004", "stock": 35},
                    {"color": "Hot Pink", "size": "S", "cost": 11.00, "price": 30.00, "barcode": "880963456005", "stock": 25},
                    {"color": "Hot Pink", "size": "M", "cost": 11.00, "price": 30.00, "barcode": "880963456006", "stock": 40},
                    {"color": "Hot Pink", "size": "L", "cost": 11.00, "price": 30.00, "barcode": "880963456007", "stock": 30},
                ],
            },
            {
                "code": "PROD-BP002",
                "name": "BLACKPINK 'Born Pink' Oversized Hoodie",
                "category": "Hoodies",
                "brand": "BLACKPINK",
                "image_url": "/uploads/products/blackpink-hoodie.jpg",
                "description": "Luxury fleece-lined relaxed fit hoodie with embroidered Blackpink crest and ribbed trims.",
                "variants": [
                    {"color": "Hot Pink", "size": "S", "cost": 22.00, "price": 58.00, "barcode": "880963456011", "stock": 30},
                    {"color": "Hot Pink", "size": "M", "cost": 22.00, "price": 58.00, "barcode": "880963456012", "stock": 50},
                    {"color": "Hot Pink", "size": "L", "cost": 22.00, "price": 58.00, "barcode": "880963456013", "stock": 40},
                    {"color": "Hot Pink", "size": "XL", "cost": 22.00, "price": 58.00, "barcode": "880963456014", "stock": 20},
                    {"color": "Black", "size": "M", "cost": 22.00, "price": 58.00, "barcode": "880963456015", "stock": 45},
                    {"color": "Black", "size": "L", "cost": 22.00, "price": 58.00, "barcode": "880963456016", "stock": 35},
                ],
            },
            {
                "code": "PROD-BTS001",
                "name": "BTS 'Yet To Come' Graphic T-Shirt",
                "category": "T-Shirts",
                "brand": "BTS",
                "image_url": "/uploads/products/bts-tshirt.jpg",
                "description": "Clean white streetwear cotton t-shirt with gold and purple BTS bullet-proof logo embroidery.",
                "variants": [
                    {"color": "White", "size": "S", "cost": 11.00, "price": 30.00, "barcode": "880963456021", "stock": 50},
                    {"color": "White", "size": "M", "cost": 11.00, "price": 30.00, "barcode": "880963456022", "stock": 65},
                    {"color": "White", "size": "L", "cost": 11.00, "price": 30.00, "barcode": "880963456023", "stock": 55},
                    {"color": "White", "size": "XL", "cost": 11.00, "price": 30.00, "barcode": "880963456024", "stock": 40},
                    {"color": "Deep Purple", "size": "M", "cost": 12.00, "price": 32.00, "barcode": "880963456025", "stock": 45},
                    {"color": "Deep Purple", "size": "L", "cost": 12.00, "price": 32.00, "barcode": "880963456026", "stock": 35},
                ],
            },
            {
                "code": "PROD-BTS002",
                "name": "BTS 'Proof' Heavyweight Purple Hoodie",
                "category": "Hoodies",
                "brand": "BTS",
                "image_url": "/uploads/products/bts-hoodie.jpg",
                "description": "Signature deep purple 420gsm French terry cotton hoodie with BTS gold metallic shield embroidery.",
                "variants": [
                    {"color": "Deep Purple", "size": "S", "cost": 25.00, "price": 65.00, "barcode": "880963456031", "stock": 35},
                    {"color": "Deep Purple", "size": "M", "cost": 25.00, "price": 65.00, "barcode": "880963456032", "stock": 55},
                    {"color": "Deep Purple", "size": "L", "cost": 25.00, "price": 65.00, "barcode": "880963456033", "stock": 45},
                    {"color": "Deep Purple", "size": "XL", "cost": 25.00, "price": 65.00, "barcode": "880963456034", "stock": 30},
                    {"color": "Black", "size": "M", "cost": 25.00, "price": 65.00, "barcode": "880963456035", "stock": 40},
                    {"color": "Black", "size": "L", "cost": 25.00, "price": 65.00, "barcode": "880963456036", "stock": 30},
                ],
            },
        ]

        total_vars = 0
        for p_data in products_to_seed:
            res = await db.execute(select(Product).where(Product.code == p_data["code"]))
            product = res.scalars().first()
            if not product:
                product = Product(
                    code=p_data["code"],
                    name=p_data["name"],
                    slug=slugify(p_data["name"]),
                    category_id=cat_map[p_data["category"]].id,
                    brand_id=brand_map[p_data["brand"]].id,
                    supplier_id=supplier.id,
                    description=p_data["description"],
                    image_url=p_data["image_url"],
                    status="ACTIVE",
                )
                db.add(product)
                await db.flush()
            else:
                product.image_url = p_data["image_url"]
                product.description = p_data["description"]
                await db.flush()

            v_count = 0
            for v_info in p_data["variants"]:
                v_count += 1
                c_id = color_map[v_info["color"]].id
                s_id = size_map[v_info["size"]].id
                
                # Check existing variant
                var_res = await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.product_id == product.id,
                        ProductVariant.color_id == c_id,
                        ProductVariant.size_id == s_id,
                    )
                )
                variant = var_res.scalars().first()
                if not variant:
                    qr_ref = await generate_qr_reference(db)
                    sku = generate_sku(product.code, v_info["color"], v_info["size"], v_count)
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=sku,
                        barcode=v_info["barcode"],
                        qr_reference=qr_ref,
                        color_id=c_id,
                        size_id=s_id,
                        cost_price=Decimal(str(v_info["cost"])),
                        selling_price=Decimal(str(v_info["price"])),
                        image_url=p_data["image_url"],
                        status="ACTIVE",
                    )
                    db.add(variant)
                    await db.flush()
                else:
                    variant.image_url = p_data["image_url"]
                    variant.barcode = v_info["barcode"]
                    variant.selling_price = Decimal(str(v_info["price"]))
                    variant.cost_price = Decimal(str(v_info["cost"]))
                    await db.flush()

                # Add stock
                stk_res = await db.execute(
                    select(InventoryStock).where(
                        InventoryStock.variant_id == variant.id,
                        InventoryStock.warehouse_id == wh.id,
                    )
                )
                stock = stk_res.scalars().first()
                if not stock:
                    stock = InventoryStock(
                        variant_id=variant.id,
                        warehouse_id=wh.id,
                        quantity=v_info["stock"],
                        reorder_level=10,
                    )
                    db.add(stock)
                else:
                    stock.quantity = v_info["stock"]
                total_vars += 1

        # Also add sample promotions for testing discount codes
        from app.models import Promotion
        from datetime import datetime, timezone, timedelta
        
        promos = [
            {
                "code": "BLACKPINK10",
                "name": "10% Blackpink Special Promo",
                "type": "PERCENTAGE",
                "value": Decimal("10.00"),
                "min_purchase_amount": Decimal("20.00"),
            },
            {
                "code": "ARMY5",
                "name": "$5 Off BTS Army Member Discount",
                "type": "FIXED",
                "value": Decimal("5.00"),
                "min_purchase_amount": Decimal("30.00"),
            },
            {
                "code": "WELCOME15",
                "name": "15% Welcome Store Discount",
                "type": "PERCENTAGE",
                "value": Decimal("15.00"),
                "min_purchase_amount": Decimal("25.00"),
            },
        ]
        for p in promos:
            res = await db.execute(select(Promotion).where(Promotion.code == p["code"]))
            promo = res.scalars().first()
            if not promo:
                promo = Promotion(
                    name=p["name"],
                    code=p["code"],
                    type=p["type"],
                    value=p["value"],
                    min_purchase_amount=p["min_purchase_amount"],
                    start_datetime=datetime.now(timezone.utc) - timedelta(days=1),
                    end_datetime=datetime.now(timezone.utc) + timedelta(days=365),
                    status="ACTIVE",
                    applies_to="ALL",
                )
                db.add(promo)

        await db.commit()
        print(f"Successfully seeded {len(products_to_seed)} K-Pop products with {total_vars} variants & inventory stocks!")


if __name__ == "__main__":
    asyncio.run(main())
