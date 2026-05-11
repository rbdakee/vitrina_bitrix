from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.db.models import BitrixAgentMapping
from app.exceptions import MappingNotFoundError
from app.repositories.bitrix_agent_mappings import BitrixAgentMappingRepository
from app.repositories.legacy_agents import LegacyAgentRepository
from app.schemas.agents import BitrixAgentMappingCreate, BitrixAgentMappingUpdate
from app.schemas.bitrix import BitrixUserProfile
from app.services.phone_utils import normalize_kz_phone


class OnboardingRequiredSignal(Exception):
    def __init__(
        self,
        *,
        bitrix_user_id: str,
        name: str | None,
        last_name: str | None,
        second_name: str | None,
    ) -> None:
        super().__init__(f"Onboarding required for Bitrix user {bitrix_user_id}.")
        self.bitrix_user_id = bitrix_user_id
        self.name = name
        self.last_name = last_name
        self.second_name = second_name

    @property
    def suggested_full_name(self) -> str | None:
        parts = [p for p in (self.last_name, self.name) if p]
        return " ".join(parts) if parts else None


class PhoneAlreadyBoundError(Exception):
    def __init__(self, agent_phone: str, bound_to_bitrix_user_id: str) -> None:
        super().__init__(
            f"Phone {agent_phone} is already bound to Bitrix user {bound_to_bitrix_user_id}."
        )
        self.agent_phone = agent_phone
        self.bound_to_bitrix_user_id = bound_to_bitrix_user_id


class InvalidPhoneError(Exception):
    pass


def _tokenize(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.lower() for part in value.split() if part.strip()}


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

    async def resolve_or_auto_bind(
        self,
        bitrix_user_id: str,
        profile: BitrixUserProfile | None,
    ):
        existing = await self.mapping_repo.get(bitrix_user_id)
        if existing:
            return existing

        if profile is None:
            raise OnboardingRequiredSignal(
                bitrix_user_id=bitrix_user_id,
                name=None,
                last_name=None,
                second_name=None,
            )

        phone_by_name = await self._match_by_name(profile)
        if phone_by_name:
            return await self._create_mapping_for_existing(bitrix_user_id, phone_by_name)

        phone_by_phone = await self._match_by_phone(profile)
        if phone_by_phone:
            return await self._create_mapping_for_existing(bitrix_user_id, phone_by_phone)

        raise OnboardingRequiredSignal(
            bitrix_user_id=bitrix_user_id,
            name=profile.name,
            last_name=profile.last_name,
            second_name=profile.second_name,
        )

    async def onboard(
        self,
        *,
        bitrix_user_id: str,
        raw_phone: str,
        name: str | None,
        last_name: str | None,
        second_name: str | None,
    ) -> tuple[BitrixAgentMapping, bool]:
        existing = await self.mapping_repo.get(bitrix_user_id)
        if existing:
            return existing, False

        normalized = normalize_kz_phone(raw_phone)
        if not normalized:
            raise InvalidPhoneError(
                "Не удалось распознать номер. Введите казахстанский номер: +7XXX..., 8XXX... или 10 цифр."
            )

        existing_mapping_for_phone = await self._find_mapping_by_phone(normalized)
        if existing_mapping_for_phone and existing_mapping_for_phone.bitrix_user_id != bitrix_user_id:
            raise PhoneAlreadyBoundError(normalized, existing_mapping_for_phone.bitrix_user_id)

        legacy_agent = await self.legacy_agent_repo.get_by_phone(normalized)
        created_new_agent = False
        full_name = self._compose_full_name(last_name, name)
        if legacy_agent is None:
            await self.legacy_agent_repo.create_minimal(normalized, full_name)
            created_new_agent = True
        else:
            full_name = legacy_agent.get("full_name") or full_name

        mapping = await self.mapping_repo.create(
            bitrix_user_id=bitrix_user_id,
            agent_phone=normalized,
            full_name=full_name,
        )
        return mapping, created_new_agent

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

    async def _create_mapping_for_existing(self, bitrix_user_id: str, agent_phone: str):
        legacy_agent = await self.legacy_agent_repo.get_by_phone(agent_phone)
        full_name = legacy_agent.get("full_name") if legacy_agent else None
        return await self.mapping_repo.create(
            bitrix_user_id=bitrix_user_id,
            agent_phone=agent_phone,
            full_name=full_name,
        )

    async def _match_by_name(self, profile: BitrixUserProfile) -> str | None:
        bx_tokens = _tokenize(profile.name) | _tokenize(profile.last_name) | _tokenize(profile.second_name)
        if len(bx_tokens) < 2:
            return None
        candidates: list[str] = []
        for agent_phone, full_name in await self.legacy_agent_repo.list_phone_and_name():
            agent_tokens = _tokenize(full_name)
            if not agent_tokens:
                continue
            overlap = bx_tokens & agent_tokens
            if len(overlap) >= 2:
                candidates.append(agent_phone)
                if len(candidates) > 1:
                    return None
        return candidates[0] if len(candidates) == 1 else None

    async def _match_by_phone(self, profile: BitrixUserProfile) -> str | None:
        for raw in (profile.personal_mobile, profile.work_phone):
            normalized = normalize_kz_phone(raw)
            if not normalized:
                continue
            agent = await self.legacy_agent_repo.get_by_phone(normalized)
            if agent:
                return normalized
        return None

    async def _find_mapping_by_phone(self, agent_phone: str):
        for mapping in await self.mapping_repo.list():
            if mapping.agent_phone == agent_phone:
                return mapping
        return None

    @staticmethod
    def _compose_full_name(last_name: str | None, name: str | None) -> str | None:
        parts = [p.strip() for p in (last_name, name) if p and p.strip()]
        return " ".join(parts) if parts else None
