"""Merchant API-key authentication.

Every merchant gets one API key, issued once at registration (`POST
/merchant/register`) and never stored or shown again — only its SHA-256
hash is persisted, on `merchants.api_key_hash`. Callers authenticate by
sending it in the `X-API-Key` header.

Why this exists: before this module, every route accepted a plain
`merchant_id` string as a query/body parameter and trusted it outright —
any caller could act as any merchant just by naming their ID. This
dependency makes `merchant_id` something the *server* derives from a
verified credential, not something the client asserts.
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.merchant import Merchant

API_KEY_PREFIX = "ar_live_"


def generate_api_key() -> str:
    """Generate a new, high-entropy API key. Shown to the merchant exactly once."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """One-way hash of an API key for storage/lookup. Never store the raw key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_current_merchant(
    x_api_key: str = Header(..., alias="X-API-Key", description="Merchant API key"),
    db: Session = Depends(get_db),
) -> Merchant:
    """FastAPI dependency: resolve and return the authenticated Merchant.

    Raises 401 if the header is missing or doesn't match any merchant.
    Use `Depends(get_current_merchant)` on any route that mutates or reads
    merchant-scoped data — never trust a client-supplied merchant_id instead.
    """
    key_hash = hash_api_key(x_api_key)
    merchant = db.execute(
        select(Merchant).where(Merchant.api_key_hash == key_hash)
    ).scalar_one_or_none()
    if merchant is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return merchant
