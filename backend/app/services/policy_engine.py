from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import ProductVariant
from app.models.checkout import CheckoutSession, PurchaseIntent
from app.models.merchant import MerchantPolicy
from app.models.order import Order

PolicyDecision = Literal["ALLOW", "REJECT", "REQUIRE_HUMAN_APPROVAL"]


def _spent_today(db: Session, merchant_id: str, exclude_checkout_id: str | None = None) -> float:
    """Sum of COMPLETED order totals and active (AUTHORIZED / PAYMENT_PENDING)
    checkout sessions for this merchant since UTC midnight.

    Used to enforce MerchantPolicy.daily_limit. Counting active in-flight
    authorizations prevents race conditions where two concurrent checkouts both
    clear the daily limit before either payment completes.
    """
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    now = datetime.now(UTC)

    completed_total = db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.merchant_id == merchant_id,
            Order.status == "COMPLETED",
            Order.created_at >= day_start,
        )
    ).scalar_one()

    active_checkouts_query = select(
        func.coalesce(func.sum(CheckoutSession.total_amount), 0)
    ).where(
        CheckoutSession.merchant_id == merchant_id,
        CheckoutSession.status.in_(["AUTHORIZED", "PAYMENT_PENDING"]),
        CheckoutSession.created_at >= day_start,
        (CheckoutSession.expires_at.is_(None)) | (CheckoutSession.expires_at > now),
    )
    if exclude_checkout_id:
        active_checkouts_query = active_checkouts_query.where(
            CheckoutSession.id != exclude_checkout_id
        )
    active_total = db.execute(active_checkouts_query).scalar_one()

    return float(completed_total or 0) + float(active_total or 0)


class PolicyResult:
    def __init__(self, decision: PolicyDecision, reason: str = ""):
        self.decision = decision
        self.reason = reason


def evaluate_checkout_policy(
    db: Session, checkout: CheckoutSession, intent_id: str | None = None
) -> PolicyResult:
    policy = db.execute(
        select(MerchantPolicy)
        .where(MerchantPolicy.merchant_id == checkout.merchant_id)
        .order_by(MerchantPolicy.created_at.desc())
        .with_for_update()
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
            variant = db.execute(
                select(ProductVariant).where(ProductVariant.id == item.variant_id)
            ).scalar_one()
            if variant.product.category not in policy.allowed_categories:
                return PolicyResult("REJECT", f"Category '{variant.product.category}' not allowed")

    amount = checkout.total_amount or 0

    # Intent validation (AP2 bounded authorization)
    if intent_id:
        intent = db.execute(
            select(PurchaseIntent).where(PurchaseIntent.intent_id == intent_id)
        ).scalar_one_or_none()
        if not intent:
            return PolicyResult("REJECT", "Invalid purchase intent")
        if intent.merchant_id != checkout.merchant_id:
            return PolicyResult("REJECT", "Purchase intent belongs to another merchant")
        if intent.status != "ACTIVE":
            return PolicyResult("REJECT", f"Purchase intent is {intent.status}")
        if intent.expires_at:
            expires_at = intent.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at < datetime.now(UTC):
                return PolicyResult("REJECT", "Purchase intent expired")
        if amount > intent.max_amount:
            return PolicyResult("REJECT", "Amount exceeds authorized intent")
        if intent.currency != checkout.currency:
            return PolicyResult("REJECT", "Intent currency mismatch")
        if intent.allowed_category:
            for item in checkout.items:
                variant = db.execute(
                    select(ProductVariant).where(ProductVariant.id == item.variant_id)
                ).scalar_one()
                if variant.product.category != intent.allowed_category:
                    return PolicyResult(
                        "REJECT", f"Intent category mismatch for '{variant.product.category}'"
                    )

    # Daily limit check — blocks structuring and concurrent overspend (counting both
    # completed orders and active authorized checkouts).
    if policy.daily_limit is not None:
        spent_today = _spent_today(db, checkout.merchant_id, exclude_checkout_id=checkout.id)
        if spent_today + float(amount) > float(policy.daily_limit):
            return PolicyResult(
                "REJECT",
                f"Daily spend limit exceeded (spent {spent_today:.2f} + "
                f"{float(amount):.2f} > limit {float(policy.daily_limit):.2f})",
            )

    # Threshold checks
    if amount <= policy.max_autonomous_amount:
        return PolicyResult("ALLOW")
    elif policy.approval_threshold and amount <= policy.approval_threshold:
        return PolicyResult("REQUIRE_HUMAN_APPROVAL", "Amount requires human approval")
    else:
        return PolicyResult("REJECT", "Amount exceeds maximum allowable threshold")
