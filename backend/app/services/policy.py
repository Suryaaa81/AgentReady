from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.merchant import MerchantPolicy
from app.schemas.merchant import MerchantPolicyCreate

def get_policy(db: Session, merchant_id: str) -> Optional[MerchantPolicy]:
    return db.execute(
        select(MerchantPolicy)
        .where(MerchantPolicy.merchant_id == merchant_id)
        .order_by(MerchantPolicy.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

def upsert_policy(db: Session, merchant_id: str, policy_in: MerchantPolicyCreate) -> MerchantPolicy:
    policy = get_policy(db, merchant_id)
    if not policy:
        policy = MerchantPolicy(merchant_id=merchant_id, **policy_in.model_dump())
        db.add(policy)
    else:
        for k, v in policy_in.model_dump().items():
            setattr(policy, k, v)
    
    db.commit()
    db.refresh(policy)
    return policy
