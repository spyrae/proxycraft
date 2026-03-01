"""Baseline PostgreSQL migration — all 9 vpncraft_ tables

Revision ID: 001_baseline_pg
Revises:
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa

revision = "001_baseline_pg"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ENUM types ---
    vpncraft_transactionstatus = sa.Enum(
        "pending", "completed", "canceled", "refunded",
        name="vpncraft_transactionstatus",
    )
    vpncraft_referrerrewardtype = sa.Enum(
        "days", "money",
        name="vpncraft_referrerrewardtype",
    )
    vpncraft_referrerrewardlevel = sa.Enum(
        "FIRST_LEVEL", "SECOND_LEVEL",
        name="vpncraft_referrerrewardlevel",
    )

    # --- 1. vpncraft_servers ---
    op.create_table(
        "vpncraft_servers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("max_clients", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(32), nullable=True),
        sa.Column("online", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_servers"),
        sa.UniqueConstraint("name", name="uq_vpncraft_servers_name"),
    )

    # --- 2. vpncraft_users ---
    op.create_table(
        "vpncraft_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("vpn_id", sa.String(36), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=True),
        sa.Column("first_name", sa.String(32), nullable=False),
        sa.Column("username", sa.String(32), nullable=True),
        sa.Column("language_code", sa.String(5), nullable=False, server_default="en"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("is_trial_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_invite_name", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_users"),
        sa.UniqueConstraint("tg_id", name="uq_vpncraft_users_tg_id"),
        sa.UniqueConstraint("vpn_id", name="uq_vpncraft_users_vpn_id"),
        sa.ForeignKeyConstraint(
            ["server_id"], ["vpncraft_servers.id"],
            name="fk_vpncraft_users_server_id_vpncraft_servers",
            ondelete="SET NULL",
        ),
    )

    # --- 3. vpncraft_transactions ---
    op.create_table(
        "vpncraft_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.String(64), nullable=False),
        sa.Column("subscription", sa.String(255), nullable=False),
        sa.Column("status", vpncraft_transactionstatus, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_transactions"),
        sa.UniqueConstraint("payment_id", name="uq_vpncraft_transactions_payment_id"),
        sa.ForeignKeyConstraint(
            ["tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_transactions_tg_id_vpncraft_users",
        ),
    )

    # --- 4. vpncraft_promocodes ---
    op.create_table(
        "vpncraft_promocodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("is_activated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("activated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_promocodes"),
        sa.UniqueConstraint("code", name="uq_vpncraft_promocodes_code"),
        sa.ForeignKeyConstraint(
            ["activated_by"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_promocodes_activated_by_vpncraft_users",
        ),
    )

    # --- 5. vpncraft_referrals ---
    op.create_table(
        "vpncraft_referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referred_tg_id", sa.Integer(), nullable=False),
        sa.Column("referrer_tg_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("referred_rewarded_at", sa.DateTime(), nullable=True),
        sa.Column("referred_bonus_days", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_referrals"),
        sa.UniqueConstraint("referred_tg_id", name="uq_vpncraft_referrals_referred_tg_id"),
        sa.ForeignKeyConstraint(
            ["referred_tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_referrals_referred_tg_id_vpncraft_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["referrer_tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_referrals_referrer_tg_id_vpncraft_users",
            ondelete="CASCADE",
        ),
    )

    # --- 6. vpncraft_referrer_rewards ---
    op.create_table(
        "vpncraft_referrer_rewards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_tg_id", sa.Integer(), nullable=False),
        sa.Column("reward_type", vpncraft_referrerrewardtype, nullable=False),
        sa.Column("reward_level", vpncraft_referrerrewardlevel, nullable=True),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("rewarded_at", sa.DateTime(), nullable=True),
        sa.Column("payment_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_referrer_rewards"),
        sa.UniqueConstraint("user_tg_id", "payment_id", name="vpncraft_uq_user_payment"),
        sa.ForeignKeyConstraint(
            ["user_tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_referrer_rewards_user_tg_id_vpncraft_users",
            ondelete="CASCADE",
        ),
    )

    # --- 7. vpncraft_invites ---
    op.create_table(
        "vpncraft_invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hash_code", sa.String(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_invites"),
        sa.UniqueConstraint("name", name="uq_vpncraft_invites_name"),
        sa.UniqueConstraint("hash_code", name="uq_vpncraft_invites_hash_code"),
    )

    # --- 8. vpncraft_mtproto_subscriptions ---
    op.create_table(
        "vpncraft_mtproto_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_tg_id", sa.Integer(), nullable=False),
        sa.Column("secret", sa.String(32), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_trial_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_mtproto_subscriptions"),
        sa.UniqueConstraint("user_tg_id", name="uq_vpncraft_mtproto_subscriptions_user_tg_id"),
        sa.UniqueConstraint("secret", name="uq_vpncraft_mtproto_subscriptions_secret"),
        sa.ForeignKeyConstraint(
            ["user_tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_mtproto_subscriptions_user_tg_id_vpncraft_users",
            ondelete="CASCADE",
        ),
    )

    # --- 9. vpncraft_whatsapp_subscriptions ---
    op.create_table(
        "vpncraft_whatsapp_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_tg_id", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_trial_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_whatsapp_subscriptions"),
        sa.UniqueConstraint("user_tg_id", name="uq_vpncraft_whatsapp_subscriptions_user_tg_id"),
        sa.UniqueConstraint("port", name="uq_vpncraft_whatsapp_subscriptions_port"),
        sa.ForeignKeyConstraint(
            ["user_tg_id"], ["vpncraft_users.tg_id"],
            name="fk_vpncraft_whatsapp_subscriptions_user_tg_id_vpncraft_users",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("vpncraft_whatsapp_subscriptions")
    op.drop_table("vpncraft_mtproto_subscriptions")
    op.drop_table("vpncraft_invites")
    op.drop_table("vpncraft_referrer_rewards")
    op.drop_table("vpncraft_referrals")
    op.drop_table("vpncraft_promocodes")
    op.drop_table("vpncraft_transactions")
    op.drop_table("vpncraft_users")
    op.drop_table("vpncraft_servers")

    sa.Enum(name="vpncraft_referrerrewardlevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="vpncraft_referrerrewardtype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="vpncraft_transactionstatus").drop(op.get_bind(), checkfirst=True)
