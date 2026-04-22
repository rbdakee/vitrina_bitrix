from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import SYNC_STATUS_NOT_REQUESTED
from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class BitrixAgentMapping(TimestampMixin, Base):
    __tablename__ = "bitrix_agent_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bitrix_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    agent_phone: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssignmentBatch(TimestampMixin, Base):
    __tablename__ = "assignment_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bitrix_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_phone: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    portal_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_count: Mapped[int] = mapped_column(nullable=False)
    assigned_count: Mapped[int] = mapped_column(nullable=False, default=0)
    selected_property_classes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    category_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    assignment_status: Mapped[str] = mapped_column(String(32), nullable=False)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default=SYNC_STATUS_NOT_REQUESTED)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["AssignmentBatchItem"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="AssignmentBatchItem.batch_position",
    )


class AssignmentBatchItem(TimestampMixin, Base):
    __tablename__ = "assignment_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "vitrina_id", name="uq_assignment_batch_items_batch_vitrina"),
        Index("ix_assignment_batch_items_sync_status", "sync_status"),
        Index("ix_assignment_batch_items_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assignment_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_position: Mapped[int] = mapped_column(nullable=False)
    vitrina_id: Mapped[int] = mapped_column(nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(10), nullable=False)
    raw_object_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    lead_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bitrix_lead_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default=SYNC_STATUS_NOT_REQUESTED)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped[AssignmentBatch] = relationship(back_populates="items")


Index("ix_assignment_batches_created_at", AssignmentBatch.created_at)
Index("ix_assignment_batches_sync_status", AssignmentBatch.sync_status)

