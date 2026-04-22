"""Create service tables for vitrina_bitrix."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_create_service_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bitrix_agent_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bitrix_user_id", sa.String(length=255), nullable=False),
        sa.Column("agent_phone", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bitrix_user_id"),
    )
    op.create_index(
        "ix_bitrix_agent_mappings_bitrix_user_id",
        "bitrix_agent_mappings",
        ["bitrix_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_bitrix_agent_mappings_agent_phone",
        "bitrix_agent_mappings",
        ["agent_phone"],
        unique=False,
    )

    op.create_table(
        "assignment_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bitrix_user_id", sa.String(length=255), nullable=False),
        sa.Column("agent_phone", sa.String(length=255), nullable=False),
        sa.Column("portal_domain", sa.String(length=255), nullable=True),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("assigned_count", sa.Integer(), nullable=False),
        sa.Column("selected_property_classes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("category_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assignment_status", sa.String(length=32), nullable=False),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assignment_batches_bitrix_user_id", "assignment_batches", ["bitrix_user_id"], unique=False)
    op.create_index("ix_assignment_batches_agent_phone", "assignment_batches", ["agent_phone"], unique=False)
    op.create_index("ix_assignment_batches_sync_status", "assignment_batches", ["sync_status"], unique=False)
    op.create_index("ix_assignment_batches_created_at", "assignment_batches", ["created_at"], unique=False)

    op.create_table(
        "assignment_batch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_position", sa.Integer(), nullable=False),
        sa.Column("vitrina_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=10), nullable=False),
        sa.Column("raw_object_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lead_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bitrix_lead_id", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["assignment_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "vitrina_id", name="uq_assignment_batch_items_batch_vitrina"),
    )
    op.create_index("ix_assignment_batch_items_batch_id", "assignment_batch_items", ["batch_id"], unique=False)
    op.create_index("ix_assignment_batch_items_vitrina_id", "assignment_batch_items", ["vitrina_id"], unique=False)
    op.create_index("ix_assignment_batch_items_sync_status", "assignment_batch_items", ["sync_status"], unique=False)
    op.create_index("ix_assignment_batch_items_created_at", "assignment_batch_items", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_assignment_batch_items_created_at", table_name="assignment_batch_items")
    op.drop_index("ix_assignment_batch_items_sync_status", table_name="assignment_batch_items")
    op.drop_index("ix_assignment_batch_items_vitrina_id", table_name="assignment_batch_items")
    op.drop_index("ix_assignment_batch_items_batch_id", table_name="assignment_batch_items")
    op.drop_table("assignment_batch_items")

    op.drop_index("ix_assignment_batches_created_at", table_name="assignment_batches")
    op.drop_index("ix_assignment_batches_sync_status", table_name="assignment_batches")
    op.drop_index("ix_assignment_batches_agent_phone", table_name="assignment_batches")
    op.drop_index("ix_assignment_batches_bitrix_user_id", table_name="assignment_batches")
    op.drop_table("assignment_batches")

    op.drop_index("ix_bitrix_agent_mappings_agent_phone", table_name="bitrix_agent_mappings")
    op.drop_index("ix_bitrix_agent_mappings_bitrix_user_id", table_name="bitrix_agent_mappings")
    op.drop_table("bitrix_agent_mappings")

