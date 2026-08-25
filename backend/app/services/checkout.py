from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Inventory, ProductVariant
from app.models.checkout import CheckoutItem, CheckoutSession, PurchaseIntent
from app.schemas.audit import AuditEventCreate
from app.schemas.checkout import CheckoutSessionCreate, PurchaseIntentCreate
from app.services.audit import log_event


def create_checkout(
    db: Session, merchant_id: str, checkout_in: CheckoutSessionCreate
) -> CheckoutSession:
    # Calculate total amount and verify inventory lock
    total_amount = 0
    items_to_add = []

    for item_in in checkout_in.items:
        # Retrieve variant and lock its inventory row for update
        variant = db.execute(
            select(ProductVariant).where(ProductVariant.id == item_in.variant_id)
        ).scalar_one_or_none()

        if not variant:
            raise ValueError(f"Variant {item_in.variant_id} not found")

        inventory = db.execute(
            select(Inventory).where(Inventory.variant_id == item_in.variant_id).with_for_update()
        ).scalar_one_or_none()

        if not inventory or inventory.available_qty < item_in.quantity:
            raise ValueError(f"Insufficient stock for variant {item_in.variant_id}")

        # Deduct available and add to reserved
        inventory.available_qty -= item_in.quantity
        inventory.reserved_qty += item_in.quantity

        unit_price = (
            variant.price_override
            if variant.price_override is not None
            else variant.product.base_price
        )
        total_amount += unit_price * item_in.quantity

        items_to_add.append(
            CheckoutItem(
                variant_id=item_in.variant_id, quantity=item_in.quantity, unit_price=unit_price
            )
        )

    # Create session
    session_obj = CheckoutSession(
        merchant_id=merchant_id,
        status="READY",
        currency=checkout_in.currency,
        total_amount=total_amount,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    db.add(session_obj)
    db.flush()

    for item in items_to_add:
        item.checkout_id = session_obj.id
        db.add(item)

    db.commit()
    db.refresh(session_obj)

    log_event(
        db,
        merchant_id,
        AuditEventCreate(
            event_type="CHECKOUT_CREATED",
            actor="system",
            payload={
                "checkout_id": session_obj.id,
                "total_amount": float(session_obj.total_amount),
            },
        ),
        checkout_id=session_obj.id,
    )

    return session_obj


def update_checkout_status(
    db: Session, checkout_id: str, status: str, failure_reason: str = None
) -> CheckoutSession:
    session_obj = db.execute(
        select(CheckoutSession).where(CheckoutSession.id == checkout_id).with_for_update()
    ).scalar_one_or_none()

    if not session_obj:
        raise ValueError(f"Checkout {checkout_id} not found")

    session_obj.status = status
    if failure_reason:
        session_obj.failure_reason = failure_reason

    # If cancelled or failed, release reserved inventory
    if status in ("CANCELLED", "FAILED", "EXPIRED"):
        for item in session_obj.items:
            inventory = db.execute(
                select(Inventory).where(Inventory.variant_id == item.variant_id).with_for_update()
            ).scalar_one_or_none()
            if inventory:
                inventory.reserved_qty -= item.quantity
                inventory.available_qty += item.quantity

    db.commit()
    db.refresh(session_obj)

    log_event(
        db,
        session_obj.merchant_id,
        AuditEventCreate(
            event_type=f"CHECKOUT_STATUS_{status}",
            actor="system",
            payload={
                "checkout_id": session_obj.id,
                "status": status,
                "failure_reason": failure_reason,
            },
        ),
        checkout_id=session_obj.id,
    )

    return session_obj


def get_checkout(db: Session, checkout_id: str) -> CheckoutSession | None:
    return db.execute(
        select(CheckoutSession).where(CheckoutSession.id == checkout_id)
    ).scalar_one_or_none()


def create_intent(db: Session, merchant_id: str, intent_in: PurchaseIntentCreate) -> PurchaseIntent:
    intent = PurchaseIntent(
        merchant_id=merchant_id,
        max_amount=intent_in.max_amount,
        currency=intent_in.currency,
        allowed_category=intent_in.allowed_category,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        status="ACTIVE",
    )
    db.add(intent)
    db.commit()
    db.refresh(intent)
    return intent


def cleanup_expired_checkouts(db: Session) -> int:
    expired_sessions = db.execute(
        select(CheckoutSession).where(
            CheckoutSession.status.notin_(("COMPLETED", "CANCELLED", "FAILED", "EXPIRED")),
            CheckoutSession.expires_at < datetime.now(UTC),
        )
    ).scalars().all()

    count = 0
    for session in expired_sessions:
        try:
            update_checkout_status(
                db, session.id, "EXPIRED", failure_reason="Session expired naturally"
            )
            count += 1
        except Exception:
            pass
    return count
