from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created, ts_updated

if TYPE_CHECKING:
    from app.models.catalog import Product
    from app.models.checkout import CheckoutSession, PurchaseIntent
    from app.models.audit import AuditEvent
    from app.models.order import Order


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    # Relationships
    policies: Mapped[list["MerchantPolicy"]] = relationship(
        "MerchantPolicy", back_populates="merchant", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship("Product", back_populates="merchant")
    checkout_sessions: Mapped[list["CheckoutSession"]] = relationship(
        "CheckoutSession", back_populates="merchant"
    )
    purchase_intents: Mapped[list["PurchaseIntent"]] = relationship(
        "PurchaseIntent", back_populates="merchant"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="merchant")
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="merchant"
    )


class MerchantPolicy(Base):
    __tablename__ = "merchant_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    max_autonomous_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    daily_limit: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    allowed_categories: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    max_delivery_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    min_return_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    approval_threshold: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        __import__("sqlalchemy").DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="policies")
