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


class BitrixUserProfile(APIModel):
    name: str | None = None
    last_name: str | None = None
    second_name: str | None = None
    work_phone: str | None = None
    personal_mobile: str | None = None


class BitrixToolbarRunRequest(APIModel):
    bitrix_user_id: str = Field(min_length=1)
    dry_run: bool = False
    portal_domain: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    member_id: str | None = None
    placement: str | None = None
    profile: BitrixUserProfile | None = None


class BitrixOnboardRequest(APIModel):
    bitrix_user_id: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    name: str | None = None
    last_name: str | None = None
    second_name: str | None = None


class BitrixOnboardResponse(APIModel):
    success: bool
    agent_phone: str
    full_name: str | None
    created_new_agent: bool


class BitrixNeedsOnboardingResponse(APIModel):
    status: str = "needs_onboarding"
    bitrix_user_id: str
    suggested_full_name: str | None
    name: str | None
    last_name: str | None
    second_name: str | None


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

