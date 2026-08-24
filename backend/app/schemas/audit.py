from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class AuditEventCreate(BaseModel):
    event_type: str
    actor: str
    payload: dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    merchant_id: str
    checkout_id: Optional[str]
    event_type: str
    actor: str
    payload: dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
