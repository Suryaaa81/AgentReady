import pytest
from app.services import catalog, checkout, policy_engine
from app.schemas.checkout import CheckoutSessionCreate, CheckoutItemCreate, PurchaseIntentCreate
from app.schemas.merchant import MerchantPolicyCreate

def test_policy_engine_allow(db, merchant):
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,500.00,HAT-M,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    # Create policy
    from app.services.policy import upsert_policy
    upsert_policy(db, merchant.id, MerchantPolicyCreate(
        max_autonomous_amount=1000, daily_limit=10000, allowed_categories=["Hats"]
    ))

    # Checkout 1 hat
    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    res = policy_engine.evaluate_checkout_policy(db, checkout_session)
    assert res.decision == "ALLOW"


def test_policy_engine_reject_category(db, merchant):
    csv = """sku,name,category,base_price,variant_sku,inventory_available
SHOES,Shoes,Shoes,500.00,SHOES-M,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    from app.services.policy import upsert_policy
    upsert_policy(db, merchant.id, MerchantPolicyCreate(
        max_autonomous_amount=1000, daily_limit=10000, allowed_categories=["Hats"]
    ))

    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    res = policy_engine.evaluate_checkout_policy(db, checkout_session)
    assert res.decision == "REJECT"
    assert "Category 'Shoes' not allowed" in res.reason


def test_policy_engine_approval(db, merchant):
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,2000.00,HAT-L,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    from app.services.policy import upsert_policy
    upsert_policy(db, merchant.id, MerchantPolicyCreate(
        max_autonomous_amount=1000, daily_limit=10000, approval_threshold=5000
    ))

    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    res = policy_engine.evaluate_checkout_policy(db, checkout_session)
    assert res.decision == "REQUIRE_HUMAN_APPROVAL"

def test_policy_engine_intent(db, merchant):
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,500.00,HAT-S,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    from app.services.policy import upsert_policy
    upsert_policy(db, merchant.id, MerchantPolicyCreate(
        max_autonomous_amount=1000, daily_limit=10000
    ))

    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    intent = checkout.create_intent(db, merchant.id, PurchaseIntentCreate(max_amount=400, currency="INR"))
    
    res = policy_engine.evaluate_checkout_policy(db, checkout_session, intent.intent_id)
    assert res.decision == "REJECT"
    assert "Amount exceeds authorized intent" in res.reason
