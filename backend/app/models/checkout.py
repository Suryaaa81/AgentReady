from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created, ts_updated

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.merchant import Merchant
    from app.models.order import Order


class CheckoutSession(Base):
    """
    Tracks an agent-initiated checkout through the state machine:
    CREATED → READY → (AUTHORIZATION_REQUIRED → AUTHORIZED)? → PAYMENT_PENDING → COMPLETED
    Side states: CANCELLED, EXPIRED, FAILED
    """

    __tablename__ = "checkout_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="CREATED", index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="checkout_sessions")
    items: Mapped[list[CheckoutItem]] = relationship(
        "CheckoutItem", back_populates="checkout", cascade="all, delete-orphan"
    )
    order: Mapped[Order | None] = relationship("Order", back_populates="checkout", uselist=False)
    audit_events: Mapped[list[AuditEvent]] = relationship("AuditEvent", back_populates="checkout")


class CheckoutItem(Base):
    """Snapshot of a variant + price at checkout creation time."""

    __tablename__ = "checkout_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    checkout_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        nullable=False,
        index=True,
    )
    variant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("product_variants.id"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # snapshot
    created_at: Mapped[datetime] = ts_created()

    checkout: Mapped[CheckoutSession] = relationship("CheckoutSession", back_populates="items")


class PurchaseIntent(Base):
    """
    AP2-inspired bounded authorization — agent declares max spend intent before checkout.
    Policy engine validates purchase against this intent.
    """

    __tablename__ = "purchase_intents"

    intent_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    max_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    allowed_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", index=True
    )  # ACTIVE | CONSUMED | EXPIRED
    created_at: Mapped[datetime] = ts_created()

    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="purchase_intents")
