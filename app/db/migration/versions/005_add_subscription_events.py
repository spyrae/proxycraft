"""Add subscription_events table for notification chain deduplication.

Revision ID: 005_add_subscription_events
Revises: 004_multi_use_promocodes
Create Date: 2026-03-03
"""

import sqlalchemy as sa
from alembic import op

revision = "005_add_subscription_events"
down_revision = "004_multi_use_promocodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vpncraft_subscription_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("expiry_time", sa.BigInteger(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_subscription_events"),
        sa.UniqueConstraint("tg_id", "expiry_time", "stage", name="uq_subscription_event_cycle"),
    )
    op.create_index(
        "ix_subscription_events_tg_id",
        "vpncraft_subscription_events",
        ["tg_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_events_tg_id", table_name="vpncraft_subscription_events")
    op.drop_table("vpncraft_subscription_events")
