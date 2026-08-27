from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.merchant import Merchant, MerchantPolicy
from app.security import generate_api_key, hash_api_key


def get_merchant_by_id(db: Session, merchant_id: str) -> Merchant | None:
    return db.execute(select(Merchant).where(Merchant.id == merchant_id)).scalar_one_or_none()


def get_first_merchant(db: Session) -> Merchant | None:
    return db.execute(select(Merchant).limit(1)).scalar_one_or_none()


def create_merchant(db: Session, name: str, email: str) -> tuple[Merchant, str]:
    """Create a merchant with a default policy and a fresh API key.

    Returns (merchant, plaintext_api_key). The plaintext key is only ever
    available here, at creation time — only its hash is persisted.

    Raises ValueError if the email is already registered. Checked upfront
    (rather than catching the resulting IntegrityError) so callers never
    need to roll back the session on this path.
    """
    existing = db.execute(select(Merchant).where(Merchant.email == email)).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"A merchant with email {email} already exists")

    plaintext_key = generate_api_key()
    merchant = Merchant(name=name, email=email, api_key_hash=hash_api_key(plaintext_key))
    db.add(merchant)
    db.flush()

    # Sensible, conservative defaults so a new merchant is immediately usable
    # without a separate "set up your policy" step.
    default_policy = MerchantPolicy(
        merchant_id=merchant.id,
        max_autonomous_amount=2000,
        currency="INR",
        daily_limit=10000,
        approval_threshold=1000,
    )
    db.add(default_policy)
    db.commit()
    db.refresh(merchant)
    return merchant, plaintext_key
