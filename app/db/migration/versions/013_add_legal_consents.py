"""Add persisted legal consent fields to users.

Revision ID: 013_add_legal_consents
Revises: 012_smoke_fixture_registry
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "013_add_legal_consents"
down_revision = "012_smoke_fixture_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxycraft_users", sa.Column("legal_consents_version", sa.String(length=32), nullable=True))
    op.add_column("proxycraft_users", sa.Column("privacy_policy_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("proxycraft_users", sa.Column("terms_of_use_accepted_at", sa.DateTime(), nullable=True))
    op.add_column(
        "proxycraft_users",
        sa.Column("personal_data_consent_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "proxycraft_users",
        sa.Column(
            "marketing_consent_granted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("proxycraft_users", sa.Column("marketing_consent_updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("proxycraft_users", "marketing_consent_updated_at")
    op.drop_column("proxycraft_users", "marketing_consent_granted")
    op.drop_column("proxycraft_users", "personal_data_consent_accepted_at")
    op.drop_column("proxycraft_users", "terms_of_use_accepted_at")
    op.drop_column("proxycraft_users", "privacy_policy_accepted_at")
    op.drop_column("proxycraft_users", "legal_consents_version")
