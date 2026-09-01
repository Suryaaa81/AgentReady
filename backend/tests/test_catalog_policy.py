from app.schemas.merchant import MerchantPolicyCreate
from app.services import catalog, policy

_CSV_HDR = (
    "sku,name,description,category,base_price,currency,"
    "variant_sku,variant_attributes,variant_price_override,inventory_available"
)


def test_catalog_import_and_query(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        'SHOE-1,Sneaker,A nice shoe,Shoes,1000.00,INR,SHOE-1-M,"{""size"": ""M""}",,10',
        'SHOE-1,Sneaker,A nice shoe,Shoes,1000.00,INR,SHOE-1-L,"{""size"": ""L""}",1100.00,5',
        "HAT-1,Cap,,Hats,200.00,INR,,,,",
    ])

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
    p = MerchantPolicyCreate(
        max_autonomous_amount=5000, daily_limit=10000, allowed_categories=["Shoes"]
    )
    res = policy.upsert_policy(db, merchant.id, p)
    assert res.max_autonomous_amount == 5000

    p2 = MerchantPolicyCreate(max_autonomous_amount=6000, daily_limit=10000)
    res2 = policy.upsert_policy(db, merchant.id, p2)
    assert res2.id == res.id  # Same policy updated
    assert res2.max_autonomous_amount == 6000


def test_catalog_import_validation_rejects_negative_and_malformed(db, merchant):
    csv_data = "\n".join([
        _CSV_HDR,
        # Row 1: negative base price
        'BAD-1,Bad Price,,Shoes,-100.00,INR,BAD-1-M,,50.00,10',
        # Row 2: negative variant price override
        'BAD-2,Bad Override,,Shoes,100.00,INR,BAD-2-M,,-50.00,10',
        # Row 3: negative inventory
        'BAD-3,Bad Stock,,Shoes,100.00,INR,BAD-3-M,,50.00,-5',
        # Row 4: missing SKU
        ',No SKU,,Shoes,100.00,INR,BAD-4-M,,50.00,5',
        # Row 5: invalid JSON attributes
        'BAD-5,Bad JSON,,Shoes,100.00,INR,BAD-5-M,"invalid-json",50.00,5',
    ])

    result = catalog.import_catalog_csv(db, merchant.id, csv_data)
    assert len(result.errors) == 5
    assert any("base_price cannot be negative" in err for err in result.errors)
    assert any("variant_price_override cannot be negative" in err for err in result.errors)
    assert any("inventory_available cannot be negative" in err for err in result.errors)
    assert any("Missing product sku" in err for err in result.errors)
    assert any("Invalid JSON in variant_attributes" in err for err in result.errors)

