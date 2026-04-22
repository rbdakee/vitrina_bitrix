from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AssignmentBatch, AssignmentBatchItem


class AssignmentBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(
        self,
        *,
        bitrix_user_id: str,
        agent_phone: str,
        portal_domain: str | None,
        requested_count: int,
        assigned_count: int,
        selected_property_classes: list[str] | None,
        category_counts: dict[str, int],
        assignment_status: str,
        sync_status: str,
        dry_run: bool,
        error_message: str | None,
        items: Sequence[dict],
    ) -> AssignmentBatch:
        batch = AssignmentBatch(
            bitrix_user_id=bitrix_user_id,
            agent_phone=agent_phone,
            portal_domain=portal_domain,
            requested_count=requested_count,
            assigned_count=assigned_count,
            selected_property_classes=selected_property_classes,
            category_counts=category_counts,
            assignment_status=assignment_status,
            sync_status=sync_status,
            dry_run=dry_run,
            error_message=error_message,
        )
        self.session.add(batch)
        await self.session.flush()

        for item in items:
            self.session.add(
                AssignmentBatchItem(
                    batch_id=batch.id,
                    batch_position=item["batch_position"],
                    vitrina_id=item["vitrina_id"],
                    category=item["category"],
                    raw_object_snapshot=item["raw_object_snapshot"],
                    lead_payload=item["lead_payload"],
                    sync_status=item["sync_status"],
                    sync_error=item.get("sync_error"),
                    bitrix_lead_id=item.get("bitrix_lead_id"),
                )
            )

        await self.session.flush()
        return await self.get_batch(batch.id)

    async def get_batch(self, batch_id: UUID) -> AssignmentBatch | None:
        result = await self.session.execute(
            select(AssignmentBatch)
            .options(selectinload(AssignmentBatch.items))
            .where(AssignmentBatch.id == batch_id)
        )
        return result.scalar_one_or_none()

