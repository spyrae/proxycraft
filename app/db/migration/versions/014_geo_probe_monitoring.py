"""Add geo probe monitoring persistence.

Revision ID: 014_geo_probe_monitoring
Revises: 013_add_legal_consents
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

revision = "014_geo_probe_monitoring"
down_revision = "013_add_legal_consents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxycraft_geo_probe_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_uuid", sa.String(length=36), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("run_uuid", name="uq_proxycraft_geo_probe_runs_run_uuid"),
    )

    op.create_table(
        "proxycraft_geo_probe_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("proxycraft_geo_probe_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("probe_scope", sa.String(length=32), nullable=False),
        sa.Column("probe_region", sa.String(length=32), nullable=False),
        sa.Column("probe_node", sa.String(length=128), nullable=True),
        sa.Column("probe_country", sa.String(length=8), nullable=True),
        sa.Column("probe_city", sa.String(length=128), nullable=True),
        sa.Column("probe_asn", sa.String(length=64), nullable=True),
        sa.Column("product", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("throughput_kbps", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(
        "ix_proxycraft_geo_probe_results_run_id",
        "proxycraft_geo_probe_results",
        ["run_id"],
    )
    op.create_index(
        "ix_proxycraft_geo_probe_results_product",
        "proxycraft_geo_probe_results",
        ["product"],
    )
    op.create_index(
        "ix_proxycraft_geo_probe_results_probe_region",
        "proxycraft_geo_probe_results",
        ["probe_region"],
    )


def downgrade() -> None:
    op.drop_index("ix_proxycraft_geo_probe_results_probe_region", table_name="proxycraft_geo_probe_results")
    op.drop_index("ix_proxycraft_geo_probe_results_product", table_name="proxycraft_geo_probe_results")
    op.drop_index("ix_proxycraft_geo_probe_results_run_id", table_name="proxycraft_geo_probe_results")
    op.drop_table("proxycraft_geo_probe_results")
    op.drop_table("proxycraft_geo_probe_runs")
