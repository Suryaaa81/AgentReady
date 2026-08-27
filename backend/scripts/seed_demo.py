"""
Bootstrap a demo merchant for local development or a fresh deploy.

Before this script existed, the demo only worked because a merchant row
with a hardcoded UUID had been manually inserted into whichever database
happened to be running - undocumented, and broken on any fresh database
(a new Railway/Supabase instance, a fresh `alembic upgrade head`, a judge
running this locally). This script replaces that with a reproducible,
idempotent bootstrap.

Usage (from backend/, with the venv active and DATABASE_URL configured):

    python scripts/seed_demo.py

Safe to re-run: if a merchant with the demo email already exists, its
existing API key is NOT re-printed (keys are never recoverable after
creation - that's by design) and the script just confirms the merchant
and sample catalog are present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.merchant import Merchant  # noqa: E402
from app.services import catalog, merchant  # noqa: E402

DEMO_EMAIL = "demo@agentready.dev"
DEMO_NAME = "AgentReady Demo Store"

SAMPLE_CATALOG_CSV = """sku,name,description,category,base_price,currency,variant_sku,variant_attributes,variant_price_override,inventory_available
RUN-001,Trail Runner Sneaker,Lightweight trail running shoe,Footwear,2499.00,INR,RUN-001-M-8,"{""size"":""8""}",,25
RUN-001,Trail Runner Sneaker,Lightweight trail running shoe,Footwear,2499.00,INR,RUN-001-M-9,"{""size"":""9""}",,15
BAG-002,Everyday Backpack,20L water-resistant daypack,Bags,1899.00,INR,BAG-002-BLK,"{""color"":""black""}",,40
BAG-002,Everyday Backpack,20L water-resistant daypack,Bags,1899.00,INR,BAG-002-NVY,"{""color"":""navy""}",,0
BTL-003,Insulated Water Bottle,750ml stainless steel bottle,Accessories,699.00,INR,BTL-003-1,,,100
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frontend-env",
        type=Path,
        help="Write the newly generated API key to this Vite env file.",
    )
    args = parser.parse_args()

    # Ensure schema exists (useful for a from-scratch SQLite/dev DB; in
    # production Postgres, Alembic migrations remain the source of truth).
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        found = db.execute(
            select(Merchant).where(Merchant.email == DEMO_EMAIL)
        ).scalar_one_or_none()

        if found is not None:
            print(f"Demo merchant already exists: {found.id}")
            print("(API key was only shown once, at creation - re-register with a")
            print(" different email if you've lost it, or query the DB directly)")
            m = found
        else:
            m, api_key = merchant.create_merchant(db, DEMO_NAME, DEMO_EMAIL)
            print(f"Created demo merchant: {m.id}")
            print()
            print("=" * 66)
            print(f"API KEY (save this now, shown once): {api_key}")
            print("=" * 66)
            print()
            print("Put it in frontend/.env as:")
            print(f"  VITE_MERCHANT_API_KEY={api_key}")
            if args.frontend_env is not None:
                args.frontend_env.parent.mkdir(parents=True, exist_ok=True)
                args.frontend_env.write_text(
                    "VITE_API_URL=http://localhost:8000\n"
                    f"VITE_MERCHANT_API_KEY={api_key}\n",
                    encoding="utf-8",
                )
                print(f"Frontend env written: {args.frontend_env}")

        result = catalog.import_catalog_csv(db, m.id, SAMPLE_CATALOG_CSV)
        print(
            f"Sample catalog: {result.products_created} products created, "
            f"{result.variants_created} variants created "
            f"(already-present ones were left untouched)"
        )


if __name__ == "__main__":
    main()
