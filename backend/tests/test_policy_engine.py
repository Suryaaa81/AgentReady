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


def test_policy_engine_rejects_cross_merchant_intent(db, merchant):
    from app.services import merchant as merchant_service
    from app.services.policy import upsert_policy

    csv = """sku,name,category,base_price,variant_sku,inventory_available
HAT-2,Cap,Hats,500.00,HAT-2-M,10"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id
    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(max_autonomous_amount=1000, daily_limit=10000),
    )
    checkout_session = checkout.create_checkout(
        db,
        merchant.id,
        CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=1)]),
    )

    other_merchant, _ = merchant_service.create_merchant(db, "Other Shop", "other@example.com")
    intent = checkout.create_intent(
        db, other_merchant.id, PurchaseIntentCreate(max_amount=1000, currency="INR")
    )

    result = policy_engine.evaluate_checkout_policy(db, checkout_session, intent.intent_id)

    assert result.decision == "REJECT"
    assert "another merchant" in result.reason


def test_policy_engine_daily_limit_accounts_for_in_flight_authorizations(db, merchant):
    """If an earlier checkout is AUTHORIZED or in PAYMENT_PENDING today, its amount
    must be counted toward the daily_limit so subsequent concurrent checkouts cannot
    bypass the daily limit before the first payment completes."""
    csv = """sku,name,category,base_price,variant_sku,inventory_available
SHIRT,Shirt,Shirts,400.00,SHIRT-M,50"""
    catalog.import_catalog_csv(db, merchant.id, csv)
    prods = catalog.get_products(db, merchant.id)
    vid = prods[0].variants[0].id

    from app.services.policy import upsert_policy

    # 500 daily limit, 1000 max autonomous per checkout
    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(max_autonomous_amount=1000, daily_limit=500),
    )

    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=vid, quantity=1)]
    )

    # Session 1 is created and AUTHORIZED (400 INR)
    checkout_1 = checkout.create_checkout(db, merchant.id, session_create)
    res_1 = policy_engine.evaluate_checkout_policy(db, checkout_1)
    assert res_1.decision == "ALLOW"
    checkout.update_checkout_status(db, checkout_1.id, "AUTHORIZED")

    # Session 2 is created concurrently (400 INR) while Session 1 is still
    # AUTHORIZED (not yet completed payment)
    checkout_2 = checkout.create_checkout(db, merchant.id, session_create)
    res_2 = policy_engine.evaluate_checkout_policy(db, checkout_2)

    # Session 2 must be REJECTED because in-flight active authorization (400) +
    # Session 2 (400) = 800 > 500
    assert res_2.decision == "REJECT"
    assert "Daily spend limit exceeded" in res_2.reason

