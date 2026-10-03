"""The only place that changes ProductVariant.quantity_on_hand.

Every change is written to the stock_movements ledger in the same transaction, and
variant rows are locked (SELECT ... FOR UPDATE) so concurrent sales of the last unit
can't both succeed.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProductVariant, StockMovement
from app.models.enums import MovementType


class StockError(Exception):
    pass


def lock_variants(db: Session, variant_ids: Iterable[int]) -> dict[int, ProductVariant]:
    ids = sorted(set(variant_ids))  # consistent lock order avoids deadlocks
    rows = db.scalars(
        select(ProductVariant)
        .where(ProductVariant.id.in_(ids))
        .order_by(ProductVariant.id)
        .with_for_update()
    ).all()
    found = {v.id: v for v in rows}
    missing = set(ids) - found.keys()
    if missing:
        raise StockError(f"Unknown variant id(s): {sorted(missing)}")
    return found


def move_stock(
    db: Session,
    variant: ProductVariant,
    qty_delta: int,
    movement_type: MovementType,
    user_id: int | None,
    ref_type: str | None = None,
    ref_id: int | None = None,
    reason: str | None = None,
) -> StockMovement:
    """Apply a stock change to an already-locked variant."""
    if qty_delta == 0:
        raise StockError("Quantity change cannot be zero")
    new_qty = variant.quantity_on_hand + qty_delta
    if new_qty < 0:
        raise StockError(
            f"Insufficient stock for {variant.sku}: "
            f"{variant.quantity_on_hand} available, {-qty_delta} requested"
        )
    variant.quantity_on_hand = new_qty
    movement = StockMovement(
        variant_id=variant.id,
        qty_delta=qty_delta,
        type=movement_type,
        ref_type=ref_type,
        ref_id=ref_id,
        reason=reason,
        user_id=user_id,
    )
    db.add(movement)
    return movement
