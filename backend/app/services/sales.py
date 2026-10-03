"""Pricing, checkout and returns."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    Payment,
    ProductVariant,
    Sale,
    SaleItem,
    SaleReturn,
    SaleReturnItem,
)
from app.models.enums import MovementType, SaleStatus
from app.schemas.sales import ReturnCreate, SaleCreate, SaleItemIn
from app.services import gst
from app.services.money import ZERO, q, round_rupee
from app.services.numbering import next_document_number
from app.services.stock import StockError, lock_variants, move_stock
from app.services.store import get_store_settings


class SaleError(Exception):
    pass


@dataclass
class PricedCart:
    items: list[SaleItem]
    subtotal: Decimal
    discount: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    round_off: Decimal
    grand_total: Decimal
    place_of_supply: str


def price_cart(
    db: Session,
    lines: list[SaleItemIn],
    variants: dict[int, ProductVariant],
    customer: Customer | None,
    bill_discount: Decimal,
    on: date,
) -> PricedCart:
    store = get_store_settings(db)
    place_of_supply = (customer.state_code if customer and customer.state_code else None) or (
        store.state_code
    )
    interstate = place_of_supply != store.state_code
    slabs = gst.load_slabs(db)

    gross = []
    for line in lines:
        variant = variants[line.variant_id]
        if not variant.is_active or not variant.product.is_active:
            raise SaleError(f"{variant.sku} is not available for sale")
        line_gross = q(variant.selling_price * line.qty)
        if line.discount > line_gross:
            raise SaleError(f"Discount on {variant.sku} exceeds the line amount")
        gross.append(line_gross)

    after_line_discount = [g - q(line.discount) for g, line in zip(gross, lines, strict=True)]
    if bill_discount > sum(after_line_discount, ZERO):
        raise SaleError("Bill discount exceeds the bill amount")
    bill_shares = gst.allocate(q(bill_discount), after_line_discount)

    items: list[SaleItem] = []
    for line, line_gross, net_before_bill, bill_share in zip(
        lines, gross, after_line_discount, bill_shares, strict=True
    ):
        variant = variants[line.variant_id]
        net_inclusive = net_before_bill - bill_share
        slab = gst.find_slab(slabs, variant.product.hsn_code, on)
        tax = gst.compute_line_tax(net_inclusive, line.qty, slab, interstate)
        items.append(
            SaleItem(
                variant_id=variant.id,
                product_name=variant.product.name,
                sku=variant.sku,
                size=variant.size,
                color=variant.color,
                hsn_code=variant.product.hsn_code,
                qty=line.qty,
                returned_qty=0,
                unit_price=variant.selling_price,
                unit_cost=variant.cost_price,
                discount=line_gross - net_inclusive,
                taxable_value=tax.taxable_value,
                gst_rate=tax.rate,
                cgst=tax.cgst,
                sgst=tax.sgst,
                igst=tax.igst,
                line_total=net_inclusive,
            )
        )

    total = sum((i.line_total for i in items), ZERO)
    grand_total = round_rupee(total)
    return PricedCart(
        items=items,
        subtotal=sum(gross, ZERO),
        discount=sum((i.discount for i in items), ZERO),
        taxable_value=sum((i.taxable_value for i in items), ZERO),
        cgst=sum((i.cgst for i in items), ZERO),
        sgst=sum((i.sgst for i in items), ZERO),
        igst=sum((i.igst for i in items), ZERO),
        round_off=grand_total - total,
        grand_total=grand_total,
        place_of_supply=place_of_supply,
    )


def _merge_lines(lines: list[SaleItemIn]) -> list[SaleItemIn]:
    """Combine repeated scans of the same variant into one line."""
    merged: dict[int, SaleItemIn] = {}
    for line in lines:
        if line.variant_id in merged:
            existing = merged[line.variant_id]
            existing.qty += line.qty
            existing.discount += line.discount
        else:
            merged[line.variant_id] = line.model_copy()
    return list(merged.values())


def _get_customer(db: Session, customer_id: int | None) -> Customer | None:
    if customer_id is None:
        return None
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise SaleError("Customer not found")
    return customer


def quote_sale(
    db: Session, lines: list[SaleItemIn], customer_id: int | None, bill_discount: Decimal
) -> PricedCart:
    lines = _merge_lines(lines)
    variants = {
        v.id: v
        for v in db.scalars(
            select(ProductVariant).where(ProductVariant.id.in_([ln.variant_id for ln in lines]))
        )
    }
    missing = {ln.variant_id for ln in lines} - variants.keys()
    if missing:
        raise SaleError(f"Unknown variant id(s): {sorted(missing)}")
    return price_cart(
        db, lines, variants, _get_customer(db, customer_id), bill_discount, date.today()
    )


def create_sale(db: Session, data: SaleCreate, cashier_id: int) -> Sale:
    """Checkout in a single transaction. Commits on success; rolls back on any error."""
    if data.idempotency_key:
        existing = db.scalar(select(Sale).where(Sale.idempotency_key == data.idempotency_key))
        if existing:
            return existing

    try:
        lines = _merge_lines(data.items)
        customer = _get_customer(db, data.customer_id)
        variants = lock_variants(db, [ln.variant_id for ln in lines])
        cart = price_cart(db, lines, variants, customer, data.bill_discount, date.today())

        paid = sum((q(p.amount) for p in data.payments), ZERO)
        if paid != cart.grand_total:
            raise SaleError(f"Payments total {paid} but the bill is {cart.grand_total}")

        store = get_store_settings(db)
        sale = Sale(
            invoice_no=next_document_number(db, "invoice", store.invoice_prefix, date.today()),
            idempotency_key=data.idempotency_key,
            customer_id=customer.id if customer else None,
            cashier_id=cashier_id,
            place_of_supply=cart.place_of_supply,
            subtotal=cart.subtotal,
            discount=cart.discount,
            taxable_value=cart.taxable_value,
            cgst=cart.cgst,
            sgst=cart.sgst,
            igst=cart.igst,
            round_off=cart.round_off,
            grand_total=cart.grand_total,
            status=SaleStatus.COMPLETED,
            notes=data.notes,
            items=cart.items,
            payments=[
                Payment(method=p.method, amount=q(p.amount), reference=p.reference)
                for p in data.payments
            ],
        )
        db.add(sale)
        db.flush()

        for item in cart.items:
            move_stock(
                db,
                variants[item.variant_id],
                -item.qty,
                MovementType.SALE,
                cashier_id,
                ref_type="sale",
                ref_id=sale.id,
            )
        db.commit()
    except (SaleError, StockError, gst.TaxConfigError):
        db.rollback()
        raise
    except IntegrityError:
        # Lost a race on the same idempotency key: return the sale that won.
        db.rollback()
        if data.idempotency_key:
            existing = db.scalar(select(Sale).where(Sale.idempotency_key == data.idempotency_key))
            if existing:
                return existing
        raise
    db.refresh(sale)
    return sale


def _returned_so_far(db: Session, sale_item_id: int) -> tuple[Decimal, Decimal, Decimal]:
    row = db.execute(
        select(
            func.coalesce(func.sum(SaleReturnItem.taxable_value), 0),
            func.coalesce(func.sum(SaleReturnItem.tax), 0),
            func.coalesce(func.sum(SaleReturnItem.amount), 0),
        ).where(SaleReturnItem.sale_item_id == sale_item_id)
    ).one()
    return Decimal(row[0]), Decimal(row[1]), Decimal(row[2])


def create_return(db: Session, sale_id: int, data: ReturnCreate, user_id: int) -> SaleReturn:
    try:
        sale = db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
        if sale is None:
            raise SaleError("Sale not found")
        items_by_id = {i.id: i for i in sale.items}

        seen: set[int] = set()
        for line in data.items:
            if line.sale_item_id not in items_by_id:
                raise SaleError(f"Item {line.sale_item_id} is not part of this sale")
            if line.sale_item_id in seen:
                raise SaleError("Each sale item may appear only once in a return")
            seen.add(line.sale_item_id)
            item = items_by_id[line.sale_item_id]
            if line.qty > item.qty - item.returned_qty:
                raise SaleError(
                    f"Cannot return {line.qty} of {item.sku}; "
                    f"only {item.qty - item.returned_qty} left"
                )

        variants = lock_variants(
            db, [items_by_id[ln.sale_item_id].variant_id for ln in data.items if ln.restock]
        )
        store = get_store_settings(db)
        sale_return = SaleReturn(
            credit_note_no=next_document_number(
                db, "credit_note", store.credit_note_prefix, date.today()
            ),
            sale_id=sale.id,
            user_id=user_id,
            reason=data.reason,
        )
        totals = {"taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO, "amount": ZERO}

        for line in data.items:
            item = items_by_id[line.sale_item_id]
            remaining_after = item.qty - item.returned_qty - line.qty
            item_tax = item.cgst + item.sgst + item.igst
            if remaining_after == 0:
                # Final units take whatever is left, so returns sum exactly to the sale.
                prev_taxable, prev_tax, prev_amount = _returned_so_far(db, item.id)
                taxable = item.taxable_value - prev_taxable
                tax = item_tax - prev_tax
                amount = item.line_total - prev_amount
            else:
                taxable = q(item.taxable_value * line.qty / item.qty)
                tax = q(item_tax * line.qty / item.qty)
                amount = taxable + tax
            item.returned_qty += line.qty

            if item.igst > 0:
                totals["igst"] += tax
            else:
                half = q(tax / 2)
                totals["cgst"] += half
                totals["sgst"] += tax - half
            totals["taxable"] += taxable
            totals["amount"] += amount

            sale_return.items.append(
                SaleReturnItem(
                    sale_item_id=item.id,
                    qty=line.qty,
                    restock=line.restock,
                    taxable_value=taxable,
                    tax=tax,
                    amount=amount,
                )
            )

        sale_return.taxable_value = totals["taxable"]
        sale_return.cgst = totals["cgst"]
        sale_return.sgst = totals["sgst"]
        sale_return.igst = totals["igst"]
        sale_return.refund_amount = totals["amount"]
        db.add(sale_return)
        db.flush()

        for line in data.items:
            if line.restock:
                item = items_by_id[line.sale_item_id]
                move_stock(
                    db,
                    variants[item.variant_id],
                    line.qty,
                    MovementType.RETURN,
                    user_id,
                    ref_type="sale_return",
                    ref_id=sale_return.id,
                )

        fully_returned = all(i.returned_qty == i.qty for i in sale.items)
        sale.status = SaleStatus.RETURNED if fully_returned else SaleStatus.PARTIALLY_RETURNED
        db.commit()
    except (SaleError, StockError):
        db.rollback()
        raise
    db.refresh(sale_return)
    return sale_return
