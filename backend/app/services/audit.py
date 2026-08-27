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
