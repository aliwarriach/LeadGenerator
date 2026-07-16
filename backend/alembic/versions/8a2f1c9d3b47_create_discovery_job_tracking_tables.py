"""create discovery job tracking tables

Revision ID: 8a2f1c9d3b47
Revises: 4fc93386b57d
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8a2f1c9d3b47"
down_revision: Union[str, Sequence[str], None] = "4fc93386b57d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "discovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=512), nullable=False),
        sa.Column("custom_niche", sa.String(length=256), nullable=False),
        sa.Column("min_rating", sa.Float(), nullable=True),
        sa.Column("total_jobs", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )

    op.create_table(
        "discovery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovery_runs.id"), nullable=False),
        sa.Column("arq_job_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=512), nullable=False),
        sa.Column("location", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("current_business_name", sa.String(length=512), nullable=True),
        sa.Column("leads_found_session", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_saved_session", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extraction_failures_session", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.Column("error_retryable", sa.Boolean(), nullable=True),
        sa.Column("error_retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_discovery_jobs_run_id", "discovery_jobs", ["run_id"], unique=False)
    op.create_index("ix_discovery_jobs_arq_job_id", "discovery_jobs", ["arq_job_id"], unique=True)
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"], unique=False)

    op.create_table(
        "discovery_job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discovery_jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index("ix_discovery_job_events_job_id", "discovery_job_events", ["job_id"], unique=False)
    op.create_index("ix_discovery_job_events_created_at", "discovery_job_events", ["created_at"], unique=False)
    op.create_index(
        "ix_discovery_job_events_job_id_id", "discovery_job_events", ["job_id", "id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_discovery_job_events_job_id_id", table_name="discovery_job_events")
    op.drop_index("ix_discovery_job_events_created_at", table_name="discovery_job_events")
    op.drop_index("ix_discovery_job_events_job_id", table_name="discovery_job_events")
    op.drop_table("discovery_job_events")

    op.drop_index("ix_discovery_jobs_status", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_arq_job_id", table_name="discovery_jobs")
    op.drop_index("ix_discovery_jobs_run_id", table_name="discovery_jobs")
    op.drop_table("discovery_jobs")

    op.drop_table("discovery_runs")
