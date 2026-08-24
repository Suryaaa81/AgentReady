from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models._base import new_uuid, ts_created, ts_updated

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("merchant_id", "sku", name="uq_product_merchant_sku"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("merchants.id"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    base_price: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = ts_created()
    updated_at: Mapped[datetime] = ts_updated()

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    product_id: Mapped[str] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # {"size": "M", "color": "red"}
    price_override: Mapped[Optional[Numeric]] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = ts_created()

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
    inventory: Mapped[Optional["Inventory"]] = relationship(
        "Inventory", back_populates="variant", uselist=False
    )


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    variant_id: Mapped[str] = mapped_column(
        String(36),
        __import__("sqlalchemy").ForeignKey("product_variants.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    available_qty: Mapped[int] = mapped_column(nullable=False, default=0)
    reserved_qty: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = ts_updated()

    variant: Mapped["ProductVariant"] = relationship("ProductVariant", back_populates="inventory")
