import pytest

from app.models.catalog import Inventory
from app.schemas.checkout import CheckoutItemCreate, CheckoutSessionCreate
from app.schemas.merchant import MerchantPolicyCreate
from app.services import catalog, checkout

_CSV_HDR = (
    "sku,name,description,category,base_price,currency,"
    "variant_sku,variant_attributes,variant_price_override,inventory_available"
)


def test_checkout_and_inventory_reservation(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-1,Sneaker,,Shoes,1000.00,INR,SHOE-1-M,,1000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)

    products = catalog.get_products(db, merchant.id)
    variant_id = products[0].variants[0].id

    # Create checkout
    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]
    )

    checkout_session = checkout.create_checkout(db, merchant.id, session_create)
    assert checkout_session.status == "READY"
    assert checkout_session.total_amount == 3000.00

    # Verify inventory reserved
    inv = db.execute(db.query(Inventory).filter_by(variant_id=variant_id).statement).scalar_one()
    assert inv.available_qty == 7
    assert inv.reserved_qty == 3

    # Cancel checkout
    checkout.update_checkout_status(db, checkout_session.id, "CANCELLED")

    # Verify inventory released
    db.refresh(inv)
    assert inv.available_qty == 10
    assert inv.reserved_qty == 0


def test_checkout_out_of_stock(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-2,Sneaker,,Shoes,1000.00,INR,SHOE-2-M,,1000.00,2",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    products = catalog.get_products(db, merchant.id)
    variant_id = products[0].variants[0].id

    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]
    )

    with pytest.raises(ValueError, match="Insufficient stock"):
        checkout.create_checkout(db, merchant.id, session_create)


def test_checkout_audit_endpoint_returns_events(client, db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-3,Sneaker,,Shoes,1000.00,INR,SHOE-3-M,,1000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id
    checkout_session = checkout.create_checkout(
        db,
        merchant.id,
        CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=1)]),
    )

    response = client.get(f"/audit/checkout/{checkout_session.id}")

    assert response.status_code == 200
    assert response.json()[0]["event_type"] == "CHECKOUT_CREATED"


def test_merchant_metrics_endpoint(client, db, merchant, auth_headers):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-METRICS,Sneaker,,Shoes,1000.00,INR,SHOE-METRICS-M,,1000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id
    c1 = checkout.create_checkout(
        db,
        merchant.id,
        CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=1)]),
    )
    checkout.update_checkout_status(db, c1.id, "AUTHORIZED")
    checkout.update_checkout_status(db, c1.id, "PAYMENT_PENDING")
    checkout.update_checkout_status(db, c1.id, "COMPLETED")

    res = client.get("/audit/metrics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_checkouts"] >= 1
    assert data["completed_checkouts"] >= 1
    assert data["checkout_success_rate"] > 0
    assert "event_breakdown" in data


def test_checkout_rejects_illegal_transition(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-4,Sneaker,,Shoes,1000.00,INR,SHOE-4-M,,1000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id
    checkout_session = checkout.create_checkout(
        db,
        merchant.id,
        CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=1)]),
    )

    checkout.update_checkout_status(db, checkout_session.id, "CANCELLED")

    with pytest.raises(ValueError, match="Invalid checkout transition"):
        checkout.update_checkout_status(db, checkout_session.id, "AUTHORIZED")


def test_human_approval_continues_to_authorized(client, db, merchant, auth_headers):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-5,Sneaker,,Shoes,2000.00,INR,SHOE-5-M,,2000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    from app.services.policy import upsert_policy

    upsert_policy(
        db,
        merchant.id,
        MerchantPolicyCreate(
            max_autonomous_amount=1000, approval_threshold=3000, daily_limit=10000
        ),
    )
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id
    response = client.post(
        "/checkout/sessions",
        headers=auth_headers,
        json={"items": [{"variant_id": variant_id, "quantity": 1}], "currency": "INR"},
    )
    checkout_id = response.json()["id"]

    authorization = client.post(f"/checkout/sessions/{checkout_id}/authorize")
    assert authorization.json()["status"] == "AUTHORIZATION_REQUIRED"
    approved = client.post(f"/checkout/sessions/{checkout_id}/authorize")
    assert approved.json()["status"] == "AUTHORIZED"


def test_checkout_completion_releases_reserved_inventory(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-6,Sneaker,,Shoes,1000.00,INR,SHOE-6-M,,1000.00,10",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id

    session_create = CheckoutSessionCreate(
        items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]
    )
    checkout_session = checkout.create_checkout(db, merchant.id, session_create)
    checkout.update_checkout_status(db, checkout_session.id, "AUTHORIZED")
    checkout.update_checkout_status(db, checkout_session.id, "PAYMENT_PENDING")
    checkout.update_checkout_status(db, checkout_session.id, "COMPLETED")

    inv = db.execute(db.query(Inventory).filter_by(variant_id=variant_id).statement).scalar_one()
    assert inv.available_qty == 7
    assert inv.reserved_qty == 0


def test_concurrent_checkout_prevents_oversell(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        "SHOE-7,Sneaker,,Shoes,1000.00,INR,SHOE-7-M,,1000.00,5",
    ])
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    variant_id = catalog.get_products(db, merchant.id)[0].variants[0].id

    # First checkout takes 3 of 5
    c1 = checkout.create_checkout(
        db,
        merchant.id,
        CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]),
    )
    assert c1.status == "READY"

    # Second checkout requests 3 of 5 (only 2 left) -> must raise Insufficient stock
    with pytest.raises(ValueError, match="Insufficient stock"):
        checkout.create_checkout(
            db,
            merchant.id,
            CheckoutSessionCreate(items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]),
        )

    inv = db.execute(db.query(Inventory).filter_by(variant_id=variant_id).statement).scalar_one()
    assert inv.available_qty == 2
    assert inv.reserved_qty == 3

