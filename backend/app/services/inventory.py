from sqlalchemy.orm import Session

from app.models import StockReceipt, StockReceiptItem, Supplier
from app.models.enums import MovementType
from app.schemas.inventory import AdjustmentIn, ReceiptCreate
from app.services.stock import StockError, lock_variants, move_stock


def receive_stock(db: Session, data: ReceiptCreate, user_id: int) -> StockReceipt:
    try:
        if data.supplier_id and db.get(Supplier, data.supplier_id) is None:
            raise StockError("Supplier not found")
        variants = lock_variants(db, [i.variant_id for i in data.items])
        receipt = StockReceipt(
            supplier_id=data.supplier_id,
            invoice_ref=data.invoice_ref,
            notes=data.notes,
            created_by=user_id,
        )
        for line in data.items:
            variant = variants[line.variant_id]
            unit_cost = line.unit_cost if line.unit_cost is not None else variant.cost_price
            receipt.items.append(
                StockReceiptItem(variant_id=variant.id, qty=line.qty, unit_cost=unit_cost)
            )
            if data.update_cost_price and line.unit_cost is not None:
                variant.cost_price = line.unit_cost
        db.add(receipt)
        db.flush()
        for line in data.items:
            move_stock(
                db,
                variants[line.variant_id],
                line.qty,
                MovementType.PURCHASE,
                user_id,
                ref_type="stock_receipt",
                ref_id=receipt.id,
            )
        db.commit()
    except StockError:
        db.rollback()
        raise
    db.refresh(receipt)
    return receipt


def adjust_stock(db: Session, data: AdjustmentIn, user_id: int):
    try:
        variant = lock_variants(db, [data.variant_id])[data.variant_id]
        movement = move_stock(
            db, variant, data.qty_delta, MovementType.ADJUSTMENT, user_id, reason=data.reason
        )
        db.commit()
    except StockError:
        db.rollback()
        raise
    return movement
