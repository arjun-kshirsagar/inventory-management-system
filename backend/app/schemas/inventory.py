from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import MovementType
from app.schemas.common import ORMModel


class ReceiptItemIn(BaseModel):
    variant_id: int
    qty: int = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class ReceiptCreate(BaseModel):
    supplier_id: int | None = None
    invoice_ref: str | None = None
    notes: str | None = None
    update_cost_price: bool = True
    items: list[ReceiptItemIn] = Field(min_length=1)


class ReceiptItemOut(ORMModel):
    id: int
    variant_id: int
    qty: int
    unit_cost: Decimal
    sku: str
    product_name: str
    size: str
    color: str


class ReceiptOut(ORMModel):
    id: int
    supplier_id: int | None
    supplier_name: str | None
    invoice_ref: str | None
    notes: str | None
    received_at: datetime
    created_by_name: str
    total_qty: int
    total_cost: Decimal
    items: list[ReceiptItemOut]


class AdjustmentIn(BaseModel):
    variant_id: int
    qty_delta: int
    reason: str = Field(min_length=3, max_length=255)


class MovementOut(ORMModel):
    id: int
    variant_id: int
    sku: str
    product_name: str
    qty_delta: int
    type: MovementType
    ref_type: str | None
    ref_id: int | None
    reason: str | None
    user_name: str | None
    created_at: datetime


class StockLevel(BaseModel):
    variant_id: int
    product_id: int
    product_name: str
    category: str | None
    brand: str | None
    sku: str
    barcode: str
    size: str
    color: str
    quantity_on_hand: int
    reorder_level: int
    cost_price: Decimal
    selling_price: Decimal
    low_stock: bool
