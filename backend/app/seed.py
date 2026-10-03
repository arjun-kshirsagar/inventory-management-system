"""Seed the database.

python -m app.seed          # admin user, store settings, GST slabs
python -m app.seed --demo   # ...plus catalog, stock and 30 days of sales
"""

import random
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Brand, Category, Customer, Sale, StockMovement, Supplier, TaxSlab, User
from app.models.enums import PaymentMethod, Role
from app.schemas.catalog import ProductCreate, VariantMatrix
from app.schemas.inventory import ReceiptCreate, ReceiptItemIn
from app.schemas.sales import PaymentIn, SaleCreate, SaleItemIn
from app.services import catalog, inventory, sales
from app.services.store import get_store_settings

GST_RATE_CHANGE = date(2025, 9, 22)

TAX_SLABS = [
    # Apparel (knitted: ch. 61, woven: ch. 62): 5% up to Rs 2,500 per piece, 18% above.
    ("Apparel - knitted", "61", Decimal("2500"), Decimal("5"), Decimal("18")),
    ("Apparel - woven", "62", Decimal("2500"), Decimal("5"), Decimal("18")),
    ("Footwear", "64", Decimal("2500"), Decimal("5"), Decimal("18")),
    ("Silk fabric / sarees", "5007", None, Decimal("5"), Decimal("5")),
    ("Default (accessories etc.)", "", None, Decimal("18"), Decimal("18")),
]


def seed_base(db) -> User:
    settings = get_settings()
    admin = db.scalar(select(User).where(User.email == settings.first_admin_email))
    if admin is None:
        admin = User(
            email=settings.first_admin_email,
            name="Store Admin",
            role=Role.ADMIN,
            password_hash=hash_password(settings.first_admin_password),
        )
        db.add(admin)
        print(f"Created admin {settings.first_admin_email} / {settings.first_admin_password}")

    store = get_store_settings(db)
    if not store.address:
        store.name = "Threads & Co."
        store.address = "12 Linking Road, Bandra West, Mumbai 400050"
        store.phone = "+91 22 5555 0101"
        store.gstin = "27ABCDE1234F1Z5"
        store.state_code = "27"
        store.state_name = "Maharashtra"
        store.footer_terms = (
            "Prices are inclusive of GST. Exchange within 15 days with tags and invoice. "
            "No refund on discounted items."
        )

    if not db.scalar(select(TaxSlab).limit(1)):
        for name, prefix, threshold, below, above in TAX_SLABS:
            db.add(
                TaxSlab(
                    name=name,
                    hsn_prefix=prefix,
                    price_threshold=threshold,
                    rate_below=below,
                    rate_above=above,
                    effective_from=GST_RATE_CHANGE,
                )
            )
    db.commit()
    return admin


DEMO_PRODUCTS = [
    # name, category, brand, hsn, gender, material, sizes, colors, mrp, price, cost
    (
        "Slim Fit Oxford Shirt",
        "Shirts",
        "Urban Thread",
        "6205",
        "Men",
        "Cotton",
        ["S", "M", "L", "XL"],
        ["White", "Blue"],
        1499,
        1299,
        620,
    ),
    (
        "Linen Kurta",
        "Ethnic",
        "Desi Loom",
        "6211",
        "Men",
        "Linen",
        ["M", "L", "XL"],
        ["Beige", "Olive"],
        2299,
        1999,
        900,
    ),
    (
        "Crew Neck T-Shirt",
        "T-Shirts",
        "Basics Co",
        "6109",
        "Unisex",
        "Cotton",
        ["S", "M", "L", "XL"],
        ["Black", "White", "Grey"],
        699,
        599,
        220,
    ),
    (
        "Stretch Denim Jeans",
        "Jeans",
        "Indigo Works",
        "6203",
        "Men",
        "Denim",
        ["30", "32", "34", "36"],
        ["Indigo", "Black"],
        2499,
        2199,
        1050,
    ),
    (
        "Floral Maxi Dress",
        "Dresses",
        "Bloom",
        "6204",
        "Women",
        "Rayon",
        ["XS", "S", "M", "L"],
        ["Pink", "Navy"],
        2999,
        2799,
        1300,
    ),
    (
        "Wool Blend Blazer",
        "Outerwear",
        "Urban Thread",
        "6203",
        "Men",
        "Wool blend",
        ["38", "40", "42"],
        ["Charcoal"],
        6999,
        6499,
        3200,
    ),
    (
        "Silk Saree",
        "Ethnic",
        "Desi Loom",
        "5007",
        "Women",
        "Silk",
        ["Free"],
        ["Maroon", "Teal"],
        8999,
        8499,
        4800,
    ),
]


def seed_demo(db, admin: User) -> None:
    if db.scalar(select(Sale).limit(1)):
        print("Demo data already present; skipping")
        return
    cashier = db.scalar(select(User).where(User.email == "cashier@store.local"))
    if cashier is None:
        cashier = User(
            email="cashier@store.local",
            name="Priya (Cashier)",
            role=Role.CASHIER,
            password_hash=hash_password("cashier123"),
        )
        db.add(cashier)
        db.commit()
        print("Created cashier cashier@store.local / cashier123")

    variants = []
    for name, cat, brand, hsn, gender, material, sizes, colors, mrp, price, cost in DEMO_PRODUCTS:
        product = catalog.create_product(
            db,
            ProductCreate(
                name=name,
                hsn_code=hsn,
                gender=gender,
                material=material,
                category_id=catalog.get_or_create(db, Category, name=cat, parent_id=None).id,
                brand_id=catalog.get_or_create(db, Brand, name=brand).id,
                matrix=VariantMatrix(
                    sizes=sizes,
                    colors=colors,
                    mrp=mrp,
                    selling_price=price,
                    cost_price=cost,
                    reorder_level=3,
                ),
            ),
        )
        variants.extend(product.variants)

    rng = random.Random(42)
    supplier = catalog.get_or_create(db, Supplier, name="Tirupur Textiles Pvt Ltd")
    supplier.gstin = "33AAACT1234B1Z2"
    db.commit()
    inventory.receive_stock(
        db,
        ReceiptCreate(
            supplier_id=supplier.id,
            invoice_ref="TT/2026/0457",
            items=[ReceiptItemIn(variant_id=v.id, qty=rng.randint(6, 20)) for v in variants],
        ),
        admin.id,
    )

    customers = [
        Customer(name="Rahul Mehta", phone="9820012345", state_code="27"),
        Customer(
            name="Ananya Iyer",
            phone="9840054321",
            state_code="33",
            gstin="33ABCDE9876K1Z3",
            address="T. Nagar, Chennai",
        ),
        Customer(name="Sneha Kulkarni", phone="9890011122", state_code="27"),
    ]
    db.add_all(customers)
    db.commit()

    now = datetime.now(UTC)
    for days_ago in range(29, -1, -1):
        for _ in range(rng.randint(1, 5)):
            in_stock = [v for v in variants if v.quantity_on_hand > 2]
            if not in_stock:
                break
            lines = [
                SaleItemIn(variant_id=v.id, qty=rng.choice([1, 1, 1, 2]))
                for v in rng.sample(in_stock, k=min(len(in_stock), rng.randint(1, 3)))
            ]
            customer = rng.choice([None, None, *customers])
            discount = Decimal(rng.choice([0, 0, 0, 100, 200]))
            quote = sales.quote_sale(db, lines, customer.id if customer else None, discount)
            db.rollback()
            sale = sales.create_sale(
                db,
                SaleCreate(
                    items=lines,
                    customer_id=customer.id if customer else None,
                    bill_discount=discount,
                    payments=[
                        PaymentIn(method=rng.choice(list(PaymentMethod)), amount=quote.grand_total)
                    ],
                ),
                rng.choice([admin.id, cashier.id]),
            )
            when = now - timedelta(days=days_ago, hours=rng.randint(0, 8))
            sale.created_at = when
            for m in db.scalars(
                select(StockMovement).where(
                    StockMovement.ref_type == "sale", StockMovement.ref_id == sale.id
                )
            ):
                m.created_at = when
            db.commit()
            for v in variants:
                db.refresh(v)
    print(f"Seeded {len(variants)} variants and {db.query(Sale).count()} demo sales")


def main() -> None:
    with SessionLocal() as db:
        admin = seed_base(db)
        if "--demo" in sys.argv:
            seed_demo(db, admin)


if __name__ == "__main__":
    main()
