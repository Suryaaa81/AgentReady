from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.merchant import Merchant
from typing import Optional


def get_merchant_by_id(db: Session, merchant_id: str) -> Optional[Merchant]:
    return db.execute(select(Merchant).where(Merchant.id == merchant_id)).scalar_one_or_none()

def get_first_merchant(db: Session) -> Optional[Merchant]:
    return db.execute(select(Merchant).limit(1)).scalar_one_or_none()
