"""Add durable mobile chat turns; no changes to existing accounts, OAuth or operations."""

from alembic import op
import sqlalchemy as sa

revision = "a710f7a40401"
down_revision = "9906fa12eb62"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_turns",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("parent_id", sa.String(32)),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text()),
        sa.Column("messages", sa.JSON()),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_chat_turns_status", "chat_turns", ["status"])


def downgrade():
    op.drop_index("ix_chat_turns_status", table_name="chat_turns")
    op.drop_table("chat_turns")
