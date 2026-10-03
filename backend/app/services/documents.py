"""HTML/PDF rendering for tax invoices, thermal receipts, credit notes and barcode labels."""

from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import barcode
from barcode.writer import SVGWriter
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from weasyprint import HTML

from app.core.config import get_settings
from app.models import ProductVariant, Sale, SaleReturn, StoreSettings
from app.services.money import amount_in_words

_env = Environment(
    loader=FileSystemLoader(Path(__file__).resolve().parent.parent / "templates"),
    autoescape=select_autoescape(["html"]),
)
_env.filters["inr"] = lambda v: f"{v:,.2f}"
_env.filters["local"] = lambda dt, fmt="%d-%m-%Y %H:%M": dt.astimezone(
    ZoneInfo(get_settings().store_timezone)
).strftime(fmt)


def _tax_breakup(items) -> list[dict]:
    """Group by HSN + rate, as required on a GST invoice."""
    groups: dict[tuple[str, object], dict] = {}
    for i in items:
        g = groups.setdefault(
            (i.hsn_code, i.gst_rate),
            {"hsn": i.hsn_code, "rate": i.gst_rate, "taxable": 0, "cgst": 0, "sgst": 0, "igst": 0},
        )
        g["taxable"] += i.taxable_value
        g["cgst"] += i.cgst
        g["sgst"] += i.sgst
        g["igst"] += i.igst
    return list(groups.values())


def render_invoice_html(sale: Sale, store: StoreSettings, layout: str = "a4") -> str:
    template = _env.get_template("receipt.html" if layout == "thermal" else "invoice.html")
    return template.render(
        sale=sale,
        store=store,
        tax_breakup=_tax_breakup(sale.items),
        interstate=sale.igst > 0,
        amount_words=amount_in_words(sale.grand_total),
    )


def render_credit_note_html(sale_return: SaleReturn, store: StoreSettings) -> str:
    return _env.get_template("credit_note.html").render(
        ret=sale_return,
        sale=sale_return.sale,
        store=store,
        amount_words=amount_in_words(sale_return.refund_amount),
    )


def barcode_svg(code: str) -> Markup:
    buf = BytesIO()
    barcode.get("code128", code, writer=SVGWriter()).write(
        buf, options={"module_height": 8, "font_size": 6, "text_distance": 3, "quiet_zone": 2}
    )
    svg = buf.getvalue().decode()
    return Markup(svg[svg.index("<svg") :])


def render_labels_html(variants: list[tuple[ProductVariant, int]], store: StoreSettings) -> str:
    labels = [
        {"variant": v, "svg": barcode_svg(v.barcode)}
        for v, copies in variants
        for _ in range(copies)
    ]
    return _env.get_template("labels.html").render(labels=labels, store=store)


def to_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()
