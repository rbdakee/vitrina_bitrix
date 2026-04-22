from __future__ import annotations

from typing import Any

from app.constants import (
    ASSIGNMENT_BATCH_SIZE,
    ASSIGNMENT_LIMIT_THRESHOLD,
    ASSIGNMENT_STATUS_ASSIGNED,
    ASSIGNMENT_STATUS_BLOCKED_LIMIT,
    ASSIGNMENT_STATUS_EMPTY_SUPPLY,
    ASSIGNMENT_STATUS_FAILED,
    ASSIGNMENT_STATUS_PREVIEW,
    SYNC_STATUS_NOT_REQUESTED,
    SYNC_STATUS_PENDING,
)
from app.exceptions import AssignmentConflictError
from app.repositories.assignment_batches import AssignmentBatchRepository
from app.repositories.legacy_agents import LegacyAgentRepository
from app.repositories.parsed_properties import ParsedPropertyRepository
from app.schemas.bitrix import BitrixExecutionContext
from app.services.agent_mapping_service import AgentMappingService
from app.services.lead_payload import LeadPayloadBuilder
from app.services.selection import AssignmentSelector


class AssignmentService:
    def __init__(
        self,
        *,
        mapping_service: AgentMappingService,
        legacy_agent_repo: LegacyAgentRepository,
        property_repo: ParsedPropertyRepository,
        batch_repo: AssignmentBatchRepository,
        payload_builder: LeadPayloadBuilder,
        selector: AssignmentSelector,
    ) -> None:
        self.mapping_service = mapping_service
        self.legacy_agent_repo = legacy_agent_repo
        self.property_repo = property_repo
        self.batch_repo = batch_repo
        self.payload_builder = payload_builder
        self.selector = selector

    async def take_assignments(
        self,
        *,
        bitrix_user_id: str,
        dry_run: bool,
        bitrix_context: BitrixExecutionContext | None = None,
        expect_sync: bool = False,
    ):
        mapping = await self.mapping_service.resolve_mapping(bitrix_user_id)
        property_classes = await self.legacy_agent_repo.get_property_classes(mapping.agent_phone)
        portal_domain = bitrix_context.portal_domain if bitrix_context else None

        non_realized_count = await self.property_repo.count_non_realized(mapping.agent_phone)
        if non_realized_count >= ASSIGNMENT_LIMIT_THRESHOLD:
            batch = await self.batch_repo.create_batch(
                bitrix_user_id=bitrix_user_id,
                agent_phone=mapping.agent_phone,
                portal_domain=portal_domain,
                requested_count=ASSIGNMENT_BATCH_SIZE,
                assigned_count=0,
                selected_property_classes=property_classes,
                category_counts={"A": 0, "B": 0, "C": 0},
                assignment_status=ASSIGNMENT_STATUS_BLOCKED_LIMIT,
                sync_status=SYNC_STATUS_NOT_REQUESTED,
                dry_run=dry_run,
                error_message=(
                    "У агента уже 15 или больше нереализованных объектов. "
                    "Новая выдача заблокирована."
                ),
                items=[],
            )
            raise AssignmentConflictError(
                "Assignment blocked because the non-realized limit is already reached.",
                batch,
            )

        try:
            selected_ids, category_map = await self.selector.select(
                self._fetch_ids,
                property_classes_filter=property_classes,
                lock_rows=not dry_run,
            )

            if not selected_ids:
                batch = await self.batch_repo.create_batch(
                    bitrix_user_id=bitrix_user_id,
                    agent_phone=mapping.agent_phone,
                    portal_domain=portal_domain,
                    requested_count=ASSIGNMENT_BATCH_SIZE,
                    assigned_count=0,
                    selected_property_classes=property_classes,
                    category_counts={"A": 0, "B": 0, "C": 0},
                    assignment_status=ASSIGNMENT_STATUS_EMPTY_SUPPLY,
                    sync_status=SYNC_STATUS_NOT_REQUESTED,
                    dry_run=dry_run,
                    error_message="Свободных объектов для выдачи не найдено.",
                    items=[],
                )
                raise AssignmentConflictError("No free supply was found for assignment.", batch)

            property_rows = await self.property_repo.fetch_rows_by_ids(selected_ids)
            category_by_id = {
                property_id: category
                for category, property_ids in category_map.items()
                for property_id in property_ids
            }

            items: list[dict[str, Any]] = []
            for index, row in enumerate(property_rows, start=1):
                snapshot = self.payload_builder.build_snapshot(row)
                payload = self.payload_builder.build_payload(row, bitrix_user_id=bitrix_user_id)
                items.append(
                    {
                        "batch_position": index,
                        "vitrina_id": row["vitrina_id"],
                        "category": category_by_id[row["vitrina_id"]],
                        "raw_object_snapshot": snapshot,
                        "lead_payload": payload,
                        "sync_status": SYNC_STATUS_PENDING if expect_sync and not dry_run else SYNC_STATUS_NOT_REQUESTED,
                    }
                )

            if not dry_run:
                await self.property_repo.mark_assigned(selected_ids, mapping.agent_phone)

            batch = await self.batch_repo.create_batch(
                bitrix_user_id=bitrix_user_id,
                agent_phone=mapping.agent_phone,
                portal_domain=portal_domain,
                requested_count=ASSIGNMENT_BATCH_SIZE,
                assigned_count=len(selected_ids),
                selected_property_classes=property_classes,
                category_counts={key: len(value) for key, value in category_map.items()},
                assignment_status=ASSIGNMENT_STATUS_PREVIEW if dry_run else ASSIGNMENT_STATUS_ASSIGNED,
                sync_status=SYNC_STATUS_PENDING if expect_sync and not dry_run else SYNC_STATUS_NOT_REQUESTED,
                dry_run=dry_run,
                error_message=None,
                items=items,
            )
            return batch
        except AssignmentConflictError:
            raise
        except Exception as exc:
            await self.batch_repo.session.rollback()
            batch = await self.batch_repo.create_batch(
                bitrix_user_id=bitrix_user_id,
                agent_phone=mapping.agent_phone,
                portal_domain=portal_domain,
                requested_count=ASSIGNMENT_BATCH_SIZE,
                assigned_count=0,
                selected_property_classes=property_classes,
                category_counts={"A": 0, "B": 0, "C": 0},
                assignment_status=ASSIGNMENT_STATUS_FAILED,
                sync_status=SYNC_STATUS_NOT_REQUESTED,
                dry_run=dry_run,
                error_message=str(exc),
                items=[],
            )
            await self.batch_repo.session.commit()
            raise RuntimeError("Assignment flow failed.") from exc

    async def get_batch(self, batch_id):
        return await self.batch_repo.get_batch(batch_id)

    async def _fetch_ids(
        self,
        category: str,
        limit_count: int,
        exclude_ids: list[int],
        property_classes: list[str] | None,
        lock_rows: bool,
    ) -> list[int]:
        return await self.property_repo.fetch_candidate_ids(
            category=category,
            limit_count=limit_count,
            exclude_ids=exclude_ids,
            property_classes=property_classes,
            lock_rows=lock_rows,
        )
