from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.dependencies import get_assignment_service
from app.exceptions import AssignmentConflictError, MappingNotFoundError
from app.schemas.assignment import (
    AssignmentBatchResponse,
    AssignmentConflictResponse,
    AssignmentTakeRequest,
)
from app.services.assignment_service import AssignmentService

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post(
    "/take-10",
    response_model=AssignmentBatchResponse,
    responses={409: {"model": AssignmentConflictResponse}},
)
async def take_ten_assignments(
    payload: AssignmentTakeRequest,
    service: AssignmentService = Depends(get_assignment_service),
):
    try:
        batch = await service.take_assignments(
            bitrix_user_id=payload.bitrix_user_id,
            dry_run=payload.dry_run,
        )
        return AssignmentBatchResponse.model_validate(batch)
    except MappingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssignmentConflictError as exc:
        response = AssignmentConflictResponse(
            message=exc.message,
            batch=AssignmentBatchResponse.model_validate(exc.batch),
        )
        return JSONResponse(status_code=409, content=jsonable_encoder(response))


@router.get("/{batch_id}", response_model=AssignmentBatchResponse)
async def get_assignment_batch(
    batch_id: UUID,
    service: AssignmentService = Depends(get_assignment_service),
):
    batch = await service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Assignment batch not found.")
    return AssignmentBatchResponse.model_validate(batch)
