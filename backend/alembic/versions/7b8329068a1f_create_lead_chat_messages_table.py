"""create lead chat messages table

Revision ID: 7b8329068a1f
Revises: 73db7de897d0
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7b8329068a1f"
down_revision: Union[str, Sequence[str], None] = "73db7de897d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lead_chat_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_chat_messages_lead_id"), "lead_chat_messages", ["lead_id"])
    op.create_index(op.f("ix_lead_chat_messages_created_at"), "lead_chat_messages", ["created_at"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_lead_chat_messages_created_at"), table_name="lead_chat_messages")
    op.drop_index(op.f("ix_lead_chat_messages_lead_id"), table_name="lead_chat_messages")
    op.drop_table("lead_chat_messages")
