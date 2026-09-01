import csv
import io
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import Inventory, Product, ProductVariant
from app.schemas.catalog import CatalogImportResult


def get_products(db: Session, merchant_id: str, limit: int = 100) -> list[Product]:
    return list(
        db.execute(select(Product).where(Product.merchant_id == merchant_id).limit(limit))
        .scalars()
        .all()
    )


def search_products_query(
    db: Session, merchant_id: str, query: str, limit: int = 10
) -> list[Product]:
    return list(
        db.execute(
            select(Product)
            .where(Product.merchant_id == merchant_id)
            .where(Product.name.ilike(f"%{query}%"))
            .limit(limit)
        )
        .scalars()
        .all()
    )


def import_catalog_csv(db: Session, merchant_id: str, csv_content: str) -> CatalogImportResult:
    """
    Imports catalog from a CSV string.
    Expected headers: sku, name, description, category, base_price, currency,
    variant_sku, variant_attributes, variant_price_override, inventory_available
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    result = CatalogImportResult(
        products_created=0, products_updated=0, variants_created=0, variants_updated=0, errors=[]
    )

    for row_idx, row in enumerate(reader):
        try:
            sku = row.get("sku")
            if not sku:
                result.errors.append(f"Row {row_idx + 1}: Missing product sku")
                continue

            base_price = Decimal(row.get("base_price", "0"))
            if base_price < 0:
                result.errors.append(f"Row {row_idx + 1}: base_price cannot be negative")
                continue

            # Product upsert
            product = db.execute(
                select(Product).where(Product.merchant_id == merchant_id, Product.sku == sku)
            ).scalar_one_or_none()
            if not product:
                product = Product(
                    merchant_id=merchant_id,
                    sku=sku,
                    name=row.get("name", "Unnamed Product"),
                    description=row.get("description"),
                    category=row.get("category"),
                    base_price=base_price,
                    currency=row.get("currency", "INR"),
                    is_active=True,
                )
                db.add(product)
                db.flush()
                result.products_created += 1
            else:
                product.name = row.get("name") or product.name
                product.description = row.get("description") or product.description
                if row.get("base_price"):
                    product.base_price = base_price
                result.products_updated += 1
                db.flush()

            variant_sku = row.get("variant_sku")
            if variant_sku:
                # Variant upsert
                variant = db.execute(
                    select(ProductVariant).where(ProductVariant.sku == variant_sku)
                ).scalar_one_or_none()

                attrs = None
                if row.get("variant_attributes"):
                    try:
                        attrs = json.loads(row["variant_attributes"])
                    except json.JSONDecodeError:
                        result.errors.append(
                            f"Row {row_idx + 1}: Invalid JSON in variant_attributes"
                        )

                override_price = None
                if row.get("variant_price_override"):
                    override_price = Decimal(row["variant_price_override"])
                    if override_price < 0:
                        result.errors.append(
                            f"Row {row_idx + 1}: variant_price_override cannot be negative"
                        )
                        continue

                inv_qty = int(row.get("inventory_available") or "0")
                if inv_qty < 0:
                    result.errors.append(
                        f"Row {row_idx + 1}: inventory_available cannot be negative"
                    )
                    continue

                if not variant:
                    variant = ProductVariant(
                        product_id=product.id,
                        sku=variant_sku,
                        attributes=attrs,
                        price_override=override_price,
                    )
                    db.add(variant)
                    db.flush()
                    result.variants_created += 1

                    # Create inventory
                    inventory = Inventory(
                        variant_id=variant.id,
                        available_qty=inv_qty,
                        reserved_qty=0,
                    )
                    db.add(inventory)
                else:
                    variant.attributes = attrs or variant.attributes
                    if override_price is not None:
                        variant.price_override = override_price
                    result.variants_updated += 1

                    # Update inventory
                    existing_inventory = db.execute(
                        select(Inventory).where(Inventory.variant_id == variant.id)
                    ).scalar_one_or_none()
                    if existing_inventory and row.get("inventory_available") is not None:
                        existing_inventory.available_qty = inv_qty
                db.flush()

        except Exception as e:
            result.errors.append(f"Row {row_idx + 1}: {str(e)}")

    db.commit()
    return result
