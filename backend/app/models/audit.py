from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created

if TYPE_CHECKING:
    from app.models.checkout import CheckoutSession
    from app.models.merchant import Merchant


class AuditEvent(Base):
    """
    Immutable audit log — one event per checkout state transition.
    created_at has no updated_at by design (append-only).
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    checkout_id: Mapped[str | None] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("checkout_sessions.id"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # "agent" | "merchant" | "system"
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = ts_created()

    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="audit_events")
    checkout: Mapped[CheckoutSession | None] = relationship(
        "CheckoutSession", back_populates="audit_events"
    )
