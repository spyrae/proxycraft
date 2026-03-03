"""Multi-use promocodes: replace is_activated/activated_by with max_uses + M2M table.

Revision ID: 004_multi_use_promocodes
Revises: 003_add_operator
Create Date: 2026-03-02
"""

import sqlalchemy as sa
from alembic import op

revision = "004_multi_use_promocodes"
down_revision = "003_add_operator"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create M2M activation tracking table
    op.create_table(
        "vpncraft_activated_promocodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("promocode_id", sa.Integer(), nullable=False),
        sa.Column("user_tg_id", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_vpncraft_activated_promocodes"),
        sa.ForeignKeyConstraint(
            ["promocode_id"],
            ["vpncraft_promocodes.id"],
            name="fk_vpncraft_activated_promocodes_promocode_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_tg_id"],
            ["vpncraft_users.tg_id"],
            name="fk_vpncraft_activated_promocodes_user_tg_id",
            ondelete="CASCADE",
        ),
    )

    # 2. Migrate existing activation data to the new table
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO vpncraft_activated_promocodes (promocode_id, user_tg_id, activated_at)
            SELECT id, activated_by, created_at
            FROM vpncraft_promocodes
            WHERE is_activated = true AND activated_by IS NOT NULL
            """
        )
    )

    # 3. Add max_uses column to promocodes
    op.add_column(
        "vpncraft_promocodes",
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
    )

    # 4. Drop old columns
    op.drop_constraint(
        "fk_vpncraft_promocodes_activated_by_vpncraft_users",
        "vpncraft_promocodes",
        type_="foreignkey",
    )
    op.drop_column("vpncraft_promocodes", "activated_by")
    op.drop_column("vpncraft_promocodes", "is_activated")


def downgrade() -> None:
    # Restore old columns
    op.add_column(
        "vpncraft_promocodes",
        sa.Column("is_activated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "vpncraft_promocodes",
        sa.Column("activated_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_vpncraft_promocodes_activated_by_vpncraft_users",
        "vpncraft_promocodes",
        "vpncraft_users",
        ["activated_by"],
        ["tg_id"],
    )

    # Migrate data back (only first activation per promocode)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE vpncraft_promocodes p
            SET is_activated = true,
                activated_by = a.user_tg_id
            FROM (
                SELECT DISTINCT ON (promocode_id) promocode_id, user_tg_id
                FROM vpncraft_activated_promocodes
                ORDER BY promocode_id, activated_at ASC
            ) a
            WHERE p.id = a.promocode_id
            """
        )
    )

    # Drop max_uses and new table
    op.drop_column("vpncraft_promocodes", "max_uses")
    op.drop_table("vpncraft_activated_promocodes")
