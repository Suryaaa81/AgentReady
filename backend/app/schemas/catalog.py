from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


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
    attributes: Optional[dict] = None
    price_override: Optional[Decimal] = None


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantResponse(ProductVariantBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_id: str
    created_at: datetime
    inventory: Optional[InventoryResponse] = None


class ProductBase(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
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
