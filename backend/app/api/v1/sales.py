from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.deps import DB, CurrentUser
from app.models import Customer, Sale, SaleItem, SaleReturn, SaleReturnItem
from app.models.enums import Role, SaleStatus
from app.schemas.common import Page
from app.schemas.sales import (
    QuoteOut,
    ReturnCreate,
    SaleCreate,
    SaleItemOut,
    SaleOut,
    SaleQuote,
    SaleReturnOut,
    SaleSummary,
)
from app.services import documents, gst
from app.services import sales as sales_service
from app.services.reports import local_range
from app.services.stock import StockError
from app.services.store import get_store_settings, store_today

router = APIRouter(tags=["sales"])


def _load_sale(db, sale_id: int) -> Sale:
    sale = db.scalar(
        select(Sale)
        .options(
            selectinload(Sale.items),
            selectinload(Sale.payments),
            selectinload(Sale.customer),
            selectinload(Sale.cashier),
            selectinload(Sale.returns).selectinload(SaleReturn.items),
        )
        .where(Sale.id == sale_id)
    )
    if sale is None:
        raise HTTPException(404, "Sale not found")
    return sale


def _sale_out(sale: Sale) -> SaleOut:
    return SaleOut.model_validate(
        {
            **{k: getattr(sale, k) for k in SaleOut.model_fields if hasattr(sale, k)},
            "cashier_name": sale.cashier.name,
        }
    )


def _translate(e: Exception) -> HTTPException:
    if isinstance(e, StockError):
        return HTTPException(409, str(e))
    return HTTPException(400, str(e))


@router.post("/sales/quote", response_model=QuoteOut)
def quote(data: SaleQuote, db: DB, _: CurrentUser):
    try:
        cart = sales_service.quote_sale(db, data.items, data.customer_id, data.bill_discount)
    except (sales_service.SaleError, gst.TaxConfigError) as e:
        raise _translate(e) from None
    finally:
        db.rollback()  # pricing may create the default settings row; never persist from a quote
    items = [
        SaleItemOut.model_validate(
            {c: getattr(i, c) for c in SaleItemOut.model_fields if c != "id"} | {"id": 0}
        )
        for i in cart.items
    ]
    return QuoteOut(
        subtotal=cart.subtotal,
        discount=cart.discount,
        taxable_value=cart.taxable_value,
        cgst=cart.cgst,
        sgst=cart.sgst,
        igst=cart.igst,
        round_off=cart.round_off,
        grand_total=cart.grand_total,
        items=items,
    )


@router.post("/sales", response_model=SaleOut, status_code=201)
def create_sale(data: SaleCreate, db: DB, user: CurrentUser):
    try:
        sale = sales_service.create_sale(db, data, user.id)
    except (sales_service.SaleError, StockError, gst.TaxConfigError) as e:
        raise _translate(e) from None
    return _sale_out(_load_sale(db, sale.id))


@router.get("/sales", response_model=Page[SaleSummary])
def list_sales(
    db: DB,
    user: CurrentUser,
    q: str | None = None,
    start: date | None = None,
    end: date | None = None,
    status: SaleStatus | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    stmt = select(Sale).outerjoin(Customer)
    if user.role == Role.CASHIER:
        stmt = stmt.where(Sale.cashier_id == user.id)
    if q:
        stmt = stmt.where(
            Sale.invoice_no.ilike(f"%{q}%")
            | Customer.phone.contains(q)
            | Customer.name.ilike(f"%{q}%")
        )
    if start or end:
        stmt = stmt.where(local_range(Sale.created_at, start or date.min, end or store_today()))
    if status:
        stmt = stmt.where(Sale.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    item_counts = (
        select(SaleItem.sale_id, func.sum(SaleItem.qty).label("n"))
        .group_by(SaleItem.sale_id)
        .subquery()
    )
    rows = db.execute(
        stmt.add_columns(item_counts.c.n)
        .join(item_counts, item_counts.c.sale_id == Sale.id)
        .options(selectinload(Sale.cashier), selectinload(Sale.customer))
        .order_by(Sale.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    items = [
        SaleSummary(
            id=s.id,
            invoice_no=s.invoice_no,
            created_at=s.created_at,
            customer_name=s.customer.name if s.customer else None,
            cashier_name=s.cashier.name,
            grand_total=s.grand_total,
            status=s.status,
            item_count=n,
        )
        for s, n in rows
    ]
    return Page(items=items, total=total)


def _check_access(sale: Sale, user) -> None:
    if user.role == Role.CASHIER and sale.cashier_id != user.id:
        raise HTTPException(404, "Sale not found")


@router.get("/sales/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: int, db: DB, user: CurrentUser):
    sale = _load_sale(db, sale_id)
    _check_access(sale, user)
    return _sale_out(sale)


@router.post("/sales/{sale_id}/returns", response_model=SaleReturnOut, status_code=201)
def create_return(sale_id: int, data: ReturnCreate, db: DB, user: CurrentUser):
    _check_access(_load_sale(db, sale_id), user)
    try:
        sale_return = sales_service.create_return(db, sale_id, data, user.id)
    except (sales_service.SaleError, StockError) as e:
        raise _translate(e) from None
    return sale_return


@router.get("/sales/{sale_id}/invoice.pdf", response_class=Response)
def invoice_pdf(
    sale_id: int, db: DB, user: CurrentUser, layout: str = Query("a4", pattern="^(a4|thermal)$")
):
    sale = _load_sale(db, sale_id)
    _check_access(sale, user)
    pdf = documents.to_pdf(documents.render_invoice_html(sale, get_store_settings(db), layout))
    filename = sale.invoice_no.replace("/", "-") + ".pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/sales/{sale_id}/invoice.html", response_class=HTMLResponse)
def invoice_html(
    sale_id: int, db: DB, user: CurrentUser, layout: str = Query("a4", pattern="^(a4|thermal)$")
):
    sale = _load_sale(db, sale_id)
    _check_access(sale, user)
    return documents.render_invoice_html(sale, get_store_settings(db), layout)


@router.get("/returns/{return_id}/credit-note.pdf", response_class=Response)
def credit_note_pdf(return_id: int, db: DB, user: CurrentUser):
    sale_return = db.scalar(
        select(SaleReturn)
        .options(
            selectinload(SaleReturn.items).selectinload(SaleReturnItem.sale_item),
            selectinload(SaleReturn.sale).selectinload(Sale.customer),
        )
        .where(SaleReturn.id == return_id)
    )
    if sale_return is None:
        raise HTTPException(404, "Return not found")
    _check_access(sale_return.sale, user)
    pdf = documents.to_pdf(documents.render_credit_note_html(sale_return, get_store_settings(db)))
    filename = sale_return.credit_note_no.replace("/", "-") + ".pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
