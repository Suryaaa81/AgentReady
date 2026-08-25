from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CheckoutItemBase(BaseModel):
    variant_id: str = Field(min_length=36, max_length=36)
    quantity: int = Field(gt=0, le=100)


class CheckoutItemCreate(CheckoutItemBase):
    pass


class CheckoutItemResponse(CheckoutItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    checkout_id: str
    unit_price: Decimal
    created_at: datetime


class CheckoutSessionBase(BaseModel):
    merchant_id: str = Field(min_length=36, max_length=36)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class CheckoutSessionCreate(CheckoutSessionBase):
    items: list[CheckoutItemCreate]


class CheckoutSessionResponse(CheckoutSessionBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    failure_reason: str | None = None
    total_amount: Decimal | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[CheckoutItemResponse] = []


class PurchaseIntentBase(BaseModel):
    max_amount: Decimal = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    allowed_category: str | None = None


class PurchaseIntentCreate(PurchaseIntentBase):
    pass


class PurchaseIntentResponse(PurchaseIntentBase):
    model_config = ConfigDict(from_attributes=True)
    intent_id: str
    merchant_id: str
    status: str
    expires_at: datetime | None = None
    created_at: datetime
