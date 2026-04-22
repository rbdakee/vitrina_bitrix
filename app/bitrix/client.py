from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.schemas.bitrix import BitrixExecutionContext


class BitrixApiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def call_method(
        self,
        context: BitrixExecutionContext,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if not context.portal_domain or not context.access_token:
            raise ValueError("Bitrix portal_domain and access_token are required.")

        url = f"https://{context.portal_domain}/rest/{method}.json"
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.post(
                url,
                params={"auth": context.access_token},
                json=params,
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                description = payload.get("error_description") or payload["error"]
                raise RuntimeError(description)
            return payload

    async def bind_toolbar_placement(
        self,
        context: BitrixExecutionContext,
        handler_url: str,
    ) -> dict[str, Any]:
        return await self.call_method(
            context,
            "placement.bind",
            {
                "PLACEMENT": "CRM_LEAD_LIST_TOOLBAR",
                "HANDLER": handler_url,
                "TITLE": "Добавить 10 объектов",
                "DESCRIPTION": "Vitrina cold assignment",
            },
        )

    async def unbind_toolbar_placement(self, context: BitrixExecutionContext) -> dict[str, Any]:
        return await self.call_method(
            context,
            "placement.unbind",
            {
                "PLACEMENT": "CRM_LEAD_LIST_TOOLBAR",
                "HANDLER": self.settings.bitrix_toolbar_url,
            },
        )

    async def create_lead(
        self,
        context: BitrixExecutionContext,
        normalized_payload: dict[str, Any],
    ) -> str:
        phones = normalized_payload.get("phones") or []
        fields: dict[str, Any] = {
            "TITLE": normalized_payload["title"],
            "ASSIGNED_BY_ID": normalized_payload["assignedById"],
            "SOURCE_ID": normalized_payload["sourceId"],
            "SOURCE_DESCRIPTION": normalized_payload["sourceDescription"],
            "COMMENTS": normalized_payload["comments"],
            "ORIGINATOR_ID": normalized_payload["originatorId"],
            "ORIGIN_ID": normalized_payload["originId"],
        }
        if phones:
            fields["PHONE"] = [
                {"VALUE": phone["value"], "VALUE_TYPE": phone.get("valueType", "WORK")}
                for phone in phones
            ]
        if normalized_payload.get("stageId"):
            fields["STAGE_ID"] = normalized_payload["stageId"]
        if normalized_payload.get("categoryId"):
            fields["CATEGORY_ID"] = normalized_payload["categoryId"]

        response = await self.call_method(context, "crm.lead.add", {"fields": fields})
        return str(response["result"])

