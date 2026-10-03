from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import PaymentMethod, SaleStatus
from app.schemas.common import ORMModel


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str = Field(pattern=r"^\+?\d{10,15}$")
    email: str | None = None
    gstin: str | None = Field(default=None, pattern=r"^\d{2}[A-Z0-9]{13}$")
    state_code: str | None = Field(default=None, pattern=r"^\d{2}$")
    address: str | None = None


class CustomerOut(ORMModel):
    id: int
    name: str
    phone: str
    email: str | None
    gstin: str | None
    state_code: str | None
    address: str | None


class SaleItemIn(BaseModel):
    variant_id: int
    qty: int = Field(gt=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class PaymentIn(BaseModel):
    method: PaymentMethod
    amount: Decimal = Field(gt=0)
    reference: str | None = None


class SaleCreate(BaseModel):
    items: list[SaleItemIn] = Field(min_length=1)
    payments: list[PaymentIn] = Field(min_length=1)
    customer_id: int | None = None
    bill_discount: Decimal = Field(default=Decimal("0"), ge=0)
    idempotency_key: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class SaleQuote(BaseModel):
    """Totals preview for the POS cart (no stock or payments changed)."""

    items: list[SaleItemIn] = Field(min_length=1)
    customer_id: int | None = None
    bill_discount: Decimal = Field(default=Decimal("0"), ge=0)


class SaleItemOut(ORMModel):
    id: int
    variant_id: int
    product_name: str
    sku: str
    size: str
    color: str
    hsn_code: str
    qty: int
    returned_qty: int
    unit_price: Decimal
    discount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    line_total: Decimal


class PaymentOut(ORMModel):
    method: PaymentMethod
    amount: Decimal
    reference: str | None


class QuoteOut(BaseModel):
    subtotal: Decimal
    discount: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    round_off: Decimal
    grand_total: Decimal
    items: list[SaleItemOut]


class SaleReturnItemOut(ORMModel):
    sale_item_id: int
    qty: int
    restock: bool
    amount: Decimal


class SaleReturnOut(ORMModel):
    id: int
    credit_note_no: str
    sale_id: int
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    refund_amount: Decimal
    reason: str | None
    created_at: datetime
    items: list[SaleReturnItemOut]


class SaleSummary(ORMModel):
    id: int
    invoice_no: str
    created_at: datetime
    customer_name: str | None
    cashier_name: str
    grand_total: Decimal
    status: SaleStatus
    item_count: int


class SaleOut(ORMModel):
    id: int
    invoice_no: str
    created_at: datetime
    customer: CustomerOut | None
    cashier_name: str
    place_of_supply: str
    subtotal: Decimal
    discount: Decimal
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    round_off: Decimal
    grand_total: Decimal
    status: SaleStatus
    notes: str | None
    items: list[SaleItemOut]
    payments: list[PaymentOut]
    returns: list[SaleReturnOut]


class ReturnItemIn(BaseModel):
    sale_item_id: int
    qty: int = Field(gt=0)
    restock: bool = True


class ReturnCreate(BaseModel):
    items: list[ReturnItemIn] = Field(min_length=1)
    reason: str | None = None
