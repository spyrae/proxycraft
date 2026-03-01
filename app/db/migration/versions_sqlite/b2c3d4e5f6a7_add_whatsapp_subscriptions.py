"""add whatsapp_subscriptions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-27 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_tg_id", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_trial_used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["user_tg_id"],
            ["users.tg_id"],
            name=op.f("fk_whatsapp_subscriptions_user_tg_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_whatsapp_subscriptions")),
        sa.UniqueConstraint("port", name=op.f("uq_whatsapp_subscriptions_port")),
        sa.UniqueConstraint("user_tg_id", name=op.f("uq_whatsapp_subscriptions_user_tg_id")),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_subscriptions")
