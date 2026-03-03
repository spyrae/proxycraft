"""Add balance wallet: balance + auto_renew fields on users, balance_log table.

Revision ID: 006_add_user_balance
Revises: 005_add_subscription_events
Create Date: 2026-03-03
"""

import sqlalchemy as sa
from alembic import op

revision = "006_add_user_balance"
down_revision = "005_add_subscription_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add balance and auto_renew columns to vpncraft_users
    op.add_column(
        "vpncraft_users",
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "vpncraft_users",
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default="true"),
    )

    # Create balance audit log table
    op.create_table(
        "vpncraft_balance_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("payment_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tg_id"],
            ["vpncraft_users.tg_id"],
            name="fk_vpncraft_balance_log_tg_id_vpncraft_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_balance_log"),
    )
    op.create_index(
        "ix_balance_log_tg_id",
        "vpncraft_balance_log",
        ["tg_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_balance_log_tg_id", table_name="vpncraft_balance_log")
    op.drop_table("vpncraft_balance_log")
    op.drop_column("vpncraft_users", "auto_renew")
    op.drop_column("vpncraft_users", "balance")
