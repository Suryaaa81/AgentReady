import hashlib
import hmac
import os
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.checkout import CheckoutSession
from app.models.order import Order, Payment
from app.schemas.audit import AuditEventCreate
from app.services.audit import log_event

try:  # pragma: no cover - optional dependency for runtime installations
    import razorpay
except ImportError:  # pragma: no cover
    razorpay = None


def _get_razorpay_credentials() -> tuple[str, str]:
    key_id = (os.getenv("RAZORPAY_KEY_ID") or settings.RAZORPAY_KEY_ID or "").strip()
    key_secret = (os.getenv("RAZORPAY_KEY_SECRET") or settings.RAZORPAY_KEY_SECRET or "").strip()
    return key_id, key_secret


def _get_razorpay_client():
    if razorpay is None:
        return None
    key_id, key_secret = _get_razorpay_credentials()
    if not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))


def _build_receipt(payment: Payment, order: Order) -> dict:
    return {
        "payment_id": payment.id,
        "order_id": order.id,
        "razorpay_order_id": payment.razorpay_order_id,
        "razorpay_payment_id": payment.razorpay_payment_id,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "merchant_id": order.merchant_id,
        "verified_at": payment.verified_at.isoformat() if payment.verified_at else None,
        "status": payment.status,
        "items": [
            {"variant_id": item.variant_id, "qty": item.quantity}
            for item in order.checkout.items
        ],
    }


def create_payment_order(db: Session, checkout_id: str, merchant_id: str | None = None) -> Payment:
    checkout = db.execute(
        select(CheckoutSession).where(CheckoutSession.id == checkout_id).with_for_update()
    ).scalar_one_or_none()
    if not checkout:
        raise ValueError("Checkout not found")
    if merchant_id is not None and checkout.merchant_id != merchant_id:
        raise ValueError("Checkout does not belong to this merchant")
    if checkout.status != "AUTHORIZED":
        raise ValueError(f"Checkout is in {checkout.status} state, must be AUTHORIZED")

    # Re-validate checkout expiration at payment initiation time
    if checkout.expires_at:
        expires_at = checkout.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            from app.services.checkout import update_checkout_status

            update_checkout_status(
                db, checkout.id, "EXPIRED", failure_reason="Checkout session has expired"
            )
            raise ValueError("Checkout session has expired")

    # Idempotency: if an order/payment already exists for this checkout, return it.
    existing_order = db.execute(
        select(Order).where(Order.checkout_id == checkout.id)
    ).scalar_one_or_none()
    if existing_order and existing_order.payment:
        return existing_order.payment

    order = existing_order or Order(
        checkout_id=checkout.id,
        merchant_id=checkout.merchant_id,
        status="PENDING",
        total_amount=checkout.total_amount,
        currency=checkout.currency,
    )
    db.add(order)
    db.flush()

    payment = Payment(
        order_id=order.id,
        amount=order.total_amount,
        currency=order.currency,
        status="PENDING",
    )
    db.add(payment)
    db.flush()

    rzp_order_id = f"order_{order.id[:18]}"
    client = _get_razorpay_client()
    if client is None and settings.PAYMENT_PROVIDER.lower() != "mock":
        db.rollback()
        raise ValueError("Razorpay credentials are not configured")
    if client is not None:
        try:
            response = client.order.create(
                data={
                    "amount": int(float(order.total_amount) * 100),
                    "currency": order.currency,
                    "receipt": str(order.id),
                    "notes": {
                        "checkout_id": checkout.id,
                        "merchant_id": checkout.merchant_id,
                    },
                    "payment_capture": 1,
                }
            )
            rzp_order_id = response.get("id") or rzp_order_id
        except Exception as exc:
            db.rollback()
            raise ValueError(f"Razorpay order creation failed: {exc}") from exc

    payment.razorpay_order_id = rzp_order_id
    checkout.status = "PAYMENT_PENDING"
    db.commit()
    db.refresh(payment)

    log_event(
        db,
        checkout.merchant_id,
        AuditEventCreate(
            event_type="PAYMENT_INITIATED",
            actor="system",
            payload={
                "payment_id": payment.id,
                "order_id": order.id,
                "razorpay_order_id": rzp_order_id,
            },
        ),
        checkout_id=checkout.id,
    )

    return payment


def verify_payment_signature(
    db: Session,
    rzp_order_id: str,
    rzp_payment_id: str,
    signature: str,
    merchant_id: str | None = None,
) -> Payment:
    payment = db.execute(
        select(Payment).where(Payment.razorpay_order_id == rzp_order_id).with_for_update()
    ).scalar_one_or_none()
    if not payment:
        raise ValueError("Payment not found")
    if merchant_id is not None and payment.order.merchant_id != merchant_id:
        raise ValueError("Payment does not belong to this merchant")

    # Idempotency: do not trust a duplicated client payload or re-verify a completed payment.
    if payment.status == "COMPLETED":
        return payment

    if payment.razorpay_payment_id and payment.razorpay_payment_id != rzp_payment_id:
        raise ValueError("Payment already linked to a different Razorpay payment")

    key_secret = os.getenv("RAZORPAY_KEY_SECRET") or settings.RAZORPAY_KEY_SECRET
    if not key_secret:
        raise ValueError("Razorpay key secret not configured")

    msg = f"{rzp_order_id}|{rzp_payment_id}".encode()
    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        msg,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(generated_signature, signature):
        payment.status = "FAILED"
        payment.order.status = "FAILED"
        from app.services.checkout import update_checkout_status

        update_checkout_status(
            db,
            payment.order.checkout_id,
            "FAILED",
            failure_reason="Invalid Razorpay signature",
        )
        db.commit()

        log_event(
            db,
            payment.order.merchant_id,
            AuditEventCreate(
                event_type="PAYMENT_VERIFICATION_FAILED",
                actor="system",
                payload={"payment_id": payment.id, "reason": "Invalid Signature"},
            ),
            checkout_id=payment.order.checkout_id,
        )
        raise ValueError("Invalid Razorpay signature")

    payment.status = "COMPLETED"
    payment.razorpay_payment_id = rzp_payment_id
    payment.verified_at = datetime.now(UTC)
    payment.order.status = "COMPLETED"

    from app.services.checkout import update_checkout_status

    update_checkout_status(db, payment.order.checkout_id, "COMPLETED")

    receipt_data = _build_receipt(payment, payment.order)
    payment.receipt_data = receipt_data
    db.commit()
    db.refresh(payment)

    log_event(
        db,
        payment.order.merchant_id,
        AuditEventCreate(
            event_type="PAYMENT_COMPLETED",
            actor="system",
            payload={
                "payment_id": payment.id,
                "razorpay_payment_id": rzp_payment_id,
                "amount": float(payment.amount),
                "receipt": receipt_data,
            },
        ),
        checkout_id=payment.order.checkout_id,
    )

    return payment
