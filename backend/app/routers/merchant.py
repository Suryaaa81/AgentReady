from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.merchant import Merchant
from app.schemas.merchant import (
    MerchantCreate,
    MerchantPolicyCreate,
    MerchantPolicyResponse,
    MerchantRegisterResponse,
)
from app.security import get_current_merchant
from app.services import merchant, policy

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.post("/register", response_model=MerchantRegisterResponse, status_code=201)
def register_merchant(merchant_in: MerchantCreate, db: Session = Depends(get_db)):
    """Create a new merchant and return its one-time API key.

    This is the only endpoint that doesn't require `X-API-Key` — a merchant
    can't have a key before it exists. Save the returned `api_key`
    immediately: it is hashed for storage and cannot be shown again.
    """
    try:
        new_merchant, api_key = merchant.create_merchant(db, merchant_in.name, merchant_in.email)
    except ValueError:
        raise HTTPException(status_code=409, detail="A merchant with this email already exists")
    return MerchantRegisterResponse(
        id=new_merchant.id,
        name=new_merchant.name,
        email=new_merchant.email,
        created_at=new_merchant.created_at,
        updated_at=new_merchant.updated_at,
        api_key=api_key,
    )


@router.get("/policies", response_model=MerchantPolicyResponse)
def get_merchant_policies(
    current: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)
):
    p = policy.get_policy(db, current.id)
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    return p


@router.put("/policies", response_model=MerchantPolicyResponse)
def update_merchant_policies(
    policy_in: MerchantPolicyCreate,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return policy.upsert_policy(db, current.id, policy_in)
