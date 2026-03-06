"""Add cancelled_at to MTProto/WhatsApp subscriptions and vpn_cancelled_at to users.

Revision ID: 009_add_cancelled_at
Revises: 008_server_overrides
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "009_add_cancelled_at"
down_revision = "008_server_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proxycraft_users",
        sa.Column("vpn_cancelled_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "proxycraft_mtproto_subscriptions",
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "proxycraft_whatsapp_subscriptions",
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proxycraft_whatsapp_subscriptions", "cancelled_at")
    op.drop_column("proxycraft_mtproto_subscriptions", "cancelled_at")
    op.drop_column("proxycraft_users", "vpn_cancelled_at")
