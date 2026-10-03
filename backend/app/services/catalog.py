import csv
import io
import re
import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Brand, Category, Product, ProductVariant
from app.schemas.catalog import ImportResult, ProductCreate, VariantCreate, VariantMatrix


class CatalogError(Exception):
    pass


def ean13(body12: str) -> str:
    digits = [int(d) for d in body12]
    check = (10 - (sum(digits[0::2]) + 3 * sum(digits[1::2])) % 10) % 10
    return body12 + str(check)


def _code(text: str, length: int) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())[:length] or "X"


def default_sku(product_id: int, size: str, color: str) -> str:
    return f"P{product_id:05d}-{_code(size, 4)}-{_code(color, 3)}"


def add_variant(db: Session, product: Product, data: VariantCreate) -> ProductVariant:
    """Create a variant; SKU and an in-store EAN-13 barcode are generated if not supplied."""
    variant = ProductVariant(
        product=product,
        sku=data.sku or default_sku(product.id, data.size, data.color),
        barcode=data.barcode or f"tmp-{uuid.uuid4().hex}",
        size=data.size,
        color=data.color,
        mrp=data.mrp,
        selling_price=data.selling_price,
        cost_price=data.cost_price,
        reorder_level=data.reorder_level,
        quantity_on_hand=0,
    )
    db.add(variant)
    db.flush()
    if not data.barcode:
        # "200" prefix is the GS1 range reserved for in-store use.
        variant.barcode = ean13(f"200{variant.id:09d}")
    return variant


def matrix_variants(matrix: VariantMatrix) -> list[VariantCreate]:
    return [
        VariantCreate(
            size=size.strip(),
            color=color.strip(),
            mrp=matrix.mrp,
            selling_price=matrix.selling_price,
            cost_price=matrix.cost_price,
            reorder_level=matrix.reorder_level,
        )
        for color in matrix.colors
        for size in matrix.sizes
    ]


def create_product(db: Session, data: ProductCreate) -> Product:
    product = Product(**data.model_dump(exclude={"variants", "matrix"}))
    db.add(product)
    db.flush()
    variants = list(data.variants)
    if data.matrix:
        variants += matrix_variants(data.matrix)
    try:
        for v in variants:
            add_variant(db, product, v)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise CatalogError("Duplicate size/colour, SKU or barcode") from e
    db.refresh(product)
    return product


def get_or_create(db: Session, model, **filters):
    obj = db.scalar(select(model).filter_by(**filters))
    if obj is None:
        obj = model(**filters)
        db.add(obj)
        db.flush()
    return obj


IMPORT_COLUMNS = [
    "product_name",
    "category",
    "brand",
    "hsn_code",
    "gender",
    "material",
    "size",
    "color",
    "mrp",
    "selling_price",
    "cost_price",
    "reorder_level",
    "sku",
    "barcode",
]


def import_csv(db: Session, content: bytes) -> ImportResult:
    """One row per variant. Rows sharing product_name + brand belong to one product.

    Imported variants start with zero stock; receive stock through a GRN.
    The whole file is rejected if any row is invalid.
    """
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    missing = {"product_name", "hsn_code", "size", "color", "mrp"} - set(reader.fieldnames or [])
    if missing:
        raise CatalogError(f"Missing columns: {', '.join(sorted(missing))}")

    errors: list[str] = []
    products: dict[tuple[str, str], Product] = {}
    created_products = created_variants = 0
    for n, row in enumerate(reader, start=2):
        row = {k: (v or "").strip() for k, v in row.items() if k}
        try:
            mrp = Decimal(row["mrp"])
            selling = Decimal(row.get("selling_price") or row["mrp"])
            cost = Decimal(row.get("cost_price") or "0")
            reorder = int(row.get("reorder_level") or 5)
        except (InvalidOperation, ValueError):
            errors.append(f"Row {n}: invalid number")
            continue
        if not re.fullmatch(r"\d{4,8}", row["hsn_code"]):
            errors.append(f"Row {n}: HSN code must be 4-8 digits")
            continue

        key = (row["product_name"].lower(), row.get("brand", "").lower())
        product = products.get(key)
        if product is None:
            category = (
                get_or_create(db, Category, name=row["category"], parent_id=None)
                if row.get("category")
                else None
            )
            brand = get_or_create(db, Brand, name=row["brand"]) if row.get("brand") else None
            product = db.scalar(
                select(Product).where(
                    Product.name == row["product_name"],
                    Product.brand_id == (brand.id if brand else None),
                )
            )
            if product is None:
                product = Product(
                    name=row["product_name"],
                    category=category,
                    brand=brand,
                    hsn_code=row["hsn_code"],
                    gender=row.get("gender") or None,
                    material=row.get("material") or None,
                )
                db.add(product)
                db.flush()
                created_products += 1
            products[key] = product
        try:
            with db.begin_nested():
                add_variant(
                    db,
                    product,
                    VariantCreate(
                        size=row["size"],
                        color=row["color"],
                        mrp=mrp,
                        selling_price=selling,
                        cost_price=cost,
                        reorder_level=reorder,
                        sku=row.get("sku") or None,
                        barcode=row.get("barcode") or None,
                    ),
                )
            created_variants += 1
        except IntegrityError:
            errors.append(f"Row {n}: duplicate variant, SKU or barcode")
        except ValueError as e:
            errors.append(f"Row {n}: {e}")

    if errors:
        db.rollback()
        return ImportResult(products_created=0, variants_created=0, errors=errors)
    db.commit()
    return ImportResult(
        products_created=created_products, variants_created=created_variants, errors=[]
    )
