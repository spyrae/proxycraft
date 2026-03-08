"""Drop unique constraint on user_tg_id for mtproto and whatsapp subscriptions.

Allows multiple subscriptions per user.

Revision ID: 015_drop_unique_user_tg_id
Revises: 014_geo_probe_monitoring
Create Date: 2026-03-08
"""

from alembic import op

revision = "015_drop_unique_user_tg_id"
down_revision = "014_geo_probe_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop unique constraints on user_tg_id (allow multiple subscriptions per user)
    op.execute(
        "ALTER TABLE proxycraft_mtproto_subscriptions "
        "DROP CONSTRAINT IF EXISTS uq_vpncraft_mtproto_subscriptions_user_tg_id"
    )
    op.execute(
        "ALTER TABLE proxycraft_mtproto_subscriptions "
        "DROP CONSTRAINT IF EXISTS proxycraft_mtproto_subscriptions_user_tg_id_key"
    )
    op.execute(
        "ALTER TABLE proxycraft_whatsapp_subscriptions "
        "DROP CONSTRAINT IF EXISTS uq_vpncraft_whatsapp_subscriptions_user_tg_id"
    )
    op.execute(
        "ALTER TABLE proxycraft_whatsapp_subscriptions "
        "DROP CONSTRAINT IF EXISTS proxycraft_whatsapp_subscriptions_user_tg_id_key"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE proxycraft_mtproto_subscriptions "
        "ADD CONSTRAINT uq_vpncraft_mtproto_subscriptions_user_tg_id UNIQUE (user_tg_id)"
    )
    op.execute(
        "ALTER TABLE proxycraft_whatsapp_subscriptions "
        "ADD CONSTRAINT uq_vpncraft_whatsapp_subscriptions_user_tg_id UNIQUE (user_tg_id)"
    )
