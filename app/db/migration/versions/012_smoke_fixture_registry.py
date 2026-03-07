"""Add smoke fixture registry for stable production verification.

Revision ID: 012_smoke_fixture_registry
Revises: 011_subscription_instances
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "012_smoke_fixture_registry"
down_revision = "011_subscription_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxycraft_smoke_fixtures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("product", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=64), nullable=True),
        sa.Column(
            "user_tg_id",
            sa.BigInteger(),
            sa.ForeignKey("proxycraft_users.tg_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vpn_subscription_id",
            sa.Integer(),
            sa.ForeignKey("proxycraft_vpn_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "mtproto_subscription_id",
            sa.Integer(),
            sa.ForeignKey("proxycraft_mtproto_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "whatsapp_subscription_id",
            sa.Integer(),
            sa.ForeignKey("proxycraft_whatsapp_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_proxycraft_smoke_fixtures_key"),
    )
    op.create_index(
        "ix_proxycraft_smoke_fixtures_user_tg_id",
        "proxycraft_smoke_fixtures",
        ["user_tg_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_proxycraft_smoke_fixtures_user_tg_id", table_name="proxycraft_smoke_fixtures")
    op.drop_table("proxycraft_smoke_fixtures")
