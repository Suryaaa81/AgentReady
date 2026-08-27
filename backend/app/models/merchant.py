from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created, ts_updated

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.catalog import Product
    from app.models.checkout import CheckoutSession, PurchaseIntent
    from app.models.order import Order


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    api_key_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    # Relationships
    policies: Mapped[list[MerchantPolicy]] = relationship(
        "MerchantPolicy", back_populates="merchant", cascade="all, delete-orphan"
    )
    products: Mapped[list[Product]] = relationship("Product", back_populates="merchant")
    checkout_sessions: Mapped[list[CheckoutSession]] = relationship(
        "CheckoutSession", back_populates="merchant"
    )
    purchase_intents: Mapped[list[PurchaseIntent]] = relationship(
        "PurchaseIntent", back_populates="merchant"
    )
    orders: Mapped[list[Order]] = relationship("Order", back_populates="merchant")
    audit_events: Mapped[list[AuditEvent]] = relationship("AuditEvent", back_populates="merchant")


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    max_autonomous_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    daily_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    allowed_categories: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    max_delivery_days: Mapped[int | None] = mapped_column(nullable=True)
    min_return_days: Mapped[int | None] = mapped_column(nullable=True)
    approval_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    merchant: Mapped[Merchant] = relationship("Merchant", back_populates="policies")
