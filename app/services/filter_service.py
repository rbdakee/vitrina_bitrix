from __future__ import annotations

from app.repositories.legacy_agents import LegacyAgentRepository
from app.services.agent_mapping_service import AgentMappingService


class FilterService:
    def __init__(
        self,
        mapping_service: AgentMappingService,
        legacy_agent_repo: LegacyAgentRepository,
    ) -> None:
        self.mapping_service = mapping_service
        self.legacy_agent_repo = legacy_agent_repo

    async def get_filters(self, bitrix_user_id: str) -> tuple[str, list[str] | None]:
        mapping = await self.mapping_service.resolve_mapping(bitrix_user_id)
        return mapping.agent_phone, await self.legacy_agent_repo.get_property_classes(mapping.agent_phone)

    async def update_filters(self, bitrix_user_id: str, property_classes: list[str]) -> tuple[str, list[str] | None]:
        mapping = await self.mapping_service.resolve_mapping(bitrix_user_id)
        normalized = [item.strip() for item in property_classes if item.strip()]
        if normalized:
            await self.legacy_agent_repo.save_property_classes(mapping.agent_phone, normalized)
            return mapping.agent_phone, normalized

        await self.legacy_agent_repo.clear_property_classes(mapping.agent_phone)
        return mapping.agent_phone, None

    async def list_distinct_property_classes(self) -> list[str]:
        return await self.legacy_agent_repo.get_distinct_property_classes()

