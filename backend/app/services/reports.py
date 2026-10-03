"""Read-only reporting queries.

Sales figures are net of returns: each sale line is scaled by (qty - returned_qty) / qty
and attributed to the original sale date. Dates are in the store's local timezone.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Date, Numeric, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Brand,
    Category,
    Payment,
    Product,
    ProductVariant,
    Sale,
    SaleItem,
    SaleReturn,
    SaleReturnItem,
    User,
)
from app.services.money import ZERO, q

Row = dict[str, Any]


def _tz() -> str:
    return get_settings().store_timezone


def local_date(column):
    return cast(func.timezone(_tz(), column), Date)


def local_range(column, start: date, end: date):
    """Inclusive [start, end] in local dates, as a sargable timestamp range."""
    zone = ZoneInfo(_tz())
    lo = datetime.combine(start, datetime.min.time(), zone)
    hi = datetime.combine(end + timedelta(days=1), datetime.min.time(), zone)
    return (column >= lo) & (column < hi)


_net_factor = cast(SaleItem.qty - SaleItem.returned_qty, Numeric) / SaleItem.qty
net_qty = SaleItem.qty - SaleItem.returned_qty
net_total = func.round(SaleItem.line_total * _net_factor, 2)
net_taxable = func.round(SaleItem.taxable_value * _net_factor, 2)
net_tax = func.round((SaleItem.cgst + SaleItem.sgst + SaleItem.igst) * _net_factor, 2)
net_cogs = SaleItem.unit_cost * net_qty


def _rows(result) -> list[Row]:
    return [dict(r._mapping) for r in result]


def dashboard(db: Session, today: date) -> Row:
    sales_today = db.execute(
        select(
            func.count(Sale.id).label("bills"),
            func.coalesce(func.sum(Sale.grand_total), 0).label("gross"),
        ).where(local_range(Sale.created_at, today, today))
    ).one()
    refunds_today = db.scalar(
        select(func.coalesce(func.sum(SaleReturn.refund_amount), 0)).where(
            local_range(SaleReturn.created_at, today, today)
        )
    )
    items_today = db.scalar(
        select(func.coalesce(func.sum(SaleItem.qty), 0))
        .join(Sale)
        .where(local_range(Sale.created_at, today, today))
    )
    low_stock = db.scalar(
        select(func.count(ProductVariant.id)).where(
            ProductVariant.is_active,
            ProductVariant.quantity_on_hand <= ProductVariant.reorder_level,
        )
    )
    start = today - timedelta(days=29)
    day = local_date(Sale.created_at)
    trend_rows = {
        r.day: r
        for r in db.execute(
            select(
                day.label("day"),
                func.count(Sale.id).label("bills"),
                func.sum(Sale.grand_total).label("total"),
            )
            .where(local_range(Sale.created_at, start, today))
            .group_by(day)
        )
    }
    trend = []
    for i in range(30):
        d = start + timedelta(days=i)
        r = trend_rows.get(d)
        trend.append({"date": d, "bills": r.bills if r else 0, "total": q(r.total) if r else ZERO})

    bills = sales_today.bills
    gross = q(sales_today.gross)
    return {
        "date": today,
        "sales_total": gross,
        "refunds_total": q(refunds_today),
        "net_sales": gross - q(refunds_today),
        "bills": bills,
        "items_sold": int(items_today),
        "average_bill": q(gross / bills) if bills else ZERO,
        "low_stock_count": low_stock,
        "trend": trend,
    }


SALES_GROUPS = ("day", "category", "brand", "cashier", "size", "color")


def sales_report(db: Session, start: date, end: date, group_by: str) -> Row:
    if group_by not in SALES_GROUPS:
        raise ValueError(f"group_by must be one of {SALES_GROUPS}")
    key = {
        "day": local_date(Sale.created_at),
        "category": func.coalesce(Category.name, "Uncategorised"),
        "brand": func.coalesce(Brand.name, "Unbranded"),
        "cashier": User.name,
        "size": SaleItem.size,
        "color": SaleItem.color,
    }[group_by]
    stmt = (
        select(
            key.label("key"),
            func.count(func.distinct(Sale.id)).label("bills"),
            func.sum(net_qty).label("qty"),
            func.sum(net_taxable).label("taxable_value"),
            func.sum(net_tax).label("tax"),
            func.sum(net_total).label("total"),
        )
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(ProductVariant, SaleItem.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .outerjoin(Brand, Product.brand_id == Brand.id)
        .join(User, Sale.cashier_id == User.id)
        .where(local_range(Sale.created_at, start, end))
        .group_by(key)
        .order_by(key if group_by == "day" else func.sum(net_total).desc())
    )
    rows = _rows(db.execute(stmt))
    payments = _rows(
        db.execute(
            select(
                Payment.method.label("method"),
                func.count(Payment.id).label("count"),
                func.sum(Payment.amount).label("amount"),
            )
            .join(Sale)
            .where(local_range(Sale.created_at, start, end))
            .group_by(Payment.method)
            .order_by(Payment.method)
        )
    )
    return {
        "rows": rows,
        "payments": payments,
        "totals": {
            "qty": sum((r["qty"] for r in rows), 0),
            "taxable_value": sum((r["taxable_value"] for r in rows), ZERO),
            "tax": sum((r["tax"] for r in rows), ZERO),
            "total": sum((r["total"] for r in rows), ZERO),
        },
    }


def _variant_sales_subquery(start: date, end: date):
    return (
        select(
            SaleItem.variant_id.label("variant_id"),
            func.sum(net_qty).label("qty_sold"),
            func.sum(net_total).label("revenue"),
        )
        .join(Sale)
        .where(local_range(Sale.created_at, start, end))
        .group_by(SaleItem.variant_id)
        .subquery()
    )


def product_performance(db: Session, start: date, end: date, limit: int = 20) -> Row:
    sold = _variant_sales_subquery(start, end)
    qty_sold = func.coalesce(sold.c.qty_sold, 0)
    base = (
        select(
            ProductVariant.id.label("variant_id"),
            Product.name.label("product_name"),
            ProductVariant.sku,
            ProductVariant.size,
            ProductVariant.color,
            qty_sold.label("qty_sold"),
            func.coalesce(sold.c.revenue, 0).label("revenue"),
            ProductVariant.quantity_on_hand.label("on_hand"),
        )
        .join(Product)
        .outerjoin(sold, sold.c.variant_id == ProductVariant.id)
        .where(ProductVariant.is_active)
    )
    best = _rows(db.execute(base.where(qty_sold > 0).order_by(qty_sold.desc()).limit(limit)))
    slow = _rows(
        db.execute(
            base.where(ProductVariant.quantity_on_hand > 0)
            .order_by(qty_sold.asc(), ProductVariant.quantity_on_hand.desc())
            .limit(limit)
        )
    )

    def sell_through(attr):
        dim = getattr(ProductVariant, attr)
        sold_sum = func.sum(qty_sold)
        on_hand = func.sum(ProductVariant.quantity_on_hand)
        rows = _rows(
            db.execute(
                select(
                    dim.label("key"),
                    sold_sum.label("qty_sold"),
                    on_hand.label("on_hand"),
                )
                .outerjoin(sold, sold.c.variant_id == ProductVariant.id)
                .where(ProductVariant.is_active)
                .group_by(dim)
                .order_by(sold_sum.desc())
            )
        )
        for r in rows:
            denom = r["qty_sold"] + r["on_hand"]
            r["sell_through_pct"] = q(Decimal(r["qty_sold"]) * 100 / denom) if denom else ZERO
        return rows

    return {
        "best_sellers": best,
        "slow_movers": slow,
        "by_size": sell_through("size"),
        "by_color": sell_through("color"),
    }


def stock_valuation(db: Session) -> Row:
    category = func.coalesce(Category.name, "Uncategorised")
    qoh = ProductVariant.quantity_on_hand
    rows = _rows(
        db.execute(
            select(
                category.label("category"),
                func.count(ProductVariant.id).label("variants"),
                func.sum(qoh).label("units"),
                func.sum(qoh * ProductVariant.cost_price).label("cost_value"),
                func.sum(qoh * ProductVariant.selling_price).label("retail_value"),
                func.sum(qoh * ProductVariant.mrp).label("mrp_value"),
            )
            .join(Product, ProductVariant.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(ProductVariant.is_active)
            .group_by(category)
            .order_by(category)
        )
    )
    totals = {
        k: sum((r[k] for r in rows), 0)
        for k in ("variants", "units", "cost_value", "retail_value", "mrp_value")
    }
    return {"rows": rows, "totals": totals}


def low_stock(db: Session) -> list[Row]:
    return _rows(
        db.execute(
            select(
                ProductVariant.id.label("variant_id"),
                Product.name.label("product_name"),
                ProductVariant.sku,
                ProductVariant.size,
                ProductVariant.color,
                ProductVariant.quantity_on_hand.label("on_hand"),
                ProductVariant.reorder_level,
                (ProductVariant.reorder_level * 2 - ProductVariant.quantity_on_hand).label(
                    "suggested_order_qty"
                ),
            )
            .join(Product)
            .where(
                ProductVariant.is_active,
                ProductVariant.quantity_on_hand <= ProductVariant.reorder_level,
            )
            .order_by(ProductVariant.quantity_on_hand, Product.name)
        )
    )


def gst_summary(db: Session, start: date, end: date) -> Row:
    """HSN-wise outward supplies and credit notes, the shape GSTR-1 tables 12 and 9B need."""
    interstate = case((Sale.igst > 0, "inter-state"), else_="intra-state")
    sales_rows = _rows(
        db.execute(
            select(
                SaleItem.hsn_code.label("hsn_code"),
                SaleItem.gst_rate.label("gst_rate"),
                func.sum(SaleItem.qty).label("qty"),
                func.sum(SaleItem.taxable_value).label("taxable_value"),
                func.sum(SaleItem.cgst).label("cgst"),
                func.sum(SaleItem.sgst).label("sgst"),
                func.sum(SaleItem.igst).label("igst"),
                func.sum(SaleItem.line_total).label("total"),
            )
            .join(Sale)
            .where(local_range(Sale.created_at, start, end))
            .group_by(SaleItem.hsn_code, SaleItem.gst_rate)
            .order_by(SaleItem.hsn_code, SaleItem.gst_rate)
        )
    )
    credit_rows = _rows(
        db.execute(
            select(
                SaleItem.hsn_code.label("hsn_code"),
                SaleItem.gst_rate.label("gst_rate"),
                func.sum(SaleReturnItem.qty).label("qty"),
                func.sum(SaleReturnItem.taxable_value).label("taxable_value"),
                func.sum(SaleReturnItem.tax).label("tax"),
                func.sum(SaleReturnItem.amount).label("total"),
            )
            .select_from(SaleReturnItem)
            .join(SaleReturn, SaleReturnItem.return_id == SaleReturn.id)
            .join(SaleItem, SaleReturnItem.sale_item_id == SaleItem.id)
            .where(local_range(SaleReturn.created_at, start, end))
            .group_by(SaleItem.hsn_code, SaleItem.gst_rate)
            .order_by(SaleItem.hsn_code, SaleItem.gst_rate)
        )
    )
    supply_rows = _rows(
        db.execute(
            select(
                interstate.label("supply_type"),
                func.count(Sale.id).label("invoices"),
                func.sum(Sale.taxable_value).label("taxable_value"),
                func.sum(Sale.cgst + Sale.sgst + Sale.igst).label("tax"),
            )
            .where(local_range(Sale.created_at, start, end))
            .group_by(interstate)
        )
    )
    return {"hsn": sales_rows, "credit_notes": credit_rows, "by_supply_type": supply_rows}


def profit(db: Session, start: date, end: date) -> Row:
    day = local_date(Sale.created_at)
    rows = _rows(
        db.execute(
            select(
                day.label("date"),
                func.sum(net_qty).label("qty"),
                func.sum(net_taxable).label("revenue"),
                func.sum(net_cogs).label("cogs"),
            )
            .join(Sale)
            .where(local_range(Sale.created_at, start, end))
            .group_by(day)
            .order_by(day)
        )
    )
    for r in rows:
        r["revenue"] = q(r["revenue"])
        r["cogs"] = q(r["cogs"])
        r["gross_profit"] = r["revenue"] - r["cogs"]
        r["margin_pct"] = q(r["gross_profit"] * 100 / r["revenue"]) if r["revenue"] else ZERO
    revenue = sum((r["revenue"] for r in rows), ZERO)
    cogs = sum((r["cogs"] for r in rows), ZERO)
    return {
        "rows": rows,
        "totals": {
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": revenue - cogs,
            "margin_pct": q((revenue - cogs) * 100 / revenue) if revenue else ZERO,
        },
    }
