from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.audit import AuditEventResponse
from app.services import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/merchant", response_model=list[AuditEventResponse])
def get_merchant_timeline(merchant_id: str, db: Session = Depends(get_db)):
    return audit.get_merchant_events(db, merchant_id)


@router.get("/checkout/{checkout_id}", response_model=list[AuditEventResponse])
def get_checkout_timeline(checkout_id: str, db: Session = Depends(get_db)):
    return audit.get_checkout_events(db, checkout_id)
