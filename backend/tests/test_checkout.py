import pytest
from app.services import catalog, checkout
from app.schemas.checkout import CheckoutSessionCreate, CheckoutItemCreate
from app.models.catalog import Inventory

def test_checkout_and_inventory_reservation(db, merchant):
    csv_data = """sku,name,description,category,base_price,currency,variant_sku,variant_attributes,variant_price_override,inventory_available
SHOE-1,Sneaker,,Shoes,1000.00,INR,SHOE-1-M,,1000.00,10"""
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    
    products = catalog.get_products(db, merchant.id)
    variant_id = products[0].variants[0].id

    # Create checkout
    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
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
    csv_data = """sku,name,description,category,base_price,currency,variant_sku,variant_attributes,variant_price_override,inventory_available
SHOE-2,Sneaker,,Shoes,1000.00,INR,SHOE-2-M,,1000.00,2"""
    catalog.import_catalog_csv(db, merchant.id, csv_data)
    products = catalog.get_products(db, merchant.id)
    variant_id = products[0].variants[0].id

    session_create = CheckoutSessionCreate(
        merchant_id=merchant.id,
        items=[CheckoutItemCreate(variant_id=variant_id, quantity=3)]
    )
    
    with pytest.raises(ValueError, match="Insufficient stock"):
        checkout.create_checkout(db, merchant.id, session_create)
