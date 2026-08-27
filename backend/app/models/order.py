from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created, ts_updated

if TYPE_CHECKING:
    from app.models.checkout import CheckoutSession
    from app.models.merchant import Merchant


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    checkout_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("checkout_sessions.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="PENDING", index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    checkout: Mapped[CheckoutSession] = relationship("CheckoutSession", back_populates="order")
    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="orders")
    payment: Mapped[Payment | None] = relationship("Payment", back_populates="order", uselist=False)


class Payment(Base):
    """
    Server-authoritative payment record.
    razorpay_payment_id is null until Razorpay captures the payment.
    verified_at is set ONLY after server-side HMAC signature verification.
    """

    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", index=True
    )  # PENDING | CAPTURED | FAILED | REFUNDED
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    receipt_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    order: Mapped[Order] = relationship("Order", back_populates="payment")
