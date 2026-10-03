from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.types import money_column


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id")

    __table_args__ = (UniqueConstraint("name", "parent_id"),)


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"))
    description: Mapped[str | None] = mapped_column(Text)
    hsn_code: Mapped[str] = mapped_column(String(8))
    gender: Mapped[str | None] = mapped_column(String(20))
    material: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[Category | None] = relationship()
    brand: Mapped[Brand | None] = relationship()
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.id"
    )


class ProductVariant(TimestampMixin, Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    barcode: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    size: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(40))
    mrp: Mapped[Decimal] = money_column()
    selling_price: Mapped[Decimal] = money_column()
    cost_price: Mapped[Decimal] = money_column()
    reorder_level: Mapped[int] = mapped_column(Integer, default=5)
    # Cached total; only services/stock.py may change it (always with a StockMovement row).
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped[Product] = relationship(back_populates="variants")

    __table_args__ = (UniqueConstraint("product_id", "size", "color"),)
