import pytest
import hmac
import hashlib
from app.services import catalog, checkout, payment, policy
from app.schemas.checkout import CheckoutSessionCreate, CheckoutItemCreate
from app.schemas.merchant import MerchantPolicyCreate
from app.config import settings

def test_payment_flow(db, merchant):
    # Setup catalog and policy
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,500.00,HAT-M,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    policy.upsert_policy(db, merchant.id, MerchantPolicyCreate(max_autonomous_amount=1000, daily_limit=10000))

    # 1. Create Checkout
    session_create = CheckoutSessionCreate(merchant_id=merchant.id, items=[CheckoutItemCreate(variant_id=vid, quantity=1)])
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    # 2. Authorize Checkout
    from app.services.policy_engine import evaluate_checkout_policy
    evaluate_checkout_policy(db, checkout_session)
    checkout_session = checkout.update_checkout_status(db, checkout_session.id, "AUTHORIZED")

    # 3. Create Payment Order
    pay = payment.create_payment_order(db, checkout_session.id)
    assert pay.status == "PENDING"
    assert pay.amount == 500.00
    
    db.refresh(checkout_session)
    assert checkout_session.status == "PAYMENT_PENDING"

    # 4. Verify Signature
    rzp_order_id = pay.razorpay_order_id
    rzp_payment_id = "pay_test123"
    
    # Mock signature
    settings.RAZORPAY_KEY_SECRET = "test_secret"
    msg = f"{rzp_order_id}|{rzp_payment_id}".encode("utf-8")
    secret = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
    sig = hmac.new(secret, msg, hashlib.sha256).hexdigest()

    verified_pay = payment.verify_payment_signature(db, rzp_order_id, rzp_payment_id, sig)
    assert verified_pay.status == "COMPLETED"
    
    db.refresh(checkout_session)
    assert checkout_session.status == "COMPLETED"
