"""Add vpn_profile_slug to users for location-scoped VPN profile selection.

Revision ID: 010_vpn_profile_slug
Revises: 009_add_cancelled_at
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "010_vpn_profile_slug"
down_revision = "009_add_cancelled_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proxycraft_users",
        sa.Column("vpn_profile_slug", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proxycraft_users", "vpn_profile_slug")
