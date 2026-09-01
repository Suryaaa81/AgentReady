from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventCreate(BaseModel):
    event_type: str
    actor: str
    payload: dict[str, Any]
    ip_address: str | None = None
    user_agent: str | None = None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    merchant_id: str
    checkout_id: str | None
    event_type: str
    actor: str
    payload: dict[str, Any]
    ip_address: str | None
    user_agent: str | None
    created_at: datetime


class AuditMetricsResponse(BaseModel):
    total_events: int
    total_checkouts: int
    completed_checkouts: int
    failed_checkouts: int
    policy_rejections: int
    checkout_success_rate: float
    policy_rejection_rate: float
    event_breakdown: dict[str, int]
