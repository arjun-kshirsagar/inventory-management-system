from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import Money


class StoreSettings(Base):
    """Single-row table (id=1) holding store identity printed on invoices."""

    __tablename__ = "store_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(200), default="My Clothing Store")
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state_code: Mapped[str] = mapped_column(String(2), default="27")
    state_name: Mapped[str] = mapped_column(String(60), default="Maharashtra")
    invoice_prefix: Mapped[str] = mapped_column(String(10), default="INV")
    credit_note_prefix: Mapped[str] = mapped_column(String(10), default="CN")
    footer_terms: Mapped[str | None] = mapped_column(Text)


class TaxSlab(Base):
    """GST rate rule. Matches products whose HSN starts with hsn_prefix.

    rate_below applies when the per-unit taxable value is <= price_threshold, otherwise
    rate_above. With no threshold, rate_below always applies. The most specific
    (longest) prefix with the latest effective_from on or before the sale date wins.
    """

    __tablename__ = "tax_slabs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    hsn_prefix: Mapped[str] = mapped_column(String(8), default="")
    price_threshold: Mapped[Decimal | None] = mapped_column(Money)
    rate_below: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    rate_above: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    effective_from: Mapped[date] = mapped_column(Date)
