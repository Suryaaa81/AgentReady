from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class CheckoutItemBase(BaseModel):
    variant_id: str
    quantity: int


class CheckoutItemCreate(CheckoutItemBase):
    pass


class CheckoutItemResponse(CheckoutItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    checkout_id: str
    unit_price: Decimal
    created_at: datetime


class CheckoutSessionBase(BaseModel):
    merchant_id: str
    currency: str = "INR"


class CheckoutSessionCreate(CheckoutSessionBase):
    items: list[CheckoutItemCreate]


class CheckoutSessionResponse(CheckoutSessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    failure_reason: Optional[str] = None
    total_amount: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: list[CheckoutItemResponse] = []


class PurchaseIntentBase(BaseModel):
    max_amount: Decimal
    currency: str = "INR"
    allowed_category: Optional[str] = None


class PurchaseIntentCreate(PurchaseIntentBase):
    pass


class PurchaseIntentResponse(PurchaseIntentBase):
    model_config = ConfigDict(from_attributes=True)
    intent_id: str
    merchant_id: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
