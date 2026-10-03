from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.deps import DB, AdminUser, CurrentUser
from app.models import (
    Brand,
    Category,
    Product,
    ProductVariant,
    StockMovement,
    StockReceipt,
    StockReceiptItem,
)
from app.models.enums import MovementType
from app.schemas.common import Page
from app.schemas.inventory import (
    AdjustmentIn,
    MovementOut,
    ReceiptCreate,
    ReceiptItemOut,
    ReceiptOut,
    StockLevel,
)
from app.services import inventory as inventory_service
from app.services.money import ZERO

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _receipt_out(r: StockReceipt) -> ReceiptOut:
    items = [
        ReceiptItemOut(
            id=i.id,
            variant_id=i.variant_id,
            qty=i.qty,
            unit_cost=i.unit_cost,
            sku=i.variant.sku,
            product_name=i.variant.product.name,
            size=i.variant.size,
            color=i.variant.color,
        )
        for i in r.items
    ]
    return ReceiptOut(
        id=r.id,
        supplier_id=r.supplier_id,
        supplier_name=r.supplier.name if r.supplier else None,
        invoice_ref=r.invoice_ref,
        notes=r.notes,
        received_at=r.received_at,
        created_by_name=r.creator.name,
        total_qty=sum(i.qty for i in r.items),
        total_cost=sum((i.qty * i.unit_cost for i in r.items), ZERO),
        items=items,
    )


def _movement_out(m: StockMovement) -> MovementOut:
    return MovementOut(
        id=m.id,
        variant_id=m.variant_id,
        sku=m.variant.sku,
        product_name=m.variant.product.name,
        qty_delta=m.qty_delta,
        type=m.type,
        ref_type=m.ref_type,
        ref_id=m.ref_id,
        reason=m.reason,
        user_name=m.user.name if m.user else None,
        created_at=m.created_at,
    )


@router.get("/stock", response_model=Page[StockLevel])
def stock_levels(
    db: DB,
    _: CurrentUser,
    q: str | None = None,
    category_id: int | None = None,
    brand_id: int | None = None,
    size: str | None = None,
    color: str | None = None,
    low_stock_only: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = (
        select(ProductVariant, Product, Category.name, Brand.name)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .outerjoin(Brand, Product.brand_id == Brand.id)
        .where(ProductVariant.is_active, Product.is_active)
    )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(like),
                ProductVariant.sku.ilike(like),
                ProductVariant.barcode == q,
            )
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if size:
        stmt = stmt.where(func.lower(ProductVariant.size) == size.lower())
    if color:
        stmt = stmt.where(func.lower(ProductVariant.color) == color.lower())
    if low_stock_only:
        stmt = stmt.where(ProductVariant.quantity_on_hand <= ProductVariant.reorder_level)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(
        stmt.order_by(Product.name, ProductVariant.color, ProductVariant.size)
        .offset(offset)
        .limit(limit)
    ).all()
    items = [
        StockLevel(
            variant_id=v.id,
            product_id=p.id,
            product_name=p.name,
            category=cat,
            brand=brand,
            sku=v.sku,
            barcode=v.barcode,
            size=v.size,
            color=v.color,
            quantity_on_hand=v.quantity_on_hand,
            reorder_level=v.reorder_level,
            cost_price=v.cost_price,
            selling_price=v.selling_price,
            low_stock=v.quantity_on_hand <= v.reorder_level,
        )
        for v, p, cat, brand in rows
    ]
    return Page(items=items, total=total)


def _load_receipt(db, receipt_id: int) -> StockReceipt:
    receipt = db.scalar(
        select(StockReceipt)
        .options(
            selectinload(StockReceipt.items)
            .selectinload(StockReceiptItem.variant)
            .selectinload(ProductVariant.product),
            selectinload(StockReceipt.supplier),
            selectinload(StockReceipt.creator),
        )
        .where(StockReceipt.id == receipt_id)
    )
    if receipt is None:
        raise HTTPException(404, "Receipt not found")
    return receipt


@router.post("/receipts", response_model=ReceiptOut, status_code=201)
def create_receipt(data: ReceiptCreate, db: DB, user: CurrentUser):
    try:
        receipt = inventory_service.receive_stock(db, data, user.id)
    except inventory_service.StockError as e:
        raise HTTPException(400, str(e)) from None
    return _receipt_out(_load_receipt(db, receipt.id))


@router.get("/receipts", response_model=Page[ReceiptOut])
def list_receipts(
    db: DB, _: CurrentUser, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)
):
    total = db.scalar(select(func.count(StockReceipt.id)))
    ids = db.scalars(
        select(StockReceipt.id).order_by(StockReceipt.id.desc()).offset(offset).limit(limit)
    ).all()
    return Page(items=[_receipt_out(_load_receipt(db, i)) for i in ids], total=total)


@router.get("/receipts/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: DB, _: CurrentUser):
    return _receipt_out(_load_receipt(db, receipt_id))


@router.post("/adjustments", response_model=MovementOut, status_code=201)
def create_adjustment(data: AdjustmentIn, db: DB, admin: AdminUser):
    try:
        movement = inventory_service.adjust_stock(db, data, admin.id)
    except inventory_service.StockError as e:
        raise HTTPException(400, str(e)) from None
    db.refresh(movement)
    return _movement_out(movement)


@router.get("/movements", response_model=Page[MovementOut])
def list_movements(
    db: DB,
    _: CurrentUser,
    variant_id: int | None = None,
    type: MovementType | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(StockMovement)
    if variant_id:
        stmt = stmt.where(StockMovement.variant_id == variant_id)
    if type:
        stmt = stmt.where(StockMovement.type == type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.options(
            selectinload(StockMovement.variant).selectinload(ProductVariant.product),
            selectinload(StockMovement.user),
        )
        .order_by(StockMovement.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return Page(items=[_movement_out(m) for m in rows], total=total)
