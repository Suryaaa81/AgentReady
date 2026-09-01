from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.merchant import Merchant
from app.schemas.audit import AuditEventResponse, AuditMetricsResponse
from app.security import get_current_merchant
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/metrics", response_model=AuditMetricsResponse)
def get_merchant_metrics(
    current: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)
):
    return audit.get_merchant_metrics(db, current.id)


@router.get("/merchant", response_model=list[AuditEventResponse])
def get_merchant_timeline(
    current: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)
):
    return audit.get_merchant_events(db, current.id)


@router.get("/checkout/{checkout_id}", response_model=list[AuditEventResponse])
def get_checkout_timeline(checkout_id: str, db: Session = Depends(get_db)):
    # Same unauthenticated-by-design pattern as GET /checkout/sessions/{id}:
    # checkout_id is the capability token here.
    return audit.get_checkout_events(db, checkout_id)
