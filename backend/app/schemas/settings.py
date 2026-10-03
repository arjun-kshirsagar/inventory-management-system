from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class StoreSettingsIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = ""
    phone: str | None = None
    email: str | None = None
    gstin: str | None = Field(default=None, pattern=r"^\d{2}[A-Z0-9]{13}$")
    state_code: str = Field(pattern=r"^\d{2}$")
    state_name: str
    invoice_prefix: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    credit_note_prefix: str = Field(min_length=1, max_length=10, pattern=r"^[A-Za-z0-9-]+$")
    footer_terms: str | None = None


class StoreSettingsOut(StoreSettingsIn, ORMModel):
    pass


class TaxSlabIn(BaseModel):
    name: str
    hsn_prefix: str = Field(default="", pattern=r"^\d{0,8}$")
    price_threshold: Decimal | None = Field(default=None, ge=0)
    rate_below: Decimal = Field(ge=0, le=100)
    rate_above: Decimal = Field(ge=0, le=100)
    effective_from: date


class TaxSlabOut(TaxSlabIn, ORMModel):
    id: int
