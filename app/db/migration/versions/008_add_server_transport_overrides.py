"""Add per-server VPN transport overrides for location-specific profiles.

Revision ID: 008_add_server_transport_overrides
Revises: 007_rename_to_proxycraft
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "008_add_server_transport_overrides"
down_revision = "007_rename_to_proxycraft"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proxycraft_servers",
        sa.Column("subscription_host", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "proxycraft_servers",
        sa.Column("subscription_port", sa.Integer(), nullable=True),
    )
    op.add_column(
        "proxycraft_servers",
        sa.Column("subscription_path", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "proxycraft_servers",
        sa.Column("inbound_remark", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "proxycraft_servers",
        sa.Column("client_flow", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proxycraft_servers", "client_flow")
    op.drop_column("proxycraft_servers", "inbound_remark")
    op.drop_column("proxycraft_servers", "subscription_path")
    op.drop_column("proxycraft_servers", "subscription_port")
    op.drop_column("proxycraft_servers", "subscription_host")
