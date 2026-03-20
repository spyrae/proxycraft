"""Add AmneziaWG peers table.

Stores WireGuard peer keys and assigned IPs for AmneziaWG VPN,
linked 1:1 to VPN subscriptions.

Revision ID: 017_add_awg_peers
Revises: 016_tg_id_to_bigint
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

revision = "017_add_awg_peers"
down_revision = "016_tg_id_to_bigint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxycraft_awg_peers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "vpn_subscription_id",
            sa.Integer,
            sa.ForeignKey("proxycraft_vpn_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("private_key", sa.Text, nullable=False),
        sa.Column("public_key", sa.String(64), nullable=False),
        sa.Column("preshared_key", sa.Text, nullable=False),
        sa.Column("assigned_ip", sa.String(18), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_proxycraft_awg_peers_vpn_subscription_id",
        "proxycraft_awg_peers",
        ["vpn_subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_proxycraft_awg_peers_vpn_subscription_id", table_name="proxycraft_awg_peers")
    op.drop_table("proxycraft_awg_peers")
