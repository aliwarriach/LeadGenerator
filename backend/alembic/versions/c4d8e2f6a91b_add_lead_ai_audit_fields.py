"""add lead ai audit fields

Revision ID: c4d8e2f6a91b
Revises: 8a2f1c9d3b47
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4d8e2f6a91b"
down_revision: Union[str, Sequence[str], None] = "8a2f1c9d3b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("leads", sa.Column("ai_ui_score", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("ai_conversion_score", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("ai_content_score", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("ai_trust_score", sa.Integer(), nullable=True))
    op.add_column(
        "leads", sa.Column("ai_issues", postgresql.ARRAY(sa.String(length=512)), nullable=True)
    )
    op.add_column("leads", sa.Column("ai_summary", sa.String(length=4096), nullable=True))
    op.add_column("leads", sa.Column("ai_audited_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("leads", "ai_audited_at")
    op.drop_column("leads", "ai_summary")
    op.drop_column("leads", "ai_issues")
    op.drop_column("leads", "ai_trust_score")
    op.drop_column("leads", "ai_content_score")
    op.drop_column("leads", "ai_conversion_score")
    op.drop_column("leads", "ai_ui_score")
