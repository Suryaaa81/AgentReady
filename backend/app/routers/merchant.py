from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.merchant import MerchantPolicyCreate, MerchantPolicyResponse
from app.services import merchant, policy

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.get("/policies", response_model=MerchantPolicyResponse)
def get_merchant_policies(merchant_id: str, db: Session = Depends(get_db)):
    p = policy.get_policy(db, merchant_id)
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    return p


@router.put("/policies", response_model=MerchantPolicyResponse)
def update_merchant_policies(
    merchant_id: str, policy_in: MerchantPolicyCreate, db: Session = Depends(get_db)
):
    # Verify merchant exists
    m = merchant.get_merchant_by_id(db, merchant_id)
    if not m:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return policy.upsert_policy(db, merchant_id, policy_in)
