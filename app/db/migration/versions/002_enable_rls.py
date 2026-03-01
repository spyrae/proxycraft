"""Enable RLS on all vpncraft tables

Revision ID: 002_enable_rls
Revises: 001_baseline_pg
Create Date: 2026-03-01
"""

from alembic import op

revision = "002_enable_rls"
down_revision = "001_baseline_pg"
branch_labels = None
depends_on = None

TABLES = [
    "vpncraft_servers",
    "vpncraft_users",
    "vpncraft_transactions",
    "vpncraft_promocodes",
    "vpncraft_referrals",
    "vpncraft_referrer_rewards",
    "vpncraft_invites",
    "vpncraft_mtproto_subscriptions",
    "vpncraft_whatsapp_subscriptions",
]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
