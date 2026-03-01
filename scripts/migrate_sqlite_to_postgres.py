#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL (Supabase).

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite /path/to/bot_database.db \
        --pg "postgresql://postgres.psfijaghtakeejrawrab:PASSWORD@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"

Tables are migrated in FK order:
    servers → users → transactions → promocodes → referrals →
    referrer_rewards → invites → mtproto_subscriptions → whatsapp_subscriptions

Features:
    - ON CONFLICT DO NOTHING for idempotency (safe to re-run)
    - Resets PostgreSQL sequences after INSERT
    - Verification: row count comparison
"""

import argparse
import asyncio
import logging
import sqlite3
import sys

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Migration order respects FK dependencies
TABLES = [
    {
        "sqlite": "servers",
        "pg": "vpncraft_servers",
        "columns": ["id", "name", "host", "max_clients", "location", "online"],
        "pk_seq": ("vpncraft_servers", "id"),
    },
    {
        "sqlite": "users",
        "pg": "vpncraft_users",
        "columns": [
            "id", "tg_id", "vpn_id", "server_id", "first_name",
            "username", "language_code", "created_at", "is_trial_used",
            "source_invite_name",
        ],
        "pk_seq": ("vpncraft_users", "id"),
    },
    {
        "sqlite": "transactions",
        "pg": "vpncraft_transactions",
        "columns": [
            "id", "tg_id", "payment_id", "subscription",
            "status", "created_at", "updated_at",
        ],
        "pk_seq": ("vpncraft_transactions", "id"),
    },
    {
        "sqlite": "promocodes",
        "pg": "vpncraft_promocodes",
        "columns": [
            "id", "code", "duration", "is_activated",
            "activated_by", "created_at",
        ],
        "pk_seq": ("vpncraft_promocodes", "id"),
    },
    {
        "sqlite": "referrals",
        "pg": "vpncraft_referrals",
        "columns": [
            "id", "referred_tg_id", "referrer_tg_id", "created_at",
            "referred_rewarded_at", "referred_bonus_days",
        ],
        "pk_seq": ("vpncraft_referrals", "id"),
    },
    {
        "sqlite": "referrer_rewards",
        "pg": "vpncraft_referrer_rewards",
        "columns": [
            "id", "user_tg_id", "reward_type", "reward_level",
            "amount", "created_at", "rewarded_at", "payment_id",
        ],
        "pk_seq": ("vpncraft_referrer_rewards", "id"),
    },
    {
        "sqlite": "invites",
        "pg": "vpncraft_invites",
        "columns": ["id", "name", "hash_code", "clicks", "created_at", "is_active"],
        "pk_seq": ("vpncraft_invites", "id"),
    },
    {
        "sqlite": "mtproto_subscriptions",
        "pg": "vpncraft_mtproto_subscriptions",
        "columns": [
            "id", "user_tg_id", "secret", "activated_at",
            "expires_at", "is_active", "is_trial_used",
        ],
        "pk_seq": ("vpncraft_mtproto_subscriptions", "id"),
    },
    {
        "sqlite": "whatsapp_subscriptions",
        "pg": "vpncraft_whatsapp_subscriptions",
        "columns": [
            "id", "user_tg_id", "port", "activated_at",
            "expires_at", "is_active", "is_trial_used",
        ],
        "pk_seq": ("vpncraft_whatsapp_subscriptions", "id"),
    },
]

# SQLite stores booleans as 0/1, PostgreSQL needs true/false
BOOL_COLUMNS = {
    "online", "is_activated", "is_active", "is_trial_used",
}


def sqlite_to_python(value, col_name: str):
    """Convert SQLite values to Python types suitable for asyncpg."""
    if value is None:
        return None
    if col_name in BOOL_COLUMNS:
        return bool(int(value))
    return value


async def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn: asyncpg.Connection,
    table_def: dict,
) -> int:
    """Migrate a single table. Returns number of rows inserted."""
    sqlite_table = table_def["sqlite"]
    pg_table = table_def["pg"]
    columns = table_def["columns"]

    # Check if SQLite table exists
    cursor = sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (sqlite_table,),
    )
    if not cursor.fetchone():
        logger.warning(f"  SQLite table '{sqlite_table}' does not exist, skipping.")
        return 0

    # Read from SQLite
    col_list = ", ".join(columns)
    cursor = sqlite_conn.execute(f"SELECT {col_list} FROM {sqlite_table}")
    rows = cursor.fetchall()

    if not rows:
        logger.info(f"  {sqlite_table} → {pg_table}: 0 rows (empty)")
        return 0

    # Build INSERT with ON CONFLICT DO NOTHING
    placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
    col_names = ", ".join(columns)
    insert_sql = f"INSERT INTO {pg_table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    inserted = 0
    for row in rows:
        converted = [sqlite_to_python(row[i], columns[i]) for i in range(len(columns))]
        try:
            result = await pg_conn.execute(insert_sql, *converted)
            if "INSERT 0 1" in result:
                inserted += 1
        except Exception as e:
            logger.error(f"  Error inserting row into {pg_table}: {e}")
            logger.error(f"  Row data: {dict(zip(columns, converted))}")

    logger.info(f"  {sqlite_table} → {pg_table}: {inserted}/{len(rows)} rows inserted")
    return inserted


async def reset_sequence(pg_conn: asyncpg.Connection, table: str, pk_column: str) -> None:
    """Reset PostgreSQL sequence to max(pk) + 1."""
    max_val = await pg_conn.fetchval(f"SELECT COALESCE(MAX({pk_column}), 0) FROM {table}")
    seq_name = f"{table}_{pk_column}_seq"
    await pg_conn.execute(f"SELECT setval('{seq_name}', $1, true)", max(max_val, 1))
    logger.info(f"  Sequence {seq_name} reset to {max_val}")


async def verify(
    sqlite_conn: sqlite3.Connection,
    pg_conn: asyncpg.Connection,
) -> bool:
    """Verify row counts match between SQLite and PostgreSQL."""
    all_ok = True
    logger.info("\n=== Verification ===")

    for table_def in TABLES:
        sqlite_table = table_def["sqlite"]
        pg_table = table_def["pg"]

        # SQLite count
        cursor = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (sqlite_table,),
        )
        if not cursor.fetchone():
            logger.info(f"  {sqlite_table}: not in SQLite (skipped)")
            continue

        cursor = sqlite_conn.execute(f"SELECT COUNT(*) FROM {sqlite_table}")
        sqlite_count = cursor.fetchone()[0]

        # PG count
        pg_count = await pg_conn.fetchval(f"SELECT COUNT(*) FROM {pg_table}")

        status = "OK" if sqlite_count == pg_count else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        logger.info(f"  {pg_table}: SQLite={sqlite_count}, PG={pg_count} [{status}]")

    return all_ok


async def main(sqlite_path: str, pg_dsn: str) -> None:
    logger.info(f"SQLite: {sqlite_path}")
    logger.info(f"PostgreSQL: {pg_dsn.split('@')[1] if '@' in pg_dsn else pg_dsn}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    pg_conn = await asyncpg.connect(pg_dsn)

    try:
        logger.info("\n=== Migrating tables ===")
        for table_def in TABLES:
            await migrate_table(sqlite_conn, pg_conn, table_def)

        logger.info("\n=== Resetting sequences ===")
        for table_def in TABLES:
            table, pk = table_def["pk_seq"]
            await reset_sequence(pg_conn, table, pk)

        ok = await verify(sqlite_conn, pg_conn)
        if ok:
            logger.info("\n Migration completed successfully!")
        else:
            logger.warning("\n Migration completed with mismatches. Please investigate.")
            sys.exit(1)
    finally:
        sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate VPNCraft data from SQLite to PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Path to SQLite database file")
    parser.add_argument("--pg", required=True, help="PostgreSQL connection string (asyncpg format)")
    args = parser.parse_args()

    asyncio.run(main(args.sqlite, args.pg))
