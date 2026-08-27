import pytest

from app.models.catalog import Inventory
from app.schemas.checkout import CheckoutItemCreate, CheckoutSessionCreate
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
