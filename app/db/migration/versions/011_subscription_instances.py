"""Introduce VPN subscription instances and allow multiple MTProto/WhatsApp subscriptions.

Revision ID: 011_subscription_instances
Revises: 010_vpn_profile_slug
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "011_subscription_instances"
down_revision = "010_vpn_profile_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxycraft_vpn_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_tg_id",
            sa.BigInteger(),
            sa.ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vpn_id", sa.String(length=36), nullable=False),
        sa.Column("client_email", sa.String(length=128), nullable=False),
        sa.Column(
            "server_id",
            sa.Integer(),
            sa.ForeignKey("proxycraft_servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("devices", sa.Integer(), nullable=True),
        sa.Column("vpn_profile_slug", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("vpn_id", name="uq_proxycraft_vpn_subscriptions_vpn_id"),
        sa.UniqueConstraint("client_email", name="uq_proxycraft_vpn_subscriptions_client_email"),
    )
    op.create_index(
        "ix_proxycraft_vpn_subscriptions_user_tg_id",
        "proxycraft_vpn_subscriptions",
        ["user_tg_id"],
    )

    op.execute(
        """
        INSERT INTO proxycraft_vpn_subscriptions (
            user_tg_id,
            vpn_id,
            client_email,
            server_id,
            devices,
            vpn_profile_slug,
            created_at,
            cancelled_at
        )
        SELECT
            tg_id,
            vpn_id,
            tg_id::text,
            server_id,
            NULL,
            vpn_profile_slug,
            created_at,
            vpn_cancelled_at
        FROM proxycraft_users
        WHERE server_id IS NOT NULL
        """
    )

    op.execute(
        "ALTER TABLE proxycraft_mtproto_subscriptions DROP CONSTRAINT IF EXISTS uq_vpncraft_mtproto_subscriptions_user_tg_id"
    )
    op.execute(
        "ALTER TABLE proxycraft_whatsapp_subscriptions DROP CONSTRAINT IF EXISTS uq_vpncraft_whatsapp_subscriptions_user_tg_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE proxycraft_mtproto_subscriptions ADD CONSTRAINT uq_vpncraft_mtproto_subscriptions_user_tg_id UNIQUE (user_tg_id)"
    )
    op.execute(
        "ALTER TABLE proxycraft_whatsapp_subscriptions ADD CONSTRAINT uq_vpncraft_whatsapp_subscriptions_user_tg_id UNIQUE (user_tg_id)"
    )

    op.drop_index("ix_proxycraft_vpn_subscriptions_user_tg_id", table_name="proxycraft_vpn_subscriptions")
    op.drop_table("proxycraft_vpn_subscriptions")
