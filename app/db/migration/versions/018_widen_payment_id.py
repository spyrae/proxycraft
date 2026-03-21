"""Widen payment_id column to VARCHAR(255).

Telegram Stars payment IDs can exceed 64 characters (up to ~140),
causing StringDataRightTruncationError on topup.

Revision ID: 018_widen_payment_id
Revises: 017_add_awg_peers
Create Date: 2026-03-21
"""

from alembic import op

revision = "018_widen_payment_id"
down_revision = "017_add_awg_peers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE proxycraft_transactions ALTER COLUMN payment_id TYPE VARCHAR(255)")
    op.execute("ALTER TABLE proxycraft_balance_log ALTER COLUMN payment_id TYPE VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE proxycraft_transactions ALTER COLUMN payment_id TYPE VARCHAR(64)")
    op.execute("ALTER TABLE proxycraft_balance_log ALTER COLUMN payment_id TYPE VARCHAR(64)")
