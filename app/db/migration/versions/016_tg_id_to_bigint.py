"""Widen all tg_id columns from INTEGER to BIGINT.

New Telegram accounts have IDs exceeding int32 range (>2^31),
causing 'value out of int32 range' errors on login.

Revision ID: 016_tg_id_to_bigint
Revises: 015_drop_unique_user_tg_id
Create Date: 2026-03-18
"""

from alembic import op

revision = "016_tg_id_to_bigint"
down_revision = "015_drop_unique_user_tg_id"
branch_labels = None
depends_on = None

# (table, column) pairs that store Telegram user IDs
TG_ID_COLUMNS = [
    ("proxycraft_users", "tg_id"),
    ("proxycraft_referrals", "referred_tg_id"),
    ("proxycraft_referrals", "referrer_tg_id"),
    ("proxycraft_activated_promocodes", "user_tg_id"),
    ("proxycraft_vpn_subscriptions", "user_tg_id"),
    ("proxycraft_smoke_fixtures", "user_tg_id"),
    ("proxycraft_balance_log", "tg_id"),
    ("proxycraft_transactions", "tg_id"),
    ("proxycraft_whatsapp_subscriptions", "user_tg_id"),
    ("proxycraft_mtproto_subscriptions", "user_tg_id"),
    ("proxycraft_referrer_rewards", "user_tg_id"),
]


def upgrade() -> None:
    for table, column in TG_ID_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT")


def downgrade() -> None:
    for table, column in TG_ID_COLUMNS:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE INTEGER")
