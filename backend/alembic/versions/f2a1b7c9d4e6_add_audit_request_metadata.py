"""add audit request metadata

Revision ID: f2a1b7c9d4e6
Revises: eebf04727465
Create Date: 2026-08-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a1b7c9d4e6"
down_revision: str | None = "eebf04727465"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("audit_events", sa.Column("user_agent", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_events", "user_agent")
    op.drop_column("audit_events", "ip_address")