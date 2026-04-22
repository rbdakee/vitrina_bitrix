from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.exceptions import MappingNotFoundError
from app.repositories.bitrix_agent_mappings import BitrixAgentMappingRepository
from app.repositories.legacy_agents import LegacyAgentRepository
from app.schemas.agents import BitrixAgentMappingCreate, BitrixAgentMappingUpdate


class AgentMappingService:
    def __init__(
        self,
        mapping_repo: BitrixAgentMappingRepository,
        legacy_agent_repo: LegacyAgentRepository,
    ) -> None:
        self.mapping_repo = mapping_repo
        self.legacy_agent_repo = legacy_agent_repo

    async def list_mappings(self):
        return await self.mapping_repo.list()

    async def resolve_mapping(self, bitrix_user_id: str):
        mapping = await self.mapping_repo.get(bitrix_user_id)
        if not mapping:
            raise MappingNotFoundError(f"Mapping for Bitrix user `{bitrix_user_id}` was not found.")
        return mapping

    async def create_mapping(self, payload: BitrixAgentMappingCreate):
        legacy_agent = await self.legacy_agent_repo.get_by_phone(payload.agent_phone)
        if not legacy_agent:
            raise ValueError(f"Legacy agent `{payload.agent_phone}` does not exist in vitrina_agents.")

        full_name = payload.full_name or legacy_agent.get("full_name")
        try:
            return await self.mapping_repo.create(
                bitrix_user_id=payload.bitrix_user_id,
                agent_phone=payload.agent_phone,
                full_name=full_name,
            )
        except IntegrityError as exc:
            await self.mapping_repo.session.rollback()
            raise ValueError("bitrix_user_id must be unique.") from exc

    async def update_mapping(self, bitrix_user_id: str, payload: BitrixAgentMappingUpdate):
        mapping = await self.resolve_mapping(bitrix_user_id)

        if payload.agent_phone:
            legacy_agent = await self.legacy_agent_repo.get_by_phone(payload.agent_phone)
            if not legacy_agent:
                raise ValueError(f"Legacy agent `{payload.agent_phone}` does not exist in vitrina_agents.")
            mapping.agent_phone = payload.agent_phone
            if payload.full_name is None:
                mapping.full_name = legacy_agent.get("full_name")

        if payload.full_name is not None:
            mapping.full_name = payload.full_name

        await self.mapping_repo.session.flush()
        return mapping

    async def delete_mapping(self, bitrix_user_id: str) -> bool:
        deleted = await self.mapping_repo.delete(bitrix_user_id)
        if not deleted:
            raise MappingNotFoundError(f"Mapping for Bitrix user `{bitrix_user_id}` was not found.")
        return True
