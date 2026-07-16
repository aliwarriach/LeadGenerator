"""add lead pipeline and pagespeed fields

Revision ID: 73db7de897d0
Revises: c4d8e2f6a91b
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "73db7de897d0"
down_revision: Union[str, Sequence[str], None] = "c4d8e2f6a91b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("leads", sa.Column("pagespeed_score", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("seo_score", sa.Float(), nullable=True))
    op.add_column(
        "leads", sa.Column("performance_issues", postgresql.ARRAY(sa.String(length=512)), nullable=True)
    )
    op.add_column("leads", sa.Column("estimated_revenue_level", sa.String(length=64), nullable=True))
    op.add_column(
        "leads",
        sa.Column("pipeline_stage", sa.String(length=32), nullable=False, server_default="new_lead"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("leads", "pipeline_stage")
    op.drop_column("leads", "estimated_revenue_level")
    op.drop_column("leads", "performance_issues")
    op.drop_column("leads", "seo_score")
    op.drop_column("leads", "pagespeed_score")
