from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_filter_service
from app.exceptions import MappingNotFoundError
from app.schemas.agents import AgentFiltersResponse, AgentFiltersUpdateRequest, PropertyClassesResponse
from app.services.filter_service import FilterService

router = APIRouter(tags=["agents"])


@router.get("/agents/{bitrix_user_id}/filters", response_model=AgentFiltersResponse)
async def get_agent_filters(
    bitrix_user_id: str,
    service: FilterService = Depends(get_filter_service),
):
    try:
        agent_phone, property_classes = await service.get_filters(bitrix_user_id)
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentFiltersResponse(
        bitrix_user_id=bitrix_user_id,
        agent_phone=agent_phone,
        property_classes=property_classes,
    )


@router.put("/agents/{bitrix_user_id}/filters", response_model=AgentFiltersResponse)
async def update_agent_filters(
    bitrix_user_id: str,
    payload: AgentFiltersUpdateRequest,
    service: FilterService = Depends(get_filter_service),
):
    try:
        agent_phone, property_classes = await service.update_filters(
            bitrix_user_id,
            payload.property_classes,
        )
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return AgentFiltersResponse(
        bitrix_user_id=bitrix_user_id,
        agent_phone=agent_phone,
        property_classes=property_classes,
    )


@router.get("/property-classes", response_model=PropertyClassesResponse)
async def list_property_classes(
    service: FilterService = Depends(get_filter_service),
):
    return PropertyClassesResponse(
        property_classes=await service.list_distinct_property_classes()
    )

