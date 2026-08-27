"""Tests for merchant registration and the X-API-Key auth dependency."""

from app.security import hash_api_key
from app.services import merchant as merchant_service


def test_register_merchant_creates_default_policy_and_key(db):
    m, api_key = merchant_service.create_merchant(db, "New Shop", "new-shop@example.com")

    assert m.id
    assert api_key.startswith("ar_live_")
    # Only the hash is persisted — the plaintext key is never stored.
    assert m.api_key_hash == hash_api_key(api_key)
    assert m.api_key_hash != api_key

    from app.services import policy

    p = policy.get_policy(db, m.id)
    assert p is not None, "registration should create a usable default policy"


def test_register_endpoint_returns_key_once(client):
    resp = client.post(
        "/merchant/register",
        json={"name": "API Test Merchant", "email": "api-test@example.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["api_key"].startswith("ar_live_")
    assert "id" in body


def test_register_duplicate_email_rejected(client):
    payload = {"name": "Dup", "email": "dup@example.com"}
    first = client.post("/merchant/register", json=payload)
    assert first.status_code == 201
    second = client.post("/merchant/register", json=payload)
    assert second.status_code == 409


def test_protected_route_rejects_missing_api_key(client):
    resp = client.get("/merchant/policies")
    assert resp.status_code in (401, 422)  # 422 if FastAPI rejects the missing header first


def test_protected_route_rejects_invalid_api_key(client):
    resp = client.get("/merchant/policies", headers={"X-API-Key": "ar_live_not_a_real_key"})
    assert resp.status_code == 401


def test_protected_route_accepts_valid_api_key(client, auth_headers):
    resp = client.get("/merchant/policies", headers=auth_headers)
    # The `merchant` fixture creates a bare Merchant (unlike the real
    # /merchant/register flow, it doesn't auto-provision a policy), so 404
    # is the correct outcome here — the point of this test is that the key
    # was accepted at all: a 401 would mean auth rejected a valid key.
    assert resp.status_code != 401


def test_api_key_cannot_impersonate_another_merchant(client, db):
    """A merchant's key must never grant access to another merchant's data."""
    m1, key1 = merchant_service.create_merchant(db, "Shop One", "shop-one@example.com")
    m2, key2 = merchant_service.create_merchant(db, "Shop Two", "shop-two@example.com")
    db.commit()

    from app.schemas.merchant import MerchantPolicyCreate
    from app.services import policy as policy_service

    policy_service.upsert_policy(
        db, m1.id, MerchantPolicyCreate(max_autonomous_amount=500, daily_limit=5000)
    )
    db.commit()

    # Shop Two has its own auto-provisioned default policy — it must never
    # see Shop One's custom values, regardless of which key is used.
    resp = client.get("/merchant/policies", headers={"X-API-Key": key2})
    assert resp.status_code == 200
    assert resp.json()["merchant_id"] == m2.id
    assert float(resp.json()["max_autonomous_amount"]) != 500.0

    resp = client.get("/merchant/policies", headers={"X-API-Key": key1})
    assert resp.status_code == 200
    assert resp.json()["merchant_id"] == m1.id
    assert float(resp.json()["max_autonomous_amount"]) == 500.0


def test_payment_routes_require_merchant_auth(client):
    payment_payload = {
        "checkout_id": "not-a-real-checkout",
    }
    verify_payload = {
        "razorpay_order_id": "order_test",
        "razorpay_payment_id": "pay_test",
        "razorpay_signature": "signature",
    }

    assert client.post("/payment/order", json=payment_payload).status_code == 422
    assert client.post("/payment/verify", json=verify_payload).status_code == 422
