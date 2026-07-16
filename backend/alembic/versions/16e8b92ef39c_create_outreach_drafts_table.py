"""create outreach drafts table

Revision ID: 16e8b92ef39c
Revises: d5621150de93
Create Date: 2026-07-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "16e8b92ef39c"
down_revision: Union[str, Sequence[str], None] = "d5621150de93"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "outreach_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outreach_drafts_lead_id"), "outreach_drafts", ["lead_id"])
    op.create_index(op.f("ix_outreach_drafts_type"), "outreach_drafts", ["type"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_outreach_drafts_type"), table_name="outreach_drafts")
    op.drop_index(op.f("ix_outreach_drafts_lead_id"), table_name="outreach_drafts")
    op.drop_table("outreach_drafts")
