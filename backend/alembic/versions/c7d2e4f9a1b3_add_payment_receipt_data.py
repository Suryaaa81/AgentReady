"""store verified receipt data with payment

Revision ID: c7d2e4f9a1b3
Revises: f2a1b7c9d4e6
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7d2e4f9a1b3"
down_revision: str | None = "f2a1b7c9d4e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("receipt_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "receipt_data")