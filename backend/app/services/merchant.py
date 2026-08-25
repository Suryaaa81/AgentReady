from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.merchant import Merchant


def get_merchant_by_id(db: Session, merchant_id: str) -> Merchant | None:
    return db.execute(select(Merchant).where(Merchant.id == merchant_id)).scalar_one_or_none()


def get_first_merchant(db: Session) -> Merchant | None:
    return db.execute(select(Merchant).limit(1)).scalar_one_or_none()
