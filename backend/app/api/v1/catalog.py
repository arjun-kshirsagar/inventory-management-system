from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.deps import DB, AdminUser, CurrentUser
from app.models import Brand, Category, Product, ProductVariant, Supplier
from app.schemas.catalog import (
    BrandIn,
    BrandOut,
    CategoryIn,
    CategoryOut,
    ImportResult,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    SupplierIn,
    SupplierOut,
    VariantCreate,
    VariantLookup,
    VariantMatrix,
    VariantOut,
    VariantUpdate,
)
from app.schemas.common import Page
from app.services import catalog as catalog_service
from app.services.documents import render_labels_html, to_pdf
from app.services.store import get_store_settings

router = APIRouter(tags=["catalog"])


def _commit(db, conflict_message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, conflict_message) from None


def _simple_crud(model, schema_in, schema_out, path: str, order_by):
    """Register list/create/update endpoints for a small lookup table."""

    @router.get(f"/{path}", response_model=list[schema_out], name=f"list_{path}")
    def list_items(db: DB, _: CurrentUser):
        return db.scalars(select(model).order_by(order_by)).all()

    @router.post(f"/{path}", response_model=schema_out, status_code=201, name=f"create_{path}")
    def create_item(data: schema_in, db: DB, _: AdminUser):
        obj = model(**data.model_dump())
        db.add(obj)
        _commit(db, "Already exists")
        return obj

    @router.put(f"/{path}/{{item_id}}", response_model=schema_out, name=f"update_{path}")
    def update_item(item_id: int, data: schema_in, db: DB, _: AdminUser):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(404, "Not found")
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        _commit(db, "Already exists")
        return obj


_simple_crud(Category, CategoryIn, CategoryOut, "categories", Category.name)
_simple_crud(Brand, BrandIn, BrandOut, "brands", Brand.name)
_simple_crud(Supplier, SupplierIn, SupplierOut, "suppliers", Supplier.name)


def _product_query():
    return select(Product).options(
        selectinload(Product.variants), selectinload(Product.category), selectinload(Product.brand)
    )


def _get_product(db, product_id: int) -> Product:
    product = db.scalar(_product_query().where(Product.id == product_id))
    if product is None:
        raise HTTPException(404, "Product not found")
    return product


@router.get("/products", response_model=Page[ProductOut])
def list_products(
    db: DB,
    _: CurrentUser,
    q: str | None = None,
    category_id: int | None = None,
    brand_id: int | None = None,
    include_inactive: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(Product)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                Product.id.in_(
                    select(ProductVariant.product_id).where(
                        or_(ProductVariant.sku.ilike(like), ProductVariant.barcode == q)
                    )
                ),
            )
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if not include_inactive:
        stmt = stmt.where(Product.is_active)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    ids = select(stmt.subquery().c.id)
    items = db.scalars(
        _product_query()
        .where(Product.id.in_(ids))
        .order_by(Product.name)
        .offset(offset)
        .limit(limit)
    ).all()
    return Page(items=items, total=total)


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(data: ProductCreate, db: DB, _: AdminUser):
    try:
        product = catalog_service.create_product(db, data)
    except catalog_service.CatalogError as e:
        raise HTTPException(409, str(e)) from None
    return _get_product(db, product.id)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DB, _: CurrentUser):
    return _get_product(db, product_id)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: DB, _: AdminUser):
    product = _get_product(db, product_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    db.commit()
    return _get_product(db, product_id)


@router.post("/products/{product_id}/variants", response_model=list[VariantOut], status_code=201)
def add_variants(
    product_id: int,
    db: DB,
    _: AdminUser,
    variant: VariantCreate | None = None,
    matrix: VariantMatrix | None = None,
):
    product = _get_product(db, product_id)
    to_add = ([variant] if variant else []) + (
        catalog_service.matrix_variants(matrix) if matrix else []
    )
    if not to_add:
        raise HTTPException(400, "Provide a variant or a matrix")
    existing = {(v.size.lower(), v.color.lower()) for v in product.variants}
    to_add = [v for v in to_add if (v.size.lower(), v.color.lower()) not in existing]
    try:
        created = [catalog_service.add_variant(db, product, v) for v in to_add]
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate SKU or barcode") from None
    return created


@router.patch("/variants/{variant_id}", response_model=VariantOut)
def update_variant(variant_id: int, data: VariantUpdate, db: DB, _: AdminUser):
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(404, "Variant not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(variant, k, v)
    if variant.selling_price > variant.mrp:
        db.rollback()
        raise HTTPException(422, "Selling price cannot exceed MRP")
    _commit(db, "Barcode already in use")
    return variant


def _lookup_rows(variants) -> list[VariantLookup]:
    return [
        VariantLookup.model_validate(
            {
                **VariantOut.model_validate(v).model_dump(),
                "product_name": v.product.name,
                "hsn_code": v.product.hsn_code,
            }
        )
        for v in variants
    ]


@router.get("/variants/lookup", response_model=list[VariantLookup])
def lookup_variants(db: DB, _: CurrentUser, q: str = Query(min_length=1), limit: int = 20):
    """POS search: exact barcode/SKU match first, otherwise name/SKU search."""
    base = (
        select(ProductVariant)
        .join(Product)
        .options(selectinload(ProductVariant.product))
        .where(ProductVariant.is_active, Product.is_active)
    )
    exact = db.scalars(
        base.where(or_(ProductVariant.barcode == q, func.upper(ProductVariant.sku) == q.upper()))
    ).all()
    if exact:
        return _lookup_rows(exact)
    like = f"%{q}%"
    rows = db.scalars(
        base.where(or_(Product.name.ilike(like), ProductVariant.sku.ilike(like)))
        .order_by(Product.name, ProductVariant.color, ProductVariant.size)
        .limit(limit)
    ).all()
    return _lookup_rows(rows)


@router.post("/products/import", response_model=ImportResult)
async def import_products(db: DB, _: AdminUser, file: UploadFile = File(...)):
    try:
        return catalog_service.import_csv(db, await file.read())
    except (catalog_service.CatalogError, UnicodeDecodeError) as e:
        raise HTTPException(400, str(e)) from None


@router.get("/products/import/template", response_class=Response)
def import_template(_: CurrentUser):
    header = ",".join(catalog_service.IMPORT_COLUMNS)
    sample = "Slim Fit Oxford Shirt,Shirts,Urban Thread,6205,Men,Cotton,M,Blue,1499,1299,650,5,,"
    return Response(
        f"{header}\n{sample}\n",
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=product_import_template.csv"},
    )


class LabelRequest(BaseModel):
    variant_id: int
    copies: int = Field(default=1, ge=1, le=500)


@router.post("/variants/labels.pdf", response_class=Response)
def barcode_labels(items: list[LabelRequest], db: DB, _: CurrentUser):
    variants = {
        v.id: v
        for v in db.scalars(
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(ProductVariant.id.in_([i.variant_id for i in items]))
        )
    }
    pairs = [(variants[i.variant_id], i.copies) for i in items if i.variant_id in variants]
    if not pairs:
        raise HTTPException(400, "No valid variants")
    pdf = to_pdf(render_labels_html(pairs, get_store_settings(db)))
    return Response(pdf, media_type="application/pdf")
