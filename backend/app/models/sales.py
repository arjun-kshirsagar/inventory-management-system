from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.catalog import ProductVariant
from app.models.enums import PaymentMethod, SaleStatus
from app.models.types import money_column
from app.models.user import User


def _enum(cls):
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state_code: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(Text)


class DocumentCounter(Base):
    """Gapless per-financial-year numbering for invoices and credit notes.

    A row-locked counter is used instead of a Postgres SEQUENCE because sequences
    leave gaps on rollback, and GST invoice series must be consecutive.
    """

    __tablename__ = "document_counters"

    doc_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    financial_year: Mapped[str] = mapped_column(String(7), primary_key=True)  # e.g. 2026-27
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class Sale(TimestampMixin, Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    cashier_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    place_of_supply: Mapped[str] = mapped_column(String(2))
    subtotal: Mapped[Decimal] = money_column()
    discount: Mapped[Decimal] = money_column()
    taxable_value: Mapped[Decimal] = money_column()
    cgst: Mapped[Decimal] = money_column()
    sgst: Mapped[Decimal] = money_column()
    igst: Mapped[Decimal] = money_column()
    round_off: Mapped[Decimal] = money_column()
    grand_total: Mapped[Decimal] = money_column()
    status: Mapped[SaleStatus] = mapped_column(_enum(SaleStatus), default=SaleStatus.COMPLETED)
    notes: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer | None] = relationship()
    cashier: Mapped[User] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", order_by="SaleItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    returns: Mapped[list["SaleReturn"]] = relationship(back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), index=True)
    # Snapshot of catalog data at time of sale, so later edits don't alter old invoices.
    product_name: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str] = mapped_column(String(64))
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(40))
    hsn_code: Mapped[str] = mapped_column(String(8))
    qty: Mapped[int] = mapped_column(Integer)
    returned_qty: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[Decimal] = money_column()
    unit_cost: Mapped[Decimal] = money_column()
    discount: Mapped[Decimal] = money_column()
    taxable_value: Mapped[Decimal] = money_column()
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    cgst: Mapped[Decimal] = money_column()
    sgst: Mapped[Decimal] = money_column()
    igst: Mapped[Decimal] = money_column()
    line_total: Mapped[Decimal] = money_column()

    sale: Mapped[Sale] = relationship(back_populates="items")
    variant: Mapped[ProductVariant] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod))
    amount: Mapped[Decimal] = money_column()
    reference: Mapped[str | None] = mapped_column(String(100))

    sale: Mapped[Sale] = relationship(back_populates="payments")


class SaleReturn(TimestampMixin, Base):
    """A return against a sale; its credit_note_no is the GST credit note number."""

    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    credit_note_no: Mapped[str] = mapped_column(String(40), unique=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    taxable_value: Mapped[Decimal] = money_column()
    cgst: Mapped[Decimal] = money_column()
    sgst: Mapped[Decimal] = money_column()
    igst: Mapped[Decimal] = money_column()
    refund_amount: Mapped[Decimal] = money_column()
    reason: Mapped[str | None] = mapped_column(Text)

    sale: Mapped[Sale] = relationship(back_populates="returns")
    items: Mapped[list["SaleReturnItem"]] = relationship(
        back_populates="sale_return", cascade="all, delete-orphan"
    )


class SaleReturnItem(Base):
    __tablename__ = "sale_return_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_id: Mapped[int] = mapped_column(ForeignKey("sale_returns.id", ondelete="CASCADE"))
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id"))
    qty: Mapped[int] = mapped_column(Integer)
    restock: Mapped[bool] = mapped_column(Boolean, default=True)
    taxable_value: Mapped[Decimal] = money_column()
    tax: Mapped[Decimal] = money_column()
    amount: Mapped[Decimal] = money_column()

    sale_return: Mapped[SaleReturn] = relationship(back_populates="items")
    sale_item: Mapped[SaleItem] = relationship()
