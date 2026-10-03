from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.catalog import ProductVariant
from app.models.enums import MovementType
from app.models.types import money_column
from app.models.user import User


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)


class StockReceipt(TimestampMixin, Base):
    """Goods received note (GRN)."""

    __tablename__ = "stock_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    invoice_ref: Mapped[str | None] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier | None] = relationship()
    creator: Mapped[User] = relationship()
    items: Mapped[list["StockReceiptItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class StockReceiptItem(Base):
    __tablename__ = "stock_receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("stock_receipts.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = money_column()

    receipt: Mapped[StockReceipt] = relationship(back_populates="items")
    variant: Mapped[ProductVariant] = relationship()


class StockMovement(TimestampMixin, Base):
    """Append-only stock ledger. SUM(qty_delta) per variant == quantity_on_hand."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("product_variants.id"), index=True)
    qty_delta: Mapped[int] = mapped_column(Integer)
    type: Mapped[MovementType] = mapped_column(
        Enum(
            MovementType,
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        )
    )
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(255))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    variant: Mapped[ProductVariant] = relationship()
    user: Mapped[User | None] = relationship()
