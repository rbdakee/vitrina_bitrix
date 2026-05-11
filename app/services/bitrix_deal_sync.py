from __future__ import annotations

from app.bitrix.client import BitrixApiClient
from app.constants import SYNC_STATUS_FAILED, SYNC_STATUS_PARTIAL_FAILED, SYNC_STATUS_PENDING, SYNC_STATUS_SUCCESS
from app.db.models import AssignmentBatch
from app.exceptions import BitrixSyncConfigurationError
from app.repositories.assignment_batches import AssignmentBatchRepository
from app.schemas.bitrix import BitrixExecutionContext
from app.services.complex_matcher import ComplexMatcher


class BitrixDealSyncService:
    def __init__(
        self,
        *,
        batch_repo: AssignmentBatchRepository,
        client: BitrixApiClient,
        complex_matcher: ComplexMatcher,
    ) -> None:
        self.batch_repo = batch_repo
        self.client = client
        self.complex_matcher = complex_matcher

    async def sync_batch(self, batch_id, context: BitrixExecutionContext) -> AssignmentBatch:
        if not context.portal_domain or not context.access_token:
            raise BitrixSyncConfigurationError(
                "portal_domain and access_token are required for live Bitrix deal sync."
            )

        batch = await self.batch_repo.get_batch(batch_id)
        if not batch:
            raise ValueError(f"Assignment batch `{batch_id}` was not found.")

        batch.sync_status = SYNC_STATUS_PENDING
        success_count = 0
        failed_count = 0

        try:
            await self.complex_matcher.fetch_next_page(context)
        except Exception:
            pass

        for item in batch.items:
            payload = dict(item.lead_payload or {})
            try:
                complex_id = await self.complex_matcher.resolve(
                    payload.get("complex_name"), context
                )
                deal_id = await self.client.create_deal_with_contact(
                    context,
                    payload=payload,
                    complex_smart_id=complex_id,
                )
                item.bitrix_lead_id = str(deal_id)
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
