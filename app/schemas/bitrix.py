from __future__ import annotations

from pydantic import Field

from app.schemas.assignment import AssignmentBatchResponse
from app.schemas.common import APIModel


class BitrixExecutionContext(APIModel):
    portal_domain: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    member_id: str | None = None
    placement: str | None = None


class BitrixToolbarRunRequest(APIModel):
    bitrix_user_id: str = Field(min_length=1)
    dry_run: bool = False
    portal_domain: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    member_id: str | None = None
    placement: str | None = None


class BitrixInstallPayload(APIModel):
    portal_domain: str
    access_token: str
    refresh_token: str | None = None
    member_id: str | None = None


class BitrixInstallResponse(APIModel):
    success: bool
    placement: str
    handler_url: str | None
    details: dict


class BitrixToolbarRunResponse(APIModel):
    batch: AssignmentBatchResponse

