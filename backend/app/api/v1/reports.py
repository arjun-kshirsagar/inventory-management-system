import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.deps import DB, AdminUser
from app.services import reports
from app.services.money import q
from app.services.store import store_today

router = APIRouter(prefix="/reports", tags=["reports"])


_today = store_today


def _dates(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or _today()
    start = start or end - timedelta(days=29)
    if start > end:
        raise HTTPException(400, "start must be on or before end")
    return start, end


def _csv(rows: list[dict[str, Any]], name: str) -> Response:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


def _json(value: Any) -> Any:
    """Serialise Decimals as strings, matching how money appears in every other endpoint."""
    if isinstance(value, Decimal):
        return str(q(value))
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


Format = Query("json", pattern="^(json|csv)$")


@router.get("/dashboard")
def dashboard(db: DB, _: AdminUser):
    return _json(reports.dashboard(db, _today()))


@router.get("/sales")
def sales(
    db: DB,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    group_by: str = Query("day", pattern=f"^({'|'.join(reports.SALES_GROUPS)})$"),
    format: str = Format,
):
    start, end = _dates(start, end)
    data = reports.sales_report(db, start, end, group_by)
    if format == "csv":
        return _csv(data["rows"], f"sales_by_{group_by}_{start}_{end}")
    return _json(data)


@router.get("/products")
def products(
    db: DB,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(20, ge=1, le=200),
    section: str = Query("best_sellers", pattern="^(best_sellers|slow_movers|by_size|by_color)$"),
    format: str = Format,
):
    start, end = _dates(start, end)
    data = reports.product_performance(db, start, end, limit)
    if format == "csv":
        return _csv(data[section], f"{section}_{start}_{end}")
    return _json(data)


@router.get("/stock-valuation")
def stock_valuation(db: DB, _: AdminUser, format: str = Format):
    data = reports.stock_valuation(db)
    if format == "csv":
        return _csv(data["rows"], f"stock_valuation_{_today()}")
    return _json(data)


@router.get("/low-stock")
def low_stock(db: DB, _: AdminUser, format: str = Format):
    rows = reports.low_stock(db)
    if format == "csv":
        return _csv(rows, f"low_stock_{_today()}")
    return _json(rows)


@router.get("/gst")
def gst_summary(
    db: DB,
    _: AdminUser,
    start: date | None = None,
    end: date | None = None,
    section: str = Query("hsn", pattern="^(hsn|credit_notes|by_supply_type)$"),
    format: str = Format,
):
    start, end = _dates(start, end)
    data = reports.gst_summary(db, start, end)
    if format == "csv":
        return _csv(data[section], f"gst_{section}_{start}_{end}")
    return _json(data)


@router.get("/profit")
def profit(
    db: DB, _: AdminUser, start: date | None = None, end: date | None = None, format: str = Format
):
    start, end = _dates(start, end)
    data = reports.profit(db, start, end)
    if format == "csv":
        return _csv(data["rows"], f"profit_{start}_{end}")
    return _json(data)
