from app.schemas.checkout import CheckoutItemCreate, CheckoutSessionCreate, PurchaseIntentCreate
from app.schemas.merchant import MerchantPolicyCreate
from app.services import catalog, checkout, policy_engine


def test_policy_engine_daily_limit_blocks_structuring(db, merchant):
    """An agent should not be able to split one purchase into several
    under-threshold checkouts that together exceed the merchant's daily_limit."""
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,400.00,HAT-M,50"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    from app.models.order import Order
    from app.services.policy import upsert_policy

    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(max_autonomous_amount=1000, daily_limit=500),
    )

    # Simulate a prior COMPLETED order today worth 400 against a 500 daily cap.
    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    prior_checkout = checkout.create_checkout(db, merchant.id, session_create)
    prior_order = Order(
        checkout_id=prior_checkout.id,
        merchant_id=merchant.id,
        status="COMPLETED",
        total_amount=400,
        currency="INR",
    )
    db.add(prior_order)
    db.commit()

    # A second, individually-small (400) checkout would push the day's total
    # to 800 — over the 500 daily_limit — even though it clears the per-order
    # max_autonomous_amount on its own.
    next_checkout = checkout.create_checkout(db, merchant.id, session_create)

    res = policy_engine.evaluate_checkout_policy(db, next_checkout)
    assert res.decision == "REJECT"
    assert "Daily spend limit exceeded" in res.reason


def test_policy_engine_allow(db, merchant):
    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT,Cap,Hats,500.00,HAT-M,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    # Create policy
    from app.services.policy import upsert_policy

    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(
            max_autonomous_amount=1000, daily_limit=10000, allowed_categories=["Hats"]
        ),
    )

    # Checkout 1 hat
    session_create = CheckoutSessionCreate(
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

    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(
            max_autonomous_amount=1000, daily_limit=10000, allowed_categories=["Hats"]
        ),
    )

    session_create = CheckoutSessionCreate(
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

    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(
            max_autonomous_amount=1000, daily_limit=10000, approval_threshold=5000
        ),
    )

    session_create = CheckoutSessionCreate(
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

    upsert_policy(
        db, merchant.id, MerchantPolicyCreate(max_autonomous_amount=1000, daily_limit=10000)
    )

    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)

    intent = checkout.create_intent(
        db, merchant.id, PurchaseIntentCreate(max_amount=400, currency="INR")
    )

    res = policy_engine.evaluate_checkout_policy(db, checkout_session, intent.intent_id)
    assert res.decision == "REJECT"
    assert "Amount exceeds authorized intent" in res.reason
