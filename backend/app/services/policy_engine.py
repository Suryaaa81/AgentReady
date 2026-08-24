from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.checkout import CheckoutSession, PurchaseIntent, CheckoutItem
from app.models.merchant import MerchantPolicy
from app.models.catalog import ProductVariant
from typing import Literal

PolicyDecision = Literal["ALLOW", "REJECT", "REQUIRE_HUMAN_APPROVAL"]

class PolicyResult:
    def __init__(self, decision: PolicyDecision, reason: str = ""):
        self.decision = decision
        self.reason = reason

def evaluate_checkout_policy(db: Session, checkout: CheckoutSession, intent_id: str | None = None) -> PolicyResult:
    policy = db.execute(
        select(MerchantPolicy).where(MerchantPolicy.merchant_id == checkout.merchant_id).order_by(MerchantPolicy.created_at.desc())
    ).scalar_one_or_none()
    
    if not policy:
        return PolicyResult("REQUIRE_HUMAN_APPROVAL", "No merchant policy configured")

    # Currency match
    if checkout.currency != policy.currency:
        return PolicyResult("REJECT", "Currency mismatch with merchant policy")

    # Category check
    if policy.allowed_categories:
        # Check if all items belong to allowed categories
        for item in checkout.items:
            variant = db.execute(select(ProductVariant).where(ProductVariant.id == item.variant_id)).scalar_one()
            if variant.product.category not in policy.allowed_categories:
                return PolicyResult("REJECT", f"Category '{variant.product.category}' not allowed")

    amount = checkout.total_amount or 0

    # Intent validation (AP2 bounded authorization)
    if intent_id:
        intent = db.execute(select(PurchaseIntent).where(PurchaseIntent.intent_id == intent_id)).scalar_one_or_none()
        if not intent:
            return PolicyResult("REJECT", "Invalid purchase intent")
        if intent.status != "ACTIVE":
            return PolicyResult("REJECT", f"Purchase intent is {intent.status}")
        if intent.expires_at:
            expires_at = intent.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                return PolicyResult("REJECT", "Purchase intent expired")
        if amount > intent.max_amount:
            return PolicyResult("REJECT", "Amount exceeds authorized intent")
        if intent.currency != checkout.currency:
            return PolicyResult("REJECT", "Intent currency mismatch")
        if intent.allowed_category:
            for item in checkout.items:
                variant = db.execute(select(ProductVariant).where(ProductVariant.id == item.variant_id)).scalar_one()
                if variant.product.category != intent.allowed_category:
                    return PolicyResult("REJECT", f"Intent category mismatch for '{variant.product.category}'")

    # Threshold checks
    if amount <= policy.max_autonomous_amount:
        return PolicyResult("ALLOW")
    elif policy.approval_threshold and amount <= policy.approval_threshold:
        return PolicyResult("REQUIRE_HUMAN_APPROVAL", "Amount requires human approval")
    else:
        return PolicyResult("REJECT", "Amount exceeds maximum allowable threshold")
