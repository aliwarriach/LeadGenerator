"""create leads table

Revision ID: ce61f0fba131
Revises:
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ce61f0fba131"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("location", sa.String(length=1024), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("has_website", sa.Boolean(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("category", sa.String(length=256), nullable=True),
        sa.Column("query", sa.String(length=512), nullable=True),
        sa.Column("search_location", sa.String(length=512), nullable=True),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_leads_dedupe_key", "leads", ["dedupe_key"], unique=True)
    op.create_index("ix_leads_source", "leads", ["source"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_leads_source", table_name="leads")
    op.drop_index("ix_leads_dedupe_key", table_name="leads")
    op.drop_table("leads")
