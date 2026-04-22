from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import APIModel


class AssignmentTakeRequest(APIModel):
    bitrix_user_id: str = Field(min_length=1)
    dry_run: bool = False


class AssignmentBatchItemResponse(APIModel):
    id: int
    batch_position: int
    vitrina_id: int
    category: str
    raw_object_snapshot: dict
    lead_payload: dict
    bitrix_lead_id: str | None
    sync_status: str
    sync_error: str | None
    created_at: datetime
    updated_at: datetime


class AssignmentBatchResponse(APIModel):
    id: UUID
    bitrix_user_id: str
    agent_phone: str
    portal_domain: str | None
    requested_count: int
    assigned_count: int
    selected_property_classes: list[str] | None
    category_counts: dict[str, int]
    assignment_status: str
    sync_status: str
    dry_run: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    items: list[AssignmentBatchItemResponse]


class AssignmentConflictResponse(APIModel):
    message: str
    batch: AssignmentBatchResponse

