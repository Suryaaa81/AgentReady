from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal


class MerchantPolicyBase(BaseModel):
    max_autonomous_amount: Decimal
    currency: str = "INR"
    daily_limit: Decimal
    allowed_categories: Optional[list[str]] = None
    max_delivery_days: Optional[int] = None
    min_return_days: Optional[int] = None
    approval_threshold: Optional[Decimal] = None
    expires_at: Optional[datetime] = None


class MerchantPolicyCreate(MerchantPolicyBase):
    pass


class MerchantPolicyResponse(MerchantPolicyBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    merchant_id: str
    created_at: datetime
    updated_at: datetime


class MerchantBase(BaseModel):
    name: str
    email: str


class MerchantCreate(MerchantBase):
    pass


class MerchantResponse(MerchantBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime
    policies: list[MerchantPolicyResponse] = []
