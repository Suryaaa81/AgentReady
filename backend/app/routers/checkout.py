from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.merchant import Merchant
from app.schemas.checkout import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PurchaseIntentCreate,
    PurchaseIntentResponse,
)
from app.security import get_current_merchant
from app.services import checkout, policy_engine

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/sessions", response_model=CheckoutSessionResponse)
@limiter.limit("20/minute")
def create_checkout_session(
    request: Request,
    checkout_in: CheckoutSessionCreate,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        return checkout.create_checkout(db, current.id, checkout_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{checkout_id}", response_model=CheckoutSessionResponse)
def get_checkout_session(checkout_id: str, db: Session = Depends(get_db)):
    # Intentionally unauthenticated: checkout_id is an unguessable UUID that
    # functions as a bearer capability for this one resource (the same
    # pattern Stripe Checkout Sessions use) — an AI buyer polling for status
    # shouldn't need the merchant's own API key.
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


@router.post("/sessions/{checkout_id}/authorize", response_model=CheckoutSessionResponse)
def authorize_checkout_session(
    checkout_id: str, intent_id: str | None = None, db: Session = Depends(get_db)
):
    session_obj = checkout.get_checkout(db, checkout_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    if session_obj.status not in ("READY", "AUTHORIZATION_REQUIRED"):
        raise HTTPException(
            status_code=400,
            detail=f"Checkout is in {session_obj.status} state, not authorizable",
        )

    if session_obj.status == "AUTHORIZATION_REQUIRED":
        return checkout.update_checkout_status(db, checkout_id, "AUTHORIZED")

    result = policy_engine.evaluate_checkout_policy(db, session_obj, intent_id)

    if result.decision == "ALLOW":
        return checkout.update_checkout_status(db, checkout_id, "AUTHORIZED")
    elif result.decision == "REQUIRE_HUMAN_APPROVAL":
        return checkout.update_checkout_status(
            db, checkout_id, "AUTHORIZATION_REQUIRED", failure_reason=result.reason
        )
    else:
        # REJECT
        return checkout.update_checkout_status(
            db, checkout_id, "FAILED", failure_reason=f"POLICY_REJECTED: {result.reason}"
        )


@router.post("/intents", response_model=PurchaseIntentResponse)
def create_purchase_intent(
    intent_in: PurchaseIntentCreate,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return checkout.create_intent(db, current.id, intent_in)
