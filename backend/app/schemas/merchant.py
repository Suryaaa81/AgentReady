from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MerchantPolicyBase(BaseModel):
    max_autonomous_amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    daily_limit: Decimal = Field(ge=0)
    allowed_categories: list[str] | None = None
    max_delivery_days: int | None = Field(default=None, ge=0)
    min_return_days: int | None = Field(default=None, ge=0)
    approval_threshold: Decimal | None = None
    expires_at: datetime | None = None


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


class MerchantRegisterResponse(MerchantResponse):
    api_key: str = Field(
        description="Plaintext API key — shown once. Store it now; it cannot be retrieved again."
    )
