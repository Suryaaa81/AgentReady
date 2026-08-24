"""
app/models/__init__.py
Re-export all ORM models so Alembic autogenerate can discover them via a single import.
"""
from app.models.audit import AuditEvent
from app.models.catalog import Inventory, Product, ProductVariant
from app.models.checkout import CheckoutItem, CheckoutSession, PurchaseIntent
from app.models.merchant import Merchant, MerchantPolicy
from app.models.order import Order, Payment

__all__ = [
    "Merchant",
    "MerchantPolicy",
    "Product",
    "ProductVariant",
    "Inventory",
    "CheckoutSession",
    "CheckoutItem",
    "PurchaseIntent",
    "Order",
    "Payment",
    "AuditEvent",
]
