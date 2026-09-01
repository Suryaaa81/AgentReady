from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventCreate


def log_event(
    db: Session, merchant_id: str, event_in: AuditEventCreate, checkout_id: str | None = None
) -> AuditEvent:
    event = AuditEvent(
        merchant_id=merchant_id,
        checkout_id=checkout_id,
        event_type=event_in.event_type,
        actor=event_in.actor,
        payload=event_in.payload,
        ip_address=event_in.ip_address,
        user_agent=event_in.user_agent,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_merchant_events(db: Session, merchant_id: str, limit: int = 100) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.merchant_id == merchant_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


def get_checkout_events(db: Session, checkout_id: str) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.checkout_id == checkout_id)
            .order_by(AuditEvent.created_at.asc())
        )
        .scalars()
        .all()
    )


def get_merchant_metrics(db: Session, merchant_id: str) -> dict:
    events = list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.merchant_id == merchant_id)
            .order_by(AuditEvent.created_at.asc())
        )
        .scalars()
        .all()
    )

    total_events = len(events)
    event_breakdown: dict[str, int] = {}
    for e in events:
        event_breakdown[e.event_type] = event_breakdown.get(e.event_type, 0) + 1

    total_checkouts = event_breakdown.get("CHECKOUT_CREATED", 0)
    completed_checkouts = (
        event_breakdown.get("PAYMENT_COMPLETED", 0)
        or event_breakdown.get("CHECKOUT_STATUS_COMPLETED", 0)
    )
    failed_checkouts = (
        event_breakdown.get("CHECKOUT_STATUS_FAILED", 0)
        + event_breakdown.get("PAYMENT_VERIFICATION_FAILED", 0)
    )

    policy_rejections = 0
    for e in events:
        if e.event_type == "CHECKOUT_STATUS_FAILED":
            payload = e.payload or {}
            reason = str(payload.get("failure_reason", ""))
            if "POLICY_REJECTED" in reason:
                policy_rejections += 1

    success_rate = (
        round((completed_checkouts / total_checkouts) * 100, 2)
        if total_checkouts > 0
        else 0.0
    )
    rejection_rate = (
        round((policy_rejections / total_checkouts) * 100, 2)
        if total_checkouts > 0
        else 0.0
    )

    return {
        "total_events": total_events,
        "total_checkouts": total_checkouts,
        "completed_checkouts": completed_checkouts,
        "failed_checkouts": failed_checkouts,
        "policy_rejections": policy_rejections,
        "checkout_success_rate": float(success_rate),
        "policy_rejection_rate": float(rejection_rate),
        "event_breakdown": event_breakdown,
    }

