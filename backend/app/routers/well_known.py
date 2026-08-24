from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.merchant import Merchant
from app.services import policy as policy_service

router = APIRouter(tags=["discovery"])

class AgentReadyProfile(BaseModel):
    id: str = "agentready-gateway"
    name: str = "AgentReady Commerce Gateway"
    currency: str = "INR"
    capabilities: list[str] = ["checkout", "policy-gated", "audit-trail"]
    interfaces: dict[str, str] = {
        "mcp": "none",
        "rest": "true",
        "acp_style_checkout": "true"
    }
    payment_provider: str = "razorpay_test"


@router.get("/.well-known/agentready", response_model=AgentReadyProfile)
def get_agentready_profile(merchant_id: str | None = None, db: Session = Depends(get_db)):
    profile = AgentReadyProfile()
    # If merchant_id provided, return live capabilities
    if merchant_id:
        m = db.query(Merchant).filter_by(id=merchant_id).first()
        if m:
            profile.name = f"{m.name} - AgentReady Gateway"
            profile.currency = "INR"
            # check if merchant has policy
            p = policy_service.get_policy(db, merchant_id)
            if p:
                profile.capabilities = ["checkout", "policy-gated", "audit-trail", "autonomous-purchases"]
            else:
                profile.capabilities = ["checkout", "audit-trail"]
            # payment provider from env/settings
            profile.payment_provider = "razorpay_test"
    return profile
