"""Rename all vpncraft_ tables, constraints and enum types to proxycraft_.

Revision ID: 007_rename_to_proxycraft
Revises: 006_add_user_balance
Create Date: 2026-03-06
"""

from alembic import op

revision = "007_rename_to_proxycraft"
down_revision = "006_add_user_balance"
branch_labels = None
depends_on = None

# Tables to rename (old → new)
TABLES = [
    "vpncraft_servers",
    "vpncraft_users",
    "vpncraft_transactions",
    "vpncraft_promocodes",
    "vpncraft_activated_promocodes",
    "vpncraft_referrals",
    "vpncraft_referrer_rewards",
    "vpncraft_invites",
    "vpncraft_mtproto_subscriptions",
    "vpncraft_whatsapp_subscriptions",
    "vpncraft_subscription_events",
    "vpncraft_balance_log",
]

# Enum types to rename (old → new)
ENUMS = [
    "vpncraft_transactionstatus",
    "vpncraft_referrerrewardtype",
    "vpncraft_referrerrewardlevel",
]

# Sequences to rename (old → new). PostgreSQL auto-creates sequences for serial PKs.
SEQUENCES = [
    "vpncraft_servers_id_seq",
    "vpncraft_users_id_seq",
    "vpncraft_transactions_id_seq",
    "vpncraft_promocodes_id_seq",
    "vpncraft_activated_promocodes_id_seq",
    "vpncraft_referrals_id_seq",
    "vpncraft_referrer_rewards_id_seq",
    "vpncraft_invites_id_seq",
    "vpncraft_mtproto_subscriptions_id_seq",
    "vpncraft_whatsapp_subscriptions_id_seq",
    "vpncraft_subscription_events_id_seq",
    "vpncraft_balance_log_id_seq",
]


def upgrade():
    conn = op.get_bind()

    # 1. Rename tables
    for old in TABLES:
        new = old.replace("vpncraft_", "proxycraft_")
        op.rename_table(old, new)

    # 2. Rename sequences (ignore if not exists — some tables use uuid PKs)
    for old_seq in SEQUENCES:
        new_seq = old_seq.replace("vpncraft_", "proxycraft_")
        conn.execute(
            __import__("sqlalchemy").text(
                f"ALTER SEQUENCE IF EXISTS {old_seq} RENAME TO {new_seq}"
            )
        )

    # 3. Rename enum types
    for old_enum in ENUMS:
        new_enum = old_enum.replace("vpncraft_", "proxycraft_")
        conn.execute(
            __import__("sqlalchemy").text(
                f"ALTER TYPE {old_enum} RENAME TO {new_enum}"
            )
        )

    # 4. Rename constraints that contain vpncraft_ in their name.
    #    We query pg_constraint to find all affected constraints and rename them.
    result = conn.execute(
        __import__("sqlalchemy").text(
            """
            SELECT conname, conrelid::regclass::text AS table_name, contype
            FROM pg_constraint
            WHERE conname LIKE '%vpncraft%'
            ORDER BY conrelid, contype
            """
        )
    )
    constraints = result.fetchall()
    for row in constraints:
        old_name = row[0]
        table_name = row[1]
        new_name = old_name.replace("vpncraft_", "proxycraft_").replace("vpncraft", "proxycraft")
        conn.execute(
            __import__("sqlalchemy").text(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )
        )

    # 5. Rename indexes that contain vpncraft_ in their name
    result = conn.execute(
        __import__("sqlalchemy").text(
            """
            SELECT indexname FROM pg_indexes
            WHERE indexname LIKE '%vpncraft%'
            """
        )
    )
    indexes = result.fetchall()
    for row in indexes:
        old_idx = row[0]
        new_idx = old_idx.replace("vpncraft_", "proxycraft_").replace("vpncraft", "proxycraft")
        conn.execute(
            __import__("sqlalchemy").text(
                f'ALTER INDEX IF EXISTS "{old_idx}" RENAME TO "{new_idx}"'
            )
        )


def downgrade():
    conn = op.get_bind()

    # Reverse: rename indexes back
    result = conn.execute(
        __import__("sqlalchemy").text(
            "SELECT indexname FROM pg_indexes WHERE indexname LIKE '%proxycraft%'"
        )
    )
    for row in result.fetchall():
        new_idx = row[0]
        old_idx = new_idx.replace("proxycraft_", "vpncraft_").replace("proxycraft", "vpncraft")
        conn.execute(
            __import__("sqlalchemy").text(
                f'ALTER INDEX IF EXISTS "{new_idx}" RENAME TO "{old_idx}"'
            )
        )

    # Reverse: rename constraints back
    result = conn.execute(
        __import__("sqlalchemy").text(
            """
            SELECT conname, conrelid::regclass::text AS table_name
            FROM pg_constraint WHERE conname LIKE '%proxycraft%'
            ORDER BY conrelid
            """
        )
    )
    for row in result.fetchall():
        new_name = row[0]
        table_name = row[1]
        old_name = new_name.replace("proxycraft_", "vpncraft_").replace("proxycraft", "vpncraft")
        conn.execute(
            __import__("sqlalchemy").text(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{new_name}" TO "{old_name}"'
            )
        )

    # Reverse: rename enum types back
    for old_enum in ENUMS:
        new_enum = old_enum.replace("vpncraft_", "proxycraft_")
        conn.execute(
            __import__("sqlalchemy").text(
                f"ALTER TYPE {new_enum} RENAME TO {old_enum}"
            )
        )

    # Reverse: rename sequences back
    for old_seq in SEQUENCES:
        new_seq = old_seq.replace("vpncraft_", "proxycraft_")
        conn.execute(
            __import__("sqlalchemy").text(
                f"ALTER SEQUENCE IF EXISTS {new_seq} RENAME TO {old_seq}"
            )
        )

    # Reverse: rename tables back
    for old in TABLES:
        new = old.replace("vpncraft_", "proxycraft_")
        op.rename_table(new, old)
