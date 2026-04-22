from __future__ import annotations

from app.bitrix.client import BitrixApiClient
from app.constants import SYNC_STATUS_FAILED, SYNC_STATUS_PARTIAL_FAILED, SYNC_STATUS_PENDING, SYNC_STATUS_SUCCESS
from app.db.models import AssignmentBatch
from app.exceptions import BitrixSyncConfigurationError
from app.repositories.assignment_batches import AssignmentBatchRepository
from app.schemas.bitrix import BitrixExecutionContext


class BitrixLeadSyncService:
    def __init__(
        self,
        *,
        batch_repo: AssignmentBatchRepository,
        client: BitrixApiClient,
    ) -> None:
        self.batch_repo = batch_repo
        self.client = client

    async def sync_batch(self, batch_id, context: BitrixExecutionContext) -> AssignmentBatch:
        if not context.portal_domain or not context.access_token:
            raise BitrixSyncConfigurationError(
                "portal_domain and access_token are required for live Bitrix lead sync."
            )

        batch = await self.batch_repo.get_batch(batch_id)
        if not batch:
            raise ValueError(f"Assignment batch `{batch_id}` was not found.")

        batch.sync_status = SYNC_STATUS_PENDING
        success_count = 0
        failed_count = 0

        for item in batch.items:
            try:
                lead_id = await self.client.create_lead(context, item.lead_payload)
                item.bitrix_lead_id = str(lead_id)
                item.sync_status = SYNC_STATUS_SUCCESS
                item.sync_error = None
                success_count += 1
            except Exception as exc:
                item.sync_status = SYNC_STATUS_FAILED
                item.sync_error = str(exc)
                failed_count += 1

        if failed_count == 0:
            batch.sync_status = SYNC_STATUS_SUCCESS
        elif success_count == 0:
            batch.sync_status = SYNC_STATUS_FAILED
        else:
            batch.sync_status = SYNC_STATUS_PARTIAL_FAILED

        await self.batch_repo.session.flush()
        return await self.batch_repo.get_batch(batch.id)

