from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None


class CategoryOut(ORMModel):
    id: int
    name: str
    parent_id: int | None


class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class BrandOut(ORMModel):
    id: int
    name: str


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    phone: str | None = None
    address: str | None = None


class SupplierOut(ORMModel):
    id: int
    name: str
    gstin: str | None
    phone: str | None
    address: str | None


class VariantBase(BaseModel):
    size: str = Field(min_length=1, max_length=20)
    color: str = Field(min_length=1, max_length=40)
    mrp: Decimal = Field(ge=0, decimal_places=2)
    selling_price: Decimal = Field(ge=0, decimal_places=2)
    cost_price: Decimal = Field(ge=0, decimal_places=2)
    reorder_level: int = Field(default=5, ge=0)

    @model_validator(mode="after")
    def price_not_above_mrp(self):
        if self.selling_price > self.mrp:
            raise ValueError("Selling price cannot exceed MRP")
        return self


class VariantCreate(VariantBase):
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)


class VariantUpdate(BaseModel):
    mrp: Decimal | None = Field(default=None, ge=0)
    selling_price: Decimal | None = Field(default=None, ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    barcode: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class VariantOut(ORMModel):
    id: int
    product_id: int
    sku: str
    barcode: str
    size: str
    color: str
    mrp: Decimal
    selling_price: Decimal
    cost_price: Decimal
    reorder_level: int
    quantity_on_hand: int
    is_active: bool


class VariantMatrix(BaseModel):
    """Generate one variant per size x color, all at the same prices."""

    sizes: list[str] = Field(min_length=1)
    colors: list[str] = Field(min_length=1)
    mrp: Decimal = Field(ge=0)
    selling_price: Decimal = Field(ge=0)
    cost_price: Decimal = Field(ge=0)
    reorder_level: int = Field(default=5, ge=0)


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category_id: int | None = None
    brand_id: int | None = None
    description: str | None = None
    hsn_code: str = Field(pattern=r"^\d{4,8}$")
    gender: str | None = None
    material: str | None = None


class ProductCreate(ProductBase):
    variants: list[VariantCreate] = []
    matrix: VariantMatrix | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: int | None = None
    brand_id: int | None = None
    description: str | None = None
    hsn_code: str | None = Field(default=None, pattern=r"^\d{4,8}$")
    gender: str | None = None
    material: str | None = None
    is_active: bool | None = None


class ProductOut(ORMModel):
    id: int
    name: str
    category_id: int | None
    brand_id: int | None
    category: CategoryOut | None
    brand: BrandOut | None
    description: str | None
    hsn_code: str
    gender: str | None
    material: str | None
    is_active: bool
    variants: list[VariantOut]


class VariantLookup(VariantOut):
    """Variant with its product's name, for POS search results."""

    product_name: str
    hsn_code: str


class ImportResult(BaseModel):
    products_created: int
    variants_created: int
    errors: list[str]
