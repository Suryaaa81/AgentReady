from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class InventoryBase(BaseModel):
    available_qty: int
    reserved_qty: int


class InventoryResponse(InventoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    variant_id: str
    updated_at: datetime


class ProductVariantBase(BaseModel):
    sku: str
    attributes: dict | None = None
    price_override: Decimal | None = None


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantResponse(ProductVariantBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    created_at: datetime
    inventory: InventoryResponse | None = None


class ProductBase(BaseModel):
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    base_price: Decimal
    currency: str = "INR"
    is_active: bool = True


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = []


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    merchant_id: str
    created_at: datetime
    updated_at: datetime
    variants: list[ProductVariantResponse] = []


class CatalogImportResult(BaseModel):
    products_created: int
    products_updated: int
    variants_created: int
    variants_updated: int
    errors: list[str] = []
