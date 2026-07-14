"""add lead enrichment fields

Revision ID: 4fc93386b57d
Revises: ce61f0fba131
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4fc93386b57d"
down_revision: Union[str, Sequence[str], None] = "ce61f0fba131"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("leads", sa.Column("website_domain", sa.String(length=512), nullable=True))
    op.add_column("leads", sa.Column("website_score", sa.Float(), nullable=True))
    op.add_column(
        "leads",
        sa.Column("website_score_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "leads", sa.Column("emails", postgresql.ARRAY(sa.String(length=320)), nullable=True)
    )
    op.add_column(
        "leads", sa.Column("tech_stack", postgresql.ARRAY(sa.String(length=128)), nullable=True)
    )
    op.add_column("leads", sa.Column("is_registered", sa.Boolean(), nullable=True))
    op.add_column("leads", sa.Column("logo_valid", sa.Boolean(), nullable=True))
    op.add_column("leads", sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_leads_website_domain", "leads", ["website_domain"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_leads_website_domain", table_name="leads")
    op.drop_column("leads", "enriched_at")
    op.drop_column("leads", "logo_valid")
    op.drop_column("leads", "is_registered")
    op.drop_column("leads", "tech_stack")
    op.drop_column("leads", "emails")
    op.drop_column("leads", "website_score_details")
    op.drop_column("leads", "website_score")
    op.drop_column("leads", "website_domain")
