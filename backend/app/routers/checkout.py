from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.checkout import CheckoutSessionCreate, CheckoutSessionResponse, PurchaseIntentCreate, PurchaseIntentResponse
from app.services import checkout

router = APIRouter(prefix="/checkout", tags=["checkout"])

@router.post("/sessions", response_model=CheckoutSessionResponse)
def create_checkout_session(merchant_id: str, checkout_in: CheckoutSessionCreate, db: Session = Depends(get_db)):
    try:
        return checkout.create_checkout(db, merchant_id, checkout_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/sessions/{checkout_id}", response_model=CheckoutSessionResponse)
def get_checkout_session(checkout_id: str, db: Session = Depends(get_db)):
    session = checkout.get_checkout(db, checkout_id)
    if not session:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    return session

@router.post("/sessions/{checkout_id}/cancel", response_model=CheckoutSessionResponse)
def cancel_checkout_session(checkout_id: str, db: Session = Depends(get_db)):
    try:
        return checkout.update_checkout_status(db, checkout_id, "CANCELLED")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

from app.services import policy_engine

@router.post("/sessions/{checkout_id}/authorize", response_model=CheckoutSessionResponse)
def authorize_checkout_session(checkout_id: str, intent_id: str = None, db: Session = Depends(get_db)):
    session_obj = checkout.get_checkout(db, checkout_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    
    if session_obj.status != "READY":
        raise HTTPException(status_code=400, detail=f"Checkout is in {session_obj.status} state, not READY")

    result = policy_engine.evaluate_checkout_policy(db, session_obj, intent_id)
    
    if result.decision == "ALLOW":
        return checkout.update_checkout_status(db, checkout_id, "AUTHORIZED")
    elif result.decision == "REQUIRE_HUMAN_APPROVAL":
        return checkout.update_checkout_status(db, checkout_id, "AUTHORIZATION_REQUIRED", failure_reason=result.reason)
    else:
        # REJECT
        return checkout.update_checkout_status(db, checkout_id, "FAILED", failure_reason=f"POLICY_REJECTED: {result.reason}")

@router.post("/intents", response_model=PurchaseIntentResponse)
def create_purchase_intent(merchant_id: str, intent_in: PurchaseIntentCreate, db: Session = Depends(get_db)):
    return checkout.create_intent(db, merchant_id, intent_in)
