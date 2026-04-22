from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_mapping_service, require_admin_token
from app.exceptions import MappingNotFoundError
from app.schemas.agents import (
    BitrixAgentMappingCreate,
    BitrixAgentMappingResponse,
    BitrixAgentMappingUpdate,
)
from app.schemas.common import MessageResponse
from app.services.agent_mapping_service import AgentMappingService

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


@router.get("/bitrix-agent-mappings", response_model=list[BitrixAgentMappingResponse])
async def list_mappings(
    service: AgentMappingService = Depends(get_mapping_service),
):
    return [BitrixAgentMappingResponse.model_validate(item) for item in await service.list_mappings()]


@router.post(
    "/bitrix-agent-mappings",
    response_model=BitrixAgentMappingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_mapping(
    payload: BitrixAgentMappingCreate,
    service: AgentMappingService = Depends(get_mapping_service),
):
    try:
        entity = await service.create_mapping(payload)
        return BitrixAgentMappingResponse.model_validate(entity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/bitrix-agent-mappings/{bitrix_user_id}", response_model=BitrixAgentMappingResponse)
async def update_mapping(
    bitrix_user_id: str,
    payload: BitrixAgentMappingUpdate,
    service: AgentMappingService = Depends(get_mapping_service),
):
    try:
        entity = await service.update_mapping(bitrix_user_id, payload)
        return BitrixAgentMappingResponse.model_validate(entity)
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/bitrix-agent-mappings/{bitrix_user_id}", response_model=MessageResponse)
async def delete_mapping(
    bitrix_user_id: str,
    service: AgentMappingService = Depends(get_mapping_service),
):
    try:
        await service.delete_mapping(bitrix_user_id)
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MessageResponse(message="Mapping deleted.")

