"""Add operator column to vpncraft_users.

Revision ID: 003_add_operator
Revises: 002_enable_rls
Create Date: 2026-03-01
"""

import sqlalchemy as sa
from alembic import op

revision = "003_add_operator"
down_revision = "002_enable_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpncraft_users",
        sa.Column("operator", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vpncraft_users", "operator")
