from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.merchant import Merchant
from app.schemas.payment import PaymentCreate, PaymentResponse, PaymentVerify
from app.security import get_current_merchant
from app.services import payment

router = APIRouter(prefix="/payment", tags=["payment"])


@router.post("/order", response_model=PaymentResponse)
@limiter.limit("20/minute")
def create_payment(
    request: Request,
    payment_in: PaymentCreate,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        return payment.create_payment_order(db, payment_in.checkout_id, current.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/verify", response_model=PaymentResponse)
@limiter.limit("20/minute")
def verify_payment(
    request: Request,
    verify_in: PaymentVerify,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        return payment.verify_payment_signature(
            db,
            verify_in.razorpay_order_id,
            verify_in.razorpay_payment_id,
            verify_in.razorpay_signature,
            current.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
