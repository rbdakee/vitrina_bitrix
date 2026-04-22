from __future__ import annotations

from pydantic import Field

from app.schemas.common import APIModel


class AgentFiltersResponse(APIModel):
    bitrix_user_id: str
    agent_phone: str
    property_classes: list[str] | None


class AgentFiltersUpdateRequest(APIModel):
    property_classes: list[str] = Field(default_factory=list)


class PropertyClassesResponse(APIModel):
    property_classes: list[str]


class BitrixAgentMappingCreate(APIModel):
    bitrix_user_id: str = Field(min_length=1)
    agent_phone: str = Field(min_length=1)
    full_name: str | None = None


class BitrixAgentMappingUpdate(APIModel):
    agent_phone: str | None = None
    full_name: str | None = None


class BitrixAgentMappingResponse(APIModel):
    id: int
    bitrix_user_id: str
    agent_phone: str
    full_name: str | None

