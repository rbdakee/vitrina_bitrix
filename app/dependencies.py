from __future__ import annotations

from pathlib import Path

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bitrix.client import BitrixApiClient
from app.config import Settings
from app.db.session import get_db_session
from app.repositories.assignment_batches import AssignmentBatchRepository
from app.repositories.bitrix_agent_mappings import BitrixAgentMappingRepository
from app.repositories.legacy_agents import LegacyAgentRepository
from app.repositories.parsed_properties import ParsedPropertyRepository
from app.services.agent_mapping_service import AgentMappingService
from app.services.assignment_service import AssignmentService
from app.services.bitrix_deal_sync import BitrixDealSyncService
from app.services.bitrix_placement import BitrixPlacementService
from app.services.complex_matcher import ComplexMatcher
from app.services.deal_payload import DealPayloadBuilder
from app.services.filter_service import FilterService
from app.services.selection import AssignmentSelector


_complex_matcher_singleton: ComplexMatcher | None = None


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_bitrix_client(settings: Settings = Depends(get_settings_dependency)) -> BitrixApiClient:
    return BitrixApiClient(settings)


def get_complex_matcher(
    settings: Settings = Depends(get_settings_dependency),
    client: BitrixApiClient = Depends(get_bitrix_client),
) -> ComplexMatcher:
    global _complex_matcher_singleton
    if _complex_matcher_singleton is None:
        _complex_matcher_singleton = ComplexMatcher(
            client=client,
            cache_path=Path(settings.bitrix_complex_cache_path),
        )
    return _complex_matcher_singleton


def get_mapping_service(
    session: AsyncSession = Depends(get_db_session),
) -> AgentMappingService:
    return AgentMappingService(
        mapping_repo=BitrixAgentMappingRepository(session),
        legacy_agent_repo=LegacyAgentRepository(session),
    )


def get_filter_service(
    session: AsyncSession = Depends(get_db_session),
    mapping_service: AgentMappingService = Depends(get_mapping_service),
) -> FilterService:
    return FilterService(
        mapping_service=mapping_service,
        legacy_agent_repo=LegacyAgentRepository(session),
    )


def get_assignment_service(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
    mapping_service: AgentMappingService = Depends(get_mapping_service),
) -> AssignmentService:
    return AssignmentService(
        mapping_service=mapping_service,
        legacy_agent_repo=LegacyAgentRepository(session),
        property_repo=ParsedPropertyRepository(session),
        batch_repo=AssignmentBatchRepository(session),
        payload_builder=DealPayloadBuilder(settings),
        selector=AssignmentSelector(),
    )


def get_bitrix_deal_sync_service(
    session: AsyncSession = Depends(get_db_session),
    client: BitrixApiClient = Depends(get_bitrix_client),
    matcher: ComplexMatcher = Depends(get_complex_matcher),
) -> BitrixDealSyncService:
    return BitrixDealSyncService(
        batch_repo=AssignmentBatchRepository(session),
        client=client,
        complex_matcher=matcher,
    )


def get_bitrix_placement_service(
    settings: Settings = Depends(get_settings_dependency),
    client: BitrixApiClient = Depends(get_bitrix_client),
) -> BitrixPlacementService:
    return BitrixPlacementService(settings=settings, client=client)


def require_admin_token(
    request: Request,
    settings: Settings = Depends(get_settings_dependency),
) -> None:
    token = request.headers.get("X-Admin-Token")
    if token != settings.admin_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-Admin-Token.",
        )


def require_bitrix_enabled(
    settings: Settings = Depends(get_settings_dependency),
) -> None:
    if not settings.bitrix_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bitrix integration is disabled.",
        )
