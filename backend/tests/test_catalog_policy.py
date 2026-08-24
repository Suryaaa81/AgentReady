import pytest
from app.models.merchant import Merchant
from app.services import catalog, policy
from app.schemas.merchant import MerchantPolicyCreate

def test_catalog_import_and_query(db, merchant):
    csv_data = """sku,name,description,category,base_price,currency,variant_sku,variant_attributes,variant_price_override,inventory_available
SHOE-1,Sneaker,A nice shoe,Shoes,1000.00,INR,SHOE-1-M,"{""size"": ""M""}",,10
SHOE-1,Sneaker,A nice shoe,Shoes,1000.00,INR,SHOE-1-L,"{""size"": ""L""}",1100.00,5
HAT-1,Cap,,Hats,200.00,INR,,,,"""
    
    result = catalog.import_catalog_csv(db, merchant.id, csv_data)
    assert len(result.errors) == 0
    assert result.products_created == 2
    assert result.variants_created == 2

    # Query products
    products = catalog.get_products(db, merchant.id)
    assert len(products) == 2
    
    # Search
    search_res = catalog.search_products_query(db, merchant.id, "sneak")
    assert len(search_res) == 1
    assert search_res[0].sku == "SHOE-1"
    assert len(search_res[0].variants) == 2

def test_policy_upsert(db, merchant):
    p = MerchantPolicyCreate(max_autonomous_amount=5000, daily_limit=10000, allowed_categories=["Shoes"])
    res = policy.upsert_policy(db, merchant.id, p)
    assert res.max_autonomous_amount == 5000
    
    p2 = MerchantPolicyCreate(max_autonomous_amount=6000, daily_limit=10000)
    res2 = policy.upsert_policy(db, merchant.id, p2)
    assert res2.id == res.id  # Same policy updated
    assert res2.max_autonomous_amount == 6000
